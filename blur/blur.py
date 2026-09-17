#!/usr/bin/env python3
"""Applies a Gaussian blur to whole images, using Pillow.

This blurs the entire image uniformly (a placeholder/preview effect, a
privacy blur over a whole photo, a soft background image behind text,
etc). It does not detect faces or blur a specific region only -- every
pixel gets the same radius.
"""
import argparse
import os
import sys
from pathlib import Path

from PIL import Image, ImageFilter

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
DEFAULT_RADIUS = 8


def find_image_files(root: Path, recursive: bool) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() in IMAGE_EXTENSIONS else []
    pattern = "**/*" if recursive else "*"
    return sorted(p for p in root.glob(pattern) if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)


def blur_image(img: Image.Image, radius: float) -> Image.Image:
    return img.filter(ImageFilter.GaussianBlur(radius=radius))


def output_path_for(src: Path, output_dir: Path | None, in_place: bool, suffix: str) -> Path:
    if in_place:
        return src
    name = f"{src.stem}{suffix}{src.suffix}"
    return (output_dir / name) if output_dir else src.with_name(name)


def write_github_output(files_processed: int):
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a") as f:
        f.write(f"files-processed={files_processed}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--path", default=".", help="Image file or directory to blur")
    parser.add_argument("--radius", type=float, default=DEFAULT_RADIUS,
                         help=f"Blur radius in pixels, higher is blurrier (default: {DEFAULT_RADIUS})")
    parser.add_argument("--suffix", default=".blurred", help="Filename suffix before the extension (default: .blurred)")
    parser.add_argument("--output-dir", type=Path, help="Write blurred images here instead of alongside the originals")
    parser.add_argument("--in-place", action="store_true", help="Overwrite the original file instead of writing a new one (destructive)")
    parser.add_argument("--no-recursive", dest="recursive", action="store_false", default=True)
    args = parser.parse_args()

    if args.radius <= 0:
        print(f"::error::--radius must be greater than 0 (got {args.radius})", file=sys.stderr)
        sys.exit(2)

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
                result = blur_image(img, args.radius)
                dest = output_path_for(src, args.output_dir, args.in_place, args.suffix)
                if dest.suffix.lower() in (".jpg", ".jpeg") and result.mode == "RGBA":
                    result = result.convert("RGB")
                result.save(dest)
        except Exception as e:
            print(f"::warning::Could not blur {src}: {e}")
            continue
        processed += 1
        print(f"{src} → {dest} (radius {args.radius})")

    print(f"\nBlurred {processed} of {len(files)} file(s) at radius {args.radius}.")
    write_github_output(files_processed=processed)


if __name__ == "__main__":
    main()
