"""Cross-platform scaffold initializer for template-derived repositories."""

from __future__ import annotations

import argparse
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def slugify(name: str) -> str:
    pieces: list[str] = []
    dash_open = False
    for char in name.lower():
        if char.isalnum():
            pieces.append(char)
            dash_open = False
        elif not dash_open:
            pieces.append("-")
            dash_open = True
    return "".join(pieces).strip("-")


def ensure_directory(relative_path: str) -> None:
    (REPO_ROOT / relative_path).mkdir(parents=True, exist_ok=True)


def write_new_file(relative_path: str, content: str) -> None:
    path = REPO_ROOT / relative_path
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing file: {relative_path}")
    path.write_text(content, encoding="utf-8")


def init_python_cli(project_name: str) -> None:
    package_name = project_name.replace("-", "_")
    ensure_directory(f"src/{package_name}")
    write_new_file(
        "pyproject.toml",
        "\n".join(
            [
                "[build-system]",
                'requires = ["setuptools>=68"]',
                'build-backend = "setuptools.build_meta"',
                "",
                "[project]",
                f'name = "{project_name}"',
                'version = "0.1.0"',
                'description = "Describe the project purpose here."',
                'readme = "README.md"',
                'requires-python = ">=3.11"',
                "",
                "[project.optional-dependencies]",
                'dev = ["pytest>=8.0"]',
                "",
            ]
        ),
    )
    write_new_file(REPO_ROOT.joinpath(f"src/{package_name}/__init__.py").relative_to(REPO_ROOT).as_posix(), "")
    write_new_file(
        REPO_ROOT.joinpath(f"src/{package_name}/__main__.py").relative_to(REPO_ROOT).as_posix(),
        "def main() -> None:\n    print('Replace this entrypoint with real behavior.')\n\n\nif __name__ == '__main__':\n    main()\n",
    )
    write_new_file(
        "tests/test_smoke.py",
        "def test_smoke() -> None:\n    assert True\n",
    )


def init_node_cli(project_name: str) -> None:
    write_new_file(
        "package.json",
        "\n".join(
            [
                "{",
                f'  "name": "{project_name}",',
                '  "version": "0.1.0",',
                '  "private": true,',
                '  "type": "module",',
                '  "scripts": {',
                '    "start": "node src/index.js",',
                '    "test": "node --test"',
                "  }",
                "}",
                "",
            ]
        ),
    )
    write_new_file("src/index.js", "console.log('Replace this entrypoint with real behavior.');\n")
    write_new_file("tests/smoke.test.js", "import test from 'node:test';\nimport assert from 'node:assert/strict';\n\ntest('smoke', () => {\n  assert.equal(1, 1);\n});\n")


def init_docs_only() -> None:
    write_new_file(
        "docs/adr/README.md",
        "# Architecture decision records\n\nRecord decisions that are costly to rediscover.\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", choices=["python-cli", "node-cli", "docs-only"])
    args = parser.parse_args()

    project_name = slugify(REPO_ROOT.name)
    for path in ["src", "tests", "config", "data", "assets", "examples", "docs/adr"]:
        ensure_directory(path)

    if args.profile == "python-cli":
        init_python_cli(project_name)
    elif args.profile == "node-cli":
        init_node_cli(project_name)
    else:
        init_docs_only()

    print(f"Applied {args.profile} scaffold for {project_name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
