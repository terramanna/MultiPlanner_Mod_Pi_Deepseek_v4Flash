"""Reject oversized source files before they become maintenance hazards."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import PurePosixPath


MAX_LINES = 600
EXCLUDED_SUFFIXES = {".lock", ".min.js", ".map"}
EXCLUDED_FILENAMES = {"package-lock.json", "npm-shrinkwrap.json"}
EXCLUDED_PATH_PARTS = {"node_modules", "vendor", "dist", "build"}


def staged_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def should_check(path: str) -> bool:
    candidate = PurePosixPath(path)
    return (
        candidate.name not in EXCLUDED_FILENAMES
        and candidate.suffix not in EXCLUDED_SUFFIXES
        and not any(part in EXCLUDED_PATH_PARTS for part in candidate.parts)
    )


def staged_line_count(path: str) -> int:
    result = subprocess.run(["git", "show", f":{path}"], check=True, capture_output=True, text=True)
    return len(result.stdout.splitlines())


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def working_tree_line_count(path: str) -> int:
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        return sum(1 for _ in handle)


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged", action="store_true")
    mode.add_argument("--all", action="store_true")
    args = parser.parse_args()

    oversized: list[tuple[str, int]] = []
    candidates = staged_files() if args.staged else tracked_files()
    for path in candidates:
        if should_check(path):
            lines = staged_line_count(path) if args.staged else working_tree_line_count(path)
            if lines > MAX_LINES:
                oversized.append((path, lines))
    if oversized:
        print(f"Source files may not exceed {MAX_LINES} lines:", file=sys.stderr)
        for path, lines in oversized:
            print(f"  {path}: {lines}", file=sys.stderr)
        print("Split the file or document and approve a narrowly scoped exception.", file=sys.stderr)
        return 1

    scope = "staged files" if args.staged else "tracked files"
    print(f"Checked {scope}. No file exceeds {MAX_LINES} lines.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
