"""Launch MultiPlanner in an Edge profile isolated from the user's profiles."""

from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any


_EDGE_FLAGS = (
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-default-apps",
    "--disable-extensions",
    "--disable-sync",
)


def edge_executable() -> Path | None:
    """Find Edge in its standard Windows installation directories."""
    candidates = (
        Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
    )
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def browser_data_directory() -> Path:
    """Keep MultiPlanner separate from signed-in Edge profiles."""
    root = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()))
    return root / "MultiPlanner" / "browser_profile_v1"


class BrowserLauncher:
    """Open the local app without invoking Edge's profile chooser."""

    def __init__(
        self,
        *,
        edge_provider: Callable[[], Path | None] = edge_executable,
        data_directory_provider: Callable[[], Path] = browser_data_directory,
        popen: Callable[[list[str]], Any] = subprocess.Popen,
    ) -> None:
        self._edge_provider = edge_provider
        self._data_directory_provider = data_directory_provider
        self._popen = popen

    def open(self, url: str) -> bool:
        executable = self._edge_provider()
        if executable is None:
            return False
        data_directory = self._data_directory_provider()
        data_directory.mkdir(parents=True, exist_ok=True)
        command = [
            str(executable),
            f"--user-data-dir={data_directory}",
            *_EDGE_FLAGS,
            "--new-window",
            "--window-size=1600,900",
            f"--app={url}",
        ]
        try:
            self._popen(command)
        except OSError:
            return False
        return True


DEFAULT_BROWSER_LAUNCHER = BrowserLauncher()


def launch_multiplanner_browser(url: str = "http://127.0.0.1:5173/") -> bool:
    return DEFAULT_BROWSER_LAUNCHER.open(url)
