from __future__ import annotations

import os
from pathlib import Path


def evict_lru(cache_dir: Path, max_bytes: int) -> None:
    """Delete oldest-written files from cache_dir until total size <= max_bytes.

    Uses mtime as the eviction key (oldest first). No-op when max_bytes <= 0
    (eviction disabled) or the directory does not exist. OSError on individual
    file deletions is silently ignored so a locked file never aborts the pass.
    """
    if max_bytes <= 0 or not cache_dir.exists():
        return
    files = _collect_files(cache_dir)
    total = sum(size for _, size, _ in files)
    if total <= max_bytes:
        return
    for _, size, path in sorted(files):
        if total <= max_bytes:
            break
        try:
            path.unlink(missing_ok=True)
            total -= size
        except OSError:
            pass


def _collect_files(cache_dir: Path) -> list[tuple[float, int, Path]]:
    """Return (mtime, size_bytes, path) for every file under cache_dir."""
    result: list[tuple[float, int, Path]] = []
    stack = [cache_dir]
    while stack:
        current = stack.pop()
        try:
            for entry in os.scandir(current):
                if entry.is_dir(follow_symlinks=False):
                    stack.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    stat = entry.stat()
                    result.append((stat.st_mtime, stat.st_size, Path(entry.path)))
        except OSError:
            pass
    return result
