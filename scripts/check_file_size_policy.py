"""Reject oversized source files before they become maintenance hazards.

Two refinements over a naive line cap:

- Python functions are measured in *logical* lines: blank lines, comment-only
  lines, and the docstring are excluded, so documenting a function the way the
  engineering rules ask for never pushes it over budget.
- A pre-warning fires in the last ``WARN_RATIO`` band of either budget, so you
  see "approaching budget" while you can still act, not only the post-hoc
  "already over budget" at commit time.
"""

from __future__ import annotations

import ast
import argparse
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath


MAX_LINES = 600
MAX_FUNCTION_LINES = 50
# Warn before the budget is blown, not after. 0.8 => warn across the last 20%.
WARN_RATIO = 0.8
FILE_WARN_LINES = int(MAX_LINES * WARN_RATIO)
FUNCTION_WARN_LINES = int(MAX_FUNCTION_LINES * WARN_RATIO)
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


def python_function_measures(source: str) -> list[tuple[str, int]]:
    """Measure each Python function in logical lines (see module docstring)."""
    lines = source.splitlines()
    measures: list[tuple[str, int]] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end_lineno = getattr(node, "end_lineno", None)
            if end_lineno is not None:
                measures.append((node.name, _python_logical_lines(node, lines, end_lineno)))
    return measures


def _python_logical_lines(node: ast.AST, lines: list[str], end_lineno: int) -> int:
    doc_start, doc_end = _docstring_span(node)
    count = 0
    for lineno in range(node.lineno, end_lineno + 1):
        if doc_start is not None and doc_start <= lineno <= doc_end:
            continue
        stripped = lines[lineno - 1].strip()
        if stripped and not stripped.startswith("#"):
            count += 1
    return count


def _docstring_span(node: ast.AST) -> tuple[int | None, int | None]:
    body = getattr(node, "body", [])
    first = body[0] if body else None
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        return first.lineno, getattr(first, "end_lineno", first.lineno)
    return None, None


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


def js_function_measures(source: str) -> list[tuple[str, int]]:
    """Measure each JS function by raw span (blank/comment stripping is TODO)."""
    return [(name, end - start + 1) for name, start, end in js_function_spans(source)]


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


# Inherently branchy single-pass tokenizer; clearer as one function than split.
def _strip_js_comments_and_strings(line: str, state: dict[str, bool]) -> str:  # noqa: C901
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


def function_findings(path: str, source: str) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """Return (violations, warnings) for the functions in *path*."""
    if path in FUNCTION_LENGTH_EXCLUDED_PATHS:
        return [], []

    suffix = PurePosixPath(path).suffix
    if suffix == ".py":
        measures = python_function_measures(source)
    elif suffix == ".js":
        measures = js_function_measures(source)
    else:
        measures = []

    violations: list[tuple[str, int]] = []
    warnings: list[tuple[str, int]] = []
    for name, count in measures:
        if count > MAX_FUNCTION_LINES:
            violations.append((f"{path}:{name}", count))
        elif count > FUNCTION_WARN_LINES:
            warnings.append((f"{path}:{name}", count))
    return violations, warnings


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged", action="store_true")
    mode.add_argument("--all", action="store_true")
    return parser.parse_args()


def collect(candidates: list[str], staged: bool):
    """Bucket candidates into oversized/near-budget files and functions."""
    oversized: list[tuple[str, int]] = []
    file_warnings: list[tuple[str, int]] = []
    func_violations: list[tuple[str, int]] = []
    func_warnings: list[tuple[str, int]] = []
    for path in candidates:
        if not should_check(path):
            continue
        lines = staged_line_count(path) if staged else working_tree_line_count(path)
        if lines > MAX_LINES:
            oversized.append((path, lines))
        elif lines > FILE_WARN_LINES:
            file_warnings.append((path, lines))
        source = staged_source_text(path) if staged else working_tree_source_text(path)
        violations, warnings = function_findings(path, source)
        func_violations.extend(violations)
        func_warnings.extend(warnings)
    return oversized, file_warnings, func_violations, func_warnings


def _print_block(header: str, rows: list[tuple[str, int]], hint: str) -> None:
    print(header, file=sys.stderr)
    for label, value in rows:
        print(f"  {label}: {value}", file=sys.stderr)
    print(hint, file=sys.stderr)


def main() -> int:
    args = _parse_args()
    candidates = staged_files() if args.staged else tracked_files()
    oversized, file_warnings, func_violations, func_warnings = collect(candidates, args.staged)

    if file_warnings:
        _print_block(
            f"Approaching the {MAX_LINES}-line file budget (warns at {FILE_WARN_LINES}):",
            file_warnings,
            "Plan the split now, before the next edit pushes it over.",
        )
    if func_warnings:
        _print_block(
            f"Approaching the {MAX_FUNCTION_LINES}-line function budget (warns at {FUNCTION_WARN_LINES}):",
            func_warnings,
            "Extract a helper soon to stay under budget.",
        )
    if oversized:
        _print_block(
            f"Source files may not exceed {MAX_LINES} lines:",
            oversized,
            "Split the file or document and approve a narrowly scoped exception.",
        )
    if func_violations:
        _print_block(
            f"Functions may not exceed {MAX_FUNCTION_LINES} lines:",
            func_violations,
            "Extract helpers until each function fits under the limit.",
        )
    if oversized or func_violations:
        return 1

    scope = "staged files" if args.staged else "tracked files"
    summary = f"Checked {scope}. No file exceeds {MAX_LINES} lines and no function exceeds {MAX_FUNCTION_LINES} lines."
    if file_warnings or func_warnings:
        summary += f" ({len(file_warnings) + len(func_warnings)} near budget — see warnings above.)"
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
