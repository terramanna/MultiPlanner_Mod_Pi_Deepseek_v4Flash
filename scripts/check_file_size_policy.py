"""Reject oversized source files before they become maintenance hazards."""

from __future__ import annotations

import ast
import argparse
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath


MAX_LINES = 600
MAX_FUNCTION_LINES = 30
SOURCE_SUFFIXES = {".js", ".py", ".ps1"}
EXCLUDED_SUFFIXES = {".lock", ".min.js", ".map"}
EXCLUDED_FILENAMES = {"package-lock.json", "npm-shrinkwrap.json"}
EXCLUDED_PATH_PARTS = {"node_modules", "vendor", "dist", "build"}
FUNCTION_LENGTH_EXCLUDED_PATHS = {"scripts/check_file_size_policy.py"}
JS_FUNCTION_START_PATTERNS = (
    re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\("),
    re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?function\s*\("),
    re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?(?:\([^;{}]*\)|[A-Za-z_$][\w$]*)\s*=>\s*\{"),
)


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
        and candidate.suffix in SOURCE_SUFFIXES
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


def staged_source_text(path: str) -> str:
    result = subprocess.run(["git", "show", f":{path}"], check=True, capture_output=True, text=True)
    return result.stdout


def working_tree_source_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def python_function_spans(source: str) -> list[tuple[str, int, int]]:
    spans: list[tuple[str, int, int]] = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is not None:
                spans.append((node.name, node.lineno, end_lineno))
    return spans


def js_function_spans(source: str) -> list[tuple[str, int, int]]:
    lines = source.splitlines()
    spans: list[tuple[str, int, int]] = []
    line_index = 0
    while line_index < len(lines):
        match = _js_function_start(lines[line_index])
        if not match:
            line_index += 1
            continue

        name = match.group(1)
        start_index = line_index
        end_index = _js_function_end(lines, line_index)
        if end_index is not None:
            spans.append((name, start_index + 1, end_index + 1))
            line_index = end_index + 1
            continue
        line_index += 1
    return spans


def _js_function_start(line: str):
    for pattern in JS_FUNCTION_START_PATTERNS:
        match = pattern.match(line)
        if match:
            return match
    return None


def _js_function_end(lines: list[str], start_index: int) -> int | None:
    state = {
        "single": False,
        "double": False,
        "template": False,
        "block_comment": False,
        "escape": False,
    }
    depth = 0
    found_body = False
    for line_index in range(start_index, len(lines)):
        cleaned = _strip_js_comments_and_strings(lines[line_index], state)
        if not found_body:
            if "{" not in cleaned:
                continue
            found_body = True
        depth += cleaned.count("{") - cleaned.count("}")
        if found_body and depth == 0:
            return line_index
    return None


def _strip_js_comments_and_strings(line: str, state: dict[str, bool]) -> str:
    cleaned: list[str] = []
    index = 0
    while index < len(line):
        ch = line[index]
        nxt = line[index + 1] if index + 1 < len(line) else ""

        if state["block_comment"]:
            if ch == "*" and nxt == "/":
                state["block_comment"] = False
                index += 2
            else:
                index += 1
            continue

        if state["template"]:
            if state["escape"]:
                state["escape"] = False
            elif ch == "\\":
                state["escape"] = True
            elif ch == "`":
                state["template"] = False
            index += 1
            continue

        if state["single"]:
            if state["escape"]:
                state["escape"] = False
            elif ch == "\\":
                state["escape"] = True
            elif ch == "'":
                state["single"] = False
            index += 1
            continue

        if state["double"]:
            if state["escape"]:
                state["escape"] = False
            elif ch == "\\":
                state["escape"] = True
            elif ch == '"':
                state["double"] = False
            index += 1
            continue

        if ch == "/" and nxt == "/":
            break
        if ch == "/" and nxt == "*":
            state["block_comment"] = True
            index += 2
            continue
        if ch == "'":
            state["single"] = True
            index += 1
            continue
        if ch == '"':
            state["double"] = True
            index += 1
            continue
        if ch == "`":
            state["template"] = True
            index += 1
            continue

        cleaned.append(ch)
        index += 1

    state["escape"] = False
    return "".join(cleaned)


def function_violations(path: str, source: str) -> list[tuple[str, int]]:
    if path in FUNCTION_LENGTH_EXCLUDED_PATHS:
        return []

    suffix = PurePosixPath(path).suffix
    if suffix == ".py":
        spans = python_function_spans(source)
    elif suffix == ".js":
        spans = js_function_spans(source)
    else:
        spans = []

    violations: list[tuple[str, int]] = []
    for name, start_line, end_line in spans:
        line_count = end_line - start_line + 1
        if line_count > MAX_FUNCTION_LINES:
            violations.append((f"{path}:{name}", line_count))
    return violations


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged", action="store_true")
    mode.add_argument("--all", action="store_true")
    args = parser.parse_args()

    oversized: list[tuple[str, int]] = []
    long_functions: list[tuple[str, int]] = []
    candidates = staged_files() if args.staged else tracked_files()
    for path in candidates:
        if should_check(path):
            lines = staged_line_count(path) if args.staged else working_tree_line_count(path)
            if lines > MAX_LINES:
                oversized.append((path, lines))
            source = staged_source_text(path) if args.staged else working_tree_source_text(path)
            long_functions.extend(function_violations(path, source))
    if oversized:
        print(f"Source files may not exceed {MAX_LINES} lines:", file=sys.stderr)
        for path, lines in oversized:
            print(f"  {path}: {lines}", file=sys.stderr)
        print("Split the file or document and approve a narrowly scoped exception.", file=sys.stderr)
        return 1

    if long_functions:
        print(f"Functions may not exceed {MAX_FUNCTION_LINES} lines:", file=sys.stderr)
        for path, lines in long_functions:
            print(f"  {path}: {lines}", file=sys.stderr)
        print("Extract helpers until each function fits under the limit.", file=sys.stderr)
        return 1

    scope = "staged files" if args.staged else "tracked files"
    print(
        f"Checked {scope}. No file exceeds {MAX_LINES} lines and no function exceeds {MAX_FUNCTION_LINES} lines."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
