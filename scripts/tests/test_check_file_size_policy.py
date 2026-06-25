"""Unit tests for scripts/check_file_size_policy.py.

The policy script carries the repo's subtlest logic -- a hand-rolled JS
comment/string tokenizer, Python and JS logical-line counters, brace matching,
and warn-band boundaries -- and is the most likely home for silent regressions.
These tests pin the current behavior of each piece and assert that the limits in
the configs and AGENTS.md stay in agreement (the classic drift this repo sees).

Run from the repo root: `pytest -q scripts/tests`.
"""

import re
import tomllib
from pathlib import Path

import check_file_size_policy as p

REPO = Path(__file__).resolve().parents[2]


def strip(line, state=None):
    """Tokenize one JS line, returning (cleaned_code, mutated_state)."""
    state = state if state is not None else p._fresh_js_state()
    return p._strip_js_comments_and_strings(line, state), state


def join(*lines):
    return "\n".join(lines)


# --------------------------------------------------------------------------
# should_check: which paths the policy inspects
# --------------------------------------------------------------------------

def test_should_check_accepts_source_suffixes():
    assert p.should_check("a.js")
    assert p.should_check("a.py")
    assert p.should_check("a.ps1")


def test_should_check_rejects_excluded_suffixes_and_names():
    assert not p.should_check("a.min.js")
    assert not p.should_check("a.map")
    assert not p.should_check("deps.lock")
    assert not p.should_check("package-lock.json")
    assert not p.should_check("npm-shrinkwrap.json")


def test_should_check_rejects_excluded_path_parts_and_non_source():
    assert not p.should_check("node_modules/x/a.js")
    assert not p.should_check("vendor/a.py")
    assert not p.should_check("dist/a.js")
    assert not p.should_check("build/a.js")
    assert not p.should_check("README.md")


def test_should_check_includes_the_policy_script_itself():
    # The script is excluded from the *function*-length rule (below), but is
    # still size-checked as a file -- these two exclusions must not be confused.
    assert p.should_check("scripts/check_file_size_policy.py")


# --------------------------------------------------------------------------
# Python logical-line counting
# --------------------------------------------------------------------------

def test_python_single_line_docstring_excluded():
    src = join("def f():", '    """doc."""', "    x = 1", "    return x")
    assert p.python_function_measures(src) == [("f", 3)]


def test_python_multi_line_docstring_excluded():
    src = join("def f():", '    """l1', "    l2", '    """', "    return 1")
    assert p.python_function_measures(src) == [("f", 2)]


def test_python_blank_and_comment_lines_excluded():
    src = join("def f():", "    # c", "", "    x = 1", "    return x")
    assert p.python_function_measures(src) == [("f", 3)]


def test_python_non_docstring_string_statement_counts():
    # Only the *first* body statement can be a docstring; a later bare string
    # literal is an ordinary statement and counts.
    src = join("def f():", "    x = 1", '    "literal"', "    return x")
    assert p.python_function_measures(src) == [("f", 4)]


def test_python_nested_functions_counted_separately():
    src = join("def outer():", "    def inner():", "        return 1", "    return inner")
    assert dict(p.python_function_measures(src)) == {"outer": 4, "inner": 2}


def test_python_async_function_counted():
    src = join("async def f():", "    await g()")
    assert p.python_function_measures(src) == [("f", 2)]


def test_python_decorator_line_excluded():
    # FunctionDef.lineno points at `def`, so the decorator line is not counted.
    src = join("@deco", "def f():", "    return 1")
    assert p.python_function_measures(src) == [("f", 2)]


# --------------------------------------------------------------------------
# JS tokenizer: _strip_js_comments_and_strings
# --------------------------------------------------------------------------

def test_js_string_escape_swallows_inner_quote():
    cleaned, _ = strip('a = "x\\"y" + z')
    assert "z" in cleaned and '"' not in cleaned and "x" not in cleaned


def test_js_double_slash_inside_string_is_not_a_comment():
    cleaned, _ = strip('u = "a//b" + c')
    assert "c" in cleaned and "//" not in cleaned


def test_js_real_line_comment_drops_the_rest():
    cleaned, _ = strip("code = 1 // note")
    assert "code = 1" in cleaned and "note" not in cleaned


def test_js_block_comment_spans_lines():
    state = p._fresh_js_state()
    first = p._strip_js_comments_and_strings("code /* start", state)
    assert "code" in first and "start" not in first
    assert state["block_comment"] is True
    second = p._strip_js_comments_and_strings("mid */ tail", state)
    assert "tail" in second and "mid" not in second
    assert state["block_comment"] is False


def test_js_template_interior_including_interpolation_stripped():
    cleaned, _ = strip("s = `a${x}b`;")
    assert "s =" in cleaned and "x" not in cleaned and "`" not in cleaned


def test_js_trailing_backslash_continues_string_but_resets_escape():
    # A line-continuation backslash keeps the string open into the next line;
    # the per-line escape flag is always reset so it never leaks across lines.
    _, state = strip('s = "ab\\')
    assert state["double"] is True
    assert state["escape"] is False


# --------------------------------------------------------------------------
# JS function span detection
# --------------------------------------------------------------------------

def test_js_span_function_declaration():
    src = join("function foo() {", "  return 1;", "}")
    assert p.js_function_spans(src) == [("foo", 1, 3)]


def test_js_span_function_expression():
    src = join("const bar = function() {", "  return 2;", "};")
    assert p.js_function_spans(src) == [("bar", 1, 3)]


