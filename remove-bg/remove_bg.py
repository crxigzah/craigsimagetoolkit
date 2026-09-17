#!/usr/bin/env python3
"""Removes the background from photos, leaving a transparent PNG, using
rembg (an ONNX background-removal model, not a plain color/chroma-key
trick -- it works on ordinary photo backgrounds, not just solid colors).

Defaults to the "u2netp" model: about 5MB and fast, well suited to
running in CI on every push. "--model u2net" or "--model
isnet-general-use" trade a slower first run and a larger one-time
download (both fetched automatically by rembg on first use) for
noticeably better edge quality on harder photos.

Output is always a PNG regardless of the input format, since only PNG
can actually store the transparency this tool adds.
"""
import argparse
import os
import sys
from pathlib import Path

from rembg import new_session, remove

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
DEFAULT_MODEL = "u2netp"


def find_image_files(root: Path, recursive: bool) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() in IMAGE_EXTENSIONS else []
    pattern = "**/*" if recursive else "*"
    return sorted(p for p in root.glob(pattern) if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)


def output_path_for(src: Path, output_dir: Path | None, suffix: str) -> Path:
    name = f"{src.stem}{suffix}.png"
    return (output_dir / name) if output_dir else src.with_name(name)


def write_github_output(files_processed: int):
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a") as f:
        f.write(f"files-processed={files_processed}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--path", default=".", help="Image file or directory to process")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                         help=f"rembg model name (default: {DEFAULT_MODEL}). Also common: u2net, isnet-general-use")
    parser.add_argument("--output-dir", type=Path, help="Write output PNGs here instead of alongside the originals")
    parser.add_argument("--suffix", default=".nobg", help="Filename suffix before .png (default: .nobg)")
    parser.add_argument("--no-recursive", dest="recursive", action="store_false", default=True)
    args = parser.parse_args()

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

    try:
        session = new_session(args.model)
    except Exception as e:
        print(f"::error::Could not load model {args.model!r}: {e}", file=sys.stderr)
        sys.exit(2)

    processed = 0
    for src in files:
        try:
            input_bytes = src.read_bytes()
            output_bytes = remove(input_bytes, session=session)
            dest = output_path_for(src, args.output_dir, args.suffix)
            dest.write_bytes(output_bytes)
        except Exception as e:
            print(f"::warning::Could not process {src}: {e}")
            continue
        processed += 1
        print(f"{src} → {dest}")

    print(f"\nRemoved the background from {processed} of {len(files)} file(s) using {args.model}.")
    write_github_output(files_processed=processed)


if __name__ == "__main__":
    main()
