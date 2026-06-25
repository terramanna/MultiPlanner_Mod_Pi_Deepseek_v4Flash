param(
    [Parameter(Mandatory)]
    [ValidateSet("python-cli", "node-cli", "docs-only")]
    [string]$Profile
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$projectName = (Split-Path -Leaf $repoRoot).ToLowerInvariant() -replace "[^a-z0-9]+", "-"
$projectName = $projectName.Trim("-")

function Ensure-Directory([string]$RelativePath) {
    New-Item -ItemType Directory -Force -Path (Join-Path $repoRoot $RelativePath) | Out-Null
}

function Write-NewFile([string]$RelativePath, [string]$Content) {
    $path = Join-Path $repoRoot $RelativePath
    if (Test-Path -LiteralPath $path) {
        throw "Refusing to overwrite existing file: $RelativePath"
    }
    Set-Content -LiteralPath $path -Value $Content -NoNewline
}

"src", "tests", "config", "data", "assets", "examples", "docs/adr", ".agents" | ForEach-Object { Ensure-Directory $_ }

$pitfallsContent = @"
# Pitfalls

Append-only log of skill-specific regressions and anti-patterns.

Rules:
- do not delete past entries
- do not rewrite history to make entries look cleaner
- append a new entry when a skill causes a regression, forces a redo, or contaminates another workflow

Entry shape:

```markdown
## 2026-01-01 - <skill-name>

- Do not <action> because it regressed <symptom>.
- Do not <action> because it forced a redo of <work>.
- Cross-contamination note: <what leaked into where>.
- Recovery: <what had to be redone>.
```
"@

Write-NewFile ".agents/pitfalls.md" $pitfallsContent

switch ($Profile) {
    "python-cli" {
        $packageName = $projectName.Replace("-", "_")
        Ensure-Directory "src/$packageName"
        Write-NewFile "pyproject.toml" @"
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "$projectName"
version = "0.1.0"
description = "Describe the project purpose here."
readme = "README.md"
requires-python = ">=3.11"

[project.optional-dependencies]
dev = ["pytest>=8.0"]
"@
        Write-NewFile "src/$packageName/__init__.py" ""
        Write-NewFile "src/$packageName/__main__.py" "def main() -> None:`n    print('Replace this entrypoint with real behavior.')`n`n`nif __name__ == '__main__':`n    main()`n"
        Write-NewFile "tests/test_smoke.py" "def test_smoke() -> None:`n    assert True`n"
    }
    "node-cli" {
        Write-NewFile "package.json" @"
{
  "name": "$projectName",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "start": "node src/index.js",
    "test": "node --test"
  }
}
"@
        Write-NewFile "src/index.js" "console.log('Replace this entrypoint with real behavior.');`n"
        Write-NewFile "tests/smoke.test.js" "import test from 'node:test';`nimport assert from 'node:assert/strict';`n`ntest('smoke', () => {`n  assert.equal(1, 1);`n});`n"
    }
    "docs-only" {
        Write-NewFile "docs/adr/README.md" "# Architecture decision records`n`nRecord decisions that are costly to rediscover.`n"
    }
}

Write-Host "Applied $Profile scaffold for $projectName." -ForegroundColor Green
