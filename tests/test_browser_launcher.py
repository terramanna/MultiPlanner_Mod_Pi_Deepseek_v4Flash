from __future__ import annotations

from pathlib import Path
import sys


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
try:
    from browser_launcher import BrowserLauncher
finally:
    sys.path.pop(0)


def test_edge_uses_isolated_profile_and_bypasses_profile_checks(tmp_path: Path) -> None:
    launches: list[list[str]] = []
    launcher = BrowserLauncher(
        edge_provider=lambda: tmp_path / "msedge.exe",
        data_directory_provider=lambda: tmp_path / "profile",
        popen=lambda command: launches.append(command),
    )

    assert launcher.open("http://127.0.0.1:5173/")
    assert len(launches) == 1
    assert f"--user-data-dir={tmp_path / 'profile'}" in launches[0]
    assert "--no-first-run" in launches[0]
    assert "--no-default-browser-check" in launches[0]
    assert "--app=http://127.0.0.1:5173/" in launches[0]


def test_missing_edge_reports_launch_failure(tmp_path: Path) -> None:
    launcher = BrowserLauncher(
        edge_provider=lambda: None,
        data_directory_provider=lambda: tmp_path / "profile",
        popen=lambda command: None,
    )

    assert launcher.open("http://127.0.0.1:5173/") is False
