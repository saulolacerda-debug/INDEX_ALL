#!/usr/bin/env python3
"""INDEX_ALL - Recursively index all files in a directory."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone


def index_all(root_dir: str, extensions: list[str] | None = None) -> list[dict]:
    """Recursively index all files under root_dir.

    Args:
        root_dir: The directory to index.
        extensions: Optional list of file extensions to include (e.g. ['.py', '.txt']).
                    If None, all files are indexed.

    Returns:
        A list of dicts, each describing one file:
            path, name, size, modified_at
    """
    root_dir = os.path.abspath(root_dir)
    if not os.path.isdir(root_dir):
        raise NotADirectoryError(f"Not a directory: {root_dir}")

    ext_filter = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions} if extensions else None

    entries = []
    for dirpath, _dirnames, filenames in os.walk(root_dir):
        for filename in sorted(filenames):
            if ext_filter is not None:
                _, ext = os.path.splitext(filename)
                if ext.lower() not in ext_filter:
                    continue

            full_path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(full_path, root_dir)

            try:
                stat = os.stat(full_path)
                entries.append(
                    {
                        "path": rel_path,
                        "name": filename,
                        "size": stat.st_size,
                        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    }
                )
            except OSError:
                continue

    return entries


def format_table(entries: list[dict]) -> str:
    """Format index entries as a human-readable table."""
    if not entries:
        return "No files found."

    headers = ("Path", "Size (bytes)", "Modified")
    rows = [(e["path"], str(e["size"]), e["modified_at"]) for e in entries]

    col_widths = [
        max(len(headers[0]), max(len(r[0]) for r in rows)),
        max(len(headers[1]), max(len(r[1]) for r in rows)),
        max(len(headers[2]), max(len(r[2]) for r in rows)),
    ]

    sep = "+-" + "-+-".join("-" * w for w in col_widths) + "-+"
    fmt = "| " + " | ".join(f"{{:<{w}}}" for w in col_widths) + " |"

    lines = [
        sep,
        fmt.format(*headers),
        sep,
        *[fmt.format(*r) for r in rows],
        sep,
        f"Total: {len(entries)} file(s)",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="INDEX_ALL: Recursively index all files in a directory.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("directory", nargs="?", default=".", help="Directory to index (default: current directory)")
    parser.add_argument(
        "-e",
        "--ext",
        metavar="EXT",
        nargs="+",
        help="Filter by file extension(s), e.g. -e .py .txt",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output as JSON instead of a table",
    )

    args = parser.parse_args(argv)

    try:
        entries = index_all(args.directory, extensions=args.ext)
    except NotADirectoryError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps(entries, indent=2))
    else:
        print(format_table(entries))

    return 0


if __name__ == "__main__":
    sys.exit(main())
