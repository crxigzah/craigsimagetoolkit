#!/usr/bin/env python3
"""Resizes images to common social platform sizes (see presets.json) or a
custom width/height, using Pillow.

Two fit modes: "cover" (default) scales the image up or down until it
fully fills the target box, then center crops whatever hangs over the
edges -- the same "fill the frame" behavior every platform's own upload
cropper uses, so a profile picture or square post never comes out
letterboxed. "contain" instead scales the image to fit entirely inside
the box and pads the rest with a background color, so nothing is ever
cropped out.

Platform preset sizes in presets.json are commonly recommended values
at time of writing -- platforms change these occasionally, so double
check current guidelines if exact pixel accuracy matters. Add your own
named presets there without touching this file.
"""
import argparse
import json
import os
import sys
from pathlib import Path

from PIL import Image

PRESETS_PATH = Path(__file__).resolve().parent / "presets.json"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def load_presets() -> dict:
    return json.loads(PRESETS_PATH.read_text())


def normalize_mode(img: Image.Image) -> Image.Image:
    """Palette (P) and grayscale-with-alpha (LA) images need converting
    before resize/paste operations -- keeps transparency where the
    source actually has it, drops to plain RGB otherwise."""
    if img.mode == "P":
        return img.convert("RGBA") if "transparency" in img.info else img.convert("RGB")
    if img.mode == "LA":
        return img.convert("RGBA")
    return img


def resize_cover(img: Image.Image, width: int, height: int) -> Image.Image:
    src_w, src_h = img.size
    scale = max(width / src_w, height / src_h)
    new_w, new_h = max(1, round(src_w * scale)), max(1, round(src_h * scale))
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - width) // 2
    top = (new_h - height) // 2
    return resized.crop((left, top, left + width, top + height))


def resize_contain(img: Image.Image, width: int, height: int, background: str) -> Image.Image:
    src_w, src_h = img.size
    scale = min(width / src_w, height / src_h)
    new_w, new_h = max(1, round(src_w * scale)), max(1, round(src_h * scale))
    resized = img.resize((new_w, new_h), Image.LANCZOS)

    has_alpha = resized.mode == "RGBA" or "transparency" in resized.info
    mode = "RGBA" if has_alpha else "RGB"
    if has_alpha and resized.mode != "RGBA":
        resized = resized.convert("RGBA")

    canvas = Image.new(mode, (width, height), background)
    offset = ((width - new_w) // 2, (height - new_h) // 2)
    canvas.paste(resized, offset, resized if has_alpha else None)
    return canvas


def resize_image(img: Image.Image, width: int, height: int, mode: str, background: str) -> Image.Image:
    img = normalize_mode(img)
    if mode == "cover":
        return resize_cover(img, width, height)
    return resize_contain(img, width, height, background)


def find_image_files(root: Path, recursive: bool) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() in IMAGE_EXTENSIONS else []
    pattern = "**/*" if recursive else "*"
    return sorted(p for p in root.glob(pattern) if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)


def output_path_for(src: Path, label: str, output_dir: Path | None, in_place: bool) -> Path:
    if in_place:
        return src
    name = f"{src.stem}.{label}{src.suffix}"
    return (output_dir / name) if output_dir else src.with_name(name)


def parse_size(raw: str) -> tuple[int, int]:
    try:
        w_str, h_str = raw.lower().split("x")
        return int(w_str), int(h_str)
    except (ValueError, AttributeError):
        raise ValueError(f"--size must look like WIDTHxHEIGHT, e.g. 1080x1080 (got {raw!r})")


def write_github_output(files_processed: int):
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a") as f:
        f.write(f"files-processed={files_processed}\n")


def print_presets(presets: dict):
    name_width = max(len(n) for n in presets) + 2
    for name, spec in sorted(presets.items()):
        size = f"{spec['width']}x{spec['height']}"
        print(f"{name.ljust(name_width)}{size.ljust(10)}{spec.get('description', '')}")


def main():
    presets = load_presets()

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--path", default=".", help="Image file or directory to resize")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--preset", choices=sorted(presets), help="Named preset from presets.json")
    group.add_argument("--size", metavar="WIDTHxHEIGHT", help="Custom size, e.g. 800x600")
    parser.add_argument("--list-presets", action="store_true", help="Print all available presets and exit")
    parser.add_argument("--mode", choices=["cover", "contain"], default="cover",
                         help="cover fills the frame and crops overflow (default); contain fits the whole image and pads")
    parser.add_argument("--background", default="white", help="Padding color for --mode contain (default: white)")
    parser.add_argument("--output-dir", type=Path, help="Write resized images here instead of alongside the originals")
    parser.add_argument("--in-place", action="store_true", help="Overwrite the original file instead of writing a new one (destructive)")
    parser.add_argument("--no-recursive", dest="recursive", action="store_false", default=True)
    args = parser.parse_args()

    if args.list_presets:
        print_presets(presets)
        return

    if not args.preset and not args.size:
        parser.error("one of --preset, --size, or --list-presets is required")

    if args.preset:
        width, height = presets[args.preset]["width"], presets[args.preset]["height"]
        label = args.preset
    else:
        try:
            width, height = parse_size(args.size)
        except ValueError as e:
            print(f"::error::{e}", file=sys.stderr)
            sys.exit(2)
        label = f"{width}x{height}"

    root = Path(args.path)
    if not root.exists():
        print(f"::error::Path does not exist: {root}", file=sys.stderr)
        sys.exit(2)

    files = find_image_files(root, args.recursive)
    if not files:
        print("No image files found.")
        write_github_output(files_processed=0)
        return

    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)

    processed = 0
    for src in files:
        try:
            with Image.open(src) as img:
                result = resize_image(img, width, height, args.mode, args.background)
                dest = output_path_for(src, label, args.output_dir, args.in_place)
                save_kwargs = {}
                if dest.suffix.lower() in (".jpg", ".jpeg"):
                    if result.mode == "RGBA":
                        result = result.convert("RGB")
                    save_kwargs["quality"] = 90
                result.save(dest, **save_kwargs)
        except Exception as e:
            print(f"::warning::Could not resize {src}: {e}")
            continue
        processed += 1
        print(f"{src} → {dest} ({width}x{height}, {args.mode})")

    print(f"\nResized {processed} of {len(files)} file(s) to {width}x{height} ({label}).")
    write_github_output(files_processed=processed)


if __name__ == "__main__":
    main()
