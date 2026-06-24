# New-project setup

Before feature work:

1. Select a profile with `scripts/initialize_project.ps1` on Windows or `scripts/initialize_project.py` on Linux/macOS, or explicitly keep the neutral layout for a different technology.
2. Replace `OWNER/REPOSITORY` in `AGENTS.md` and `.github/ISSUE_TEMPLATE/config.yml`.
3. Fill out `CONTEXT.md`, including canonical domain terms and invariants.
4. Replace the placeholder identities in `config/commit-actors.json`.
5. Run `./scripts/install_git_hooks.ps1` on Windows or `./scripts/install_git_hooks.sh` on Linux/macOS in every contributor clone.
6. Review the 1,200-line default in `scripts/check_file_size_policy.py`.
7. Replace `LICENSE`, `SECURITY.md`, and `CODEOWNERS` with project-specific values before publishing.
8. Create a repo-level `.venv` and install backend/frontend dependencies.

Do not delete the audit trail merely because a project begins with one contributor. It is needed as soon as work is delegated or resumed later.

## Commit actor example

The template includes a default `config/commit-actors.json` for your current
workflow. Replace it if the derived repository needs different actors. Current
default:

```json
{
  "actors": {
    "Terra": {
      "git_name": "Terra",
      "git_email": "terramanna@users.noreply.github.com"
    },
    "Brian Codex": {
      "git_name": "Brian Codex",
      "git_email": "brian.codex@terramanna.local"
    },
    "Claude Appleton": {
      "git_name": "Claude Appleton",
      "git_email": "claude.appleton@terramanna.local"
    },
    "Hermes Relay": {
      "git_name": "Hermes Relay",
      "git_email": "hermes.relay@terramanna.local"
    }
  }
}
```

Install hooks only after this file is correct.

## First commit flow

1. Configure Git to match one actor entry:

   ```powershell
   git config user.name "Terra"
   git config user.email "terramanna@users.noreply.github.com"
   ```

2. Make your changes and stage them:

   ```powershell
   git add .
   ```

3. Commit with the matching `Actor:` trailer:

   ```powershell
   git commit -m "chore: initialize project metadata" -m "Actor: Terra"
   ```

If the trailer and Git identity do not match `config/commit-actors.json`, the
commit hook will reject the commit.

## Local developer bootstrap

From the repository root on Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .\apps\api pytest httpx
cd .\apps\web
npm install
cd ..\..
```

Or run:

```powershell
.\scripts\bootstrap_local.ps1
```

The workspace includes `.vscode/settings.json` so VS Code will prefer
`.\.venv\Scripts\python.exe` and auto-activate it in new terminals.
