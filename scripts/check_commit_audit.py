"""Validate commit audit trailers against tracked actor configuration."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
ACTOR_CONFIG_PATH = REPO_ROOT / "config" / "commit-actors.json"


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def read_actor_config() -> dict[str, dict[str, str]]:
    if not ACTOR_CONFIG_PATH.exists():
        raise SystemExit(
            fail(
                "Commit audit is not configured. Update config/commit-actors.json "
                "before installing hooks."
            )
        )

    data = json.loads(ACTOR_CONFIG_PATH.read_text(encoding="utf-8"))
    actors = data.get("actors")
    if not isinstance(actors, dict) or not actors:
        raise SystemExit(
            fail("config/commit-actors.json must define a non-empty 'actors' object.")
        )

    validated: dict[str, dict[str, str]] = {}
    for actor, identity in actors.items():
        if not isinstance(identity, dict):
            raise SystemExit(fail(f"Actor '{actor}' must map to an object."))
        name = identity.get("git_name")
        email = identity.get("git_email")
        if not name or not email:
            raise SystemExit(
                fail(
                    f"Actor '{actor}' must include both 'git_name' and 'git_email' in "
                    "config/commit-actors.json."
                )
            )
        validated[actor] = {"git_name": str(name), "git_email": str(email)}

    return validated


def read_actor_trailer(message_file: Path) -> str:
    actor = ""
    for line in message_file.read_text(encoding="utf-8").splitlines():
        if line.startswith("Actor: "):
            actor = line[len("Actor: ") :].strip()
    if not actor:
        raise SystemExit(
            fail("Commit rejected: add an Actor: trailer (docs/COMMIT_AUDIT.md).")
        )
    return actor


def git_author_ident() -> str:
    result = subprocess.run(
        ["git", "var", "GIT_AUTHOR_IDENT"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        return fail("Usage: check_commit_audit.py <commit-message-file>")

    actors = read_actor_config()
    actor = read_actor_trailer(Path(argv[1]))
    if actor not in actors:
        valid = ", ".join(sorted(actors))
        return fail(
            f"Commit rejected: unknown Actor '{actor}'. Valid actors: {valid}."
        )

    author = git_author_ident()
    expected = actors[actor]
    expected_fragment = f"{expected['git_name']} <{expected['git_email']}>"
    if expected_fragment not in author:
        return fail(
            f"Commit rejected: Actor '{actor}' expects '{expected_fragment}' but "
            f"git author is '{author}'."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