def test_js_span_arrow_with_param_list():
    src = join("const baz = (a, b) => {", "  return a + b;", "};")
    assert p.js_function_spans(src) == [("baz", 1, 3)]


def test_js_span_arrow_single_param_and_async():
    src = join("const af = async () => {", "  return 1;", "};")
    assert p.js_function_spans(src) == [("af", 1, 3)]


def test_js_span_counts_nested_braces():
    src = join("function outer() {", "  if (x) {", "    y();", "  }", "  return 1;", "}")
    assert p.js_function_spans(src) == [("outer", 1, 6)]


def test_js_span_ignores_brace_inside_string():
    src = join("function s() {", '  const a = "}";', "  return a;", "}")
    assert p.js_function_spans(src) == [("s", 1, 4)]


def test_js_span_unclosed_function_is_skipped():
    src = join("function broken() {", "  return 1;")
    assert p.js_function_spans(src) == []


def test_js_span_no_false_positive_on_plain_assignment():
    assert p.js_function_spans("const x = 1;") == []


# --------------------------------------------------------------------------
# JS logical-line counting (the newest, previously hand-checked code)
# --------------------------------------------------------------------------

def test_js_logical_excludes_blank_and_comment_lines():
    src = join("function f() {", "  // comment", "  const x = 1;", "", "  return x;", "}")
    assert p.js_function_measures(src) == [("f", 4)]


def test_js_logical_inline_comment_line_still_counts():
    src = join("function h() {", "  return 1; // trailing", "}")
    assert p.js_function_measures(src) == [("h", 3)]


def test_js_logical_multiline_template_interior_excluded():
    # Opening line (has code before the backtick) and the closing line (has `;`)
    # count; the two interior template lines do not.
    src = join("function g() {", "  const s = `", "    multi", "    line", "  `;", "  return s;", "}")
    assert p.js_function_measures(src) == [("g", 5)]


def test_js_logical_brace_in_string_does_not_shorten_span():
    src = join("function s() {", '  const a = "}";', "  return a;", "}")
    assert p.js_function_measures(src) == [("s", 4)]


# --------------------------------------------------------------------------
# function_findings: 50 / 40 boundaries
# --------------------------------------------------------------------------

def make_py_func(total_logical):
    """A Python function whose body brings it to exactly total_logical lines."""
    stmts = "\n".join(f"    a{i} = {i}" for i in range(total_logical - 1))
    return f"def f():\n{stmts}\n"


def test_function_violation_at_51():
    violations, warnings = p.function_findings("x.py", make_py_func(51))
    assert violations == [("x.py:f", 51)]
    assert warnings == []


def test_function_warning_at_50():
    violations, warnings = p.function_findings("x.py", make_py_func(50))
    assert violations == []
    assert warnings == [("x.py:f", 50)]


def test_function_warning_at_41():
    violations, warnings = p.function_findings("x.py", make_py_func(41))
    assert warnings == [("x.py:f", 41)]


def test_function_clean_at_40():
    violations, warnings = p.function_findings("x.py", make_py_func(40))
    assert violations == [] and warnings == []


def test_function_findings_skips_excluded_path():
    assert p.function_findings("scripts/check_file_size_policy.py", make_py_func(80)) == ([], [])


# --------------------------------------------------------------------------
# collect: 600 / 480 file boundaries (IO mocked)
# --------------------------------------------------------------------------

def test_collect_file_thresholds(monkeypatch):
    counts = {"over.py": 601, "exact.py": 600, "warn.py": 481, "edge.py": 480, "ok.py": 10}
    monkeypatch.setattr(p, "working_tree_line_count", lambda path: counts[path])
    monkeypatch.setattr(p, "working_tree_source_text", lambda path: "")
    oversized, file_warnings, func_violations, func_warnings = p.collect(list(counts), staged=False)
    assert oversized == [("over.py", 601)]
    assert sorted(file_warnings) == [("exact.py", 600), ("warn.py", 481)]
    assert func_violations == [] and func_warnings == []


# --------------------------------------------------------------------------
# Anti-drift: configs and docs must agree on the limits
# --------------------------------------------------------------------------

def read(rel):
    return (REPO / rel).read_text(encoding="utf-8")


def test_complexity_threshold_agrees_across_configs():
    ruff_cx = tomllib.loads(read("ruff.toml"))["lint"]["mccabe"]["max-complexity"]
    eslint = re.search(r'complexity:\s*\[\s*"error"\s*,\s*(\d+)\s*\]', read("apps/web/eslint.config.js"))
    doc = re.search(r"cyclomatic complexity (\d+)", read("AGENTS.md"))
    assert eslint and doc, "complexity threshold not found in a config/doc"
    assert ruff_cx == int(eslint.group(1)) == int(doc.group(1)) == 10


def test_line_limits_agree_with_docs():
    agents = read("AGENTS.md")
    file_max = int(re.search(r"No source file may exceed (\d+) lines", agents).group(1))
    func_max = int(re.search(r"No function may exceed (\d+) lines", agents).group(1))
    warn = re.search(r"\((\d+) lines\s*/\s*(\d+)\s+function lines\)", agents)
    assert file_max == p.MAX_LINES == 600
    assert func_max == p.MAX_FUNCTION_LINES == 50
    assert int(warn.group(1)) == p.FILE_WARN_LINES == 480
    assert int(warn.group(2)) == p.FUNCTION_WARN_LINES == 40
