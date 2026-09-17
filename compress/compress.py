#!/usr/bin/env python3
"""Losslessly compresses every PNG file under a given path using oxipng.

Used both as a standalone CLI tool and as the script behind this repo's
own GitHub Action (see action.yml) -- kept to a single dependency so the
Action installs fast on every run.
"""
import argparse
import os
import sys
from pathlib import Path

import oxipng


def find_png_files(root: Path, recursive: bool) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() == ".png" else []
    # Path.glob is case-sensitive on Linux (GitHub Actions runners), so
    # both extensions are searched explicitly rather than relying on a
    # case-insensitive filesystem that won't exist in CI.
    pattern = "**/*" if recursive else "*"
    files = [p for p in root.glob(pattern) if p.is_file() and p.suffix.lower() == ".png"]
    return sorted(set(files))


def format_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def compress_files(png_files: list[Path], level: int, check: bool):
    """Returns (rows, total_before, total_after, files_needing_work) where
    rows is [(path, before_size, after_size, pct_saved), ...]."""
    rows = []
    files_needing_work = []
    total_before = total_after = 0

    for path in png_files:
        try:
            original_bytes = path.read_bytes()
        except OSError as e:
            print(f"::warning::Could not read {path}: {e}")
            continue

        original_size = len(original_bytes)
        try:
            optimized_bytes = oxipng.optimize_from_memory(original_bytes, level=level)
        except Exception as e:
            print(f"::warning::Could not optimize {path}: {e}")
            continue

        optimized_size = len(optimized_bytes)
        total_before += original_size
        total_after += optimized_size

        if optimized_size < original_size:
            files_needing_work.append(path)
            if not check:
                path.write_bytes(optimized_bytes)

        pct_saved = (1 - optimized_size / original_size) * 100 if original_size else 0.0
        rows.append((path, original_size, optimized_size, pct_saved))

    return rows, total_before, total_after, files_needing_work


def print_summary(rows, total_before: int, total_after: int, check: bool):
    if not rows:
        print("No PNG files found.")
        return

    verb = "Would compress" if check else "Compressed"
    print(f"\n{verb} {len(rows)} PNG file(s):\n")

    name_width = min(max(len(str(r[0])) for r in rows) + 2, 70)
    header = f"{'File'.ljust(name_width)}{'Before'.rjust(10)}{'After'.rjust(10)}{'Saved'.rjust(9)}"
    print(header)
    print("-" * len(header))
    for path, before, after, pct in rows:
        print(f"{str(path).ljust(name_width)}{format_bytes(before).rjust(10)}{format_bytes(after).rjust(10)}{f'{pct:.1f}%'.rjust(9)}")

    total_pct = (1 - total_after / total_before) * 100 if total_before else 0.0
    print(f"\nTotal: {format_bytes(total_before)} → {format_bytes(total_after)} ({total_pct:.1f}% saved)")


def write_github_output(files_processed: int, bytes_saved: int):
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a") as f:
        f.write(f"files-processed={files_processed}\n")
        f.write(f"bytes-saved={bytes_saved}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default=".", help="File or directory to search for PNGs (default: current directory)")
    parser.add_argument("--level", type=int, default=4, choices=range(0, 7), metavar="[0-6]", help="Oxipng optimization level, higher is slower but smaller (default: 4)")
    parser.add_argument("--no-recursive", dest="recursive", action="store_false", default=True, help="Only search the top level of --path, not subdirectories")
    parser.add_argument("--check", action="store_true", help="Report savings without modifying files; exit 1 if any file could shrink further")
    args = parser.parse_args()

    root = Path(args.path)
    if not root.exists():
        print(f"::error::Path does not exist: {root}", file=sys.stderr)
        sys.exit(2)

    png_files = find_png_files(root, args.recursive)
    rows, total_before, total_after, files_needing_work = compress_files(png_files, args.level, args.check)
    print_summary(rows, total_before, total_after, args.check)
    write_github_output(files_processed=len(rows), bytes_saved=total_before - total_after)

    if args.check and files_needing_work:
        print(f"\n{len(files_needing_work)} file(s) can be compressed further. Run without --check to fix them.")
        sys.exit(1)


if __name__ == "__main__":
    main()
