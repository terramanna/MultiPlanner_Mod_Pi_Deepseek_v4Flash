# Commit audit policy

Every commit must identify the actor in both Git metadata and the message. This makes history attributable even when several people and agents work on the same repository.

The valid actor list lives in `config/commit-actors.json`. Each actor entry must
define:

- The `Actor:` trailer text used in commit messages.
- The `git_name` value required in Git author metadata.
- The `git_email` value required in Git author metadata.

Replace the placeholder values in `config/commit-actors.json` before installing
hooks.

## Install the checks

Run this once in each clone after configuring `config/commit-actors.json`:

```powershell
.\scripts\install_git_hooks.ps1
```

```sh
./scripts/install_git_hooks.sh
```

Then configure your Git identity to match one actor entry:

```powershell
git config user.name "Your Name"
git config user.email "your-github-noreply@example.com"
```

The repository stores the hook path locally; it does not overwrite a different hook path unless `-Force` or `--force` is supplied.

## Commit example

```powershell
git -c user.name="Codex Agent" -c user.email="codex@example.local" commit `
  -m "feat: describe the change" -m "Actor: Codex Agent"
```

The `commit-msg` hook rejects missing, unknown, and mismatched actor identities. Use an `Actor:` trailer on every commit.
