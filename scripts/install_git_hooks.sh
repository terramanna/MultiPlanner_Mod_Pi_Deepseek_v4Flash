#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

existing=$(git config --get core.hooksPath || true)
if [ -n "${existing}" ] && [ "${existing}" != ".githooks" ] && [ "${1:-}" != "--force" ]; then
  echo "Refusing to overwrite existing core.hooksPath '${existing}'. Re-run with --force to use .githooks." >&2
  exit 1
fi

git config core.hooksPath .githooks
echo "Configured git hooksPath -> .githooks"
