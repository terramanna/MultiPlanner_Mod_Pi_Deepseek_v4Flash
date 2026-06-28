import time
from pathlib import Path

import pytest

from multiplanner_api.cache_eviction import _collect_files, evict_lru


def _write(path: Path, size: int, mtime: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    import os
    os.utime(path, (mtime, mtime))
    return path


def test_no_op_when_under_limit(tmp_path):
    _write(tmp_path / "a.tif", 100, 1000.0)
    _write(tmp_path / "b.tif", 100, 2000.0)
    evict_lru(tmp_path, max_bytes=500)
    assert (tmp_path / "a.tif").exists()
    assert (tmp_path / "b.tif").exists()


def test_evicts_oldest_first(tmp_path):
    _write(tmp_path / "old.tif", 100, 1000.0)
    _write(tmp_path / "mid.tif", 100, 2000.0)
    _write(tmp_path / "new.tif", 100, 3000.0)
    evict_lru(tmp_path, max_bytes=150)
    assert not (tmp_path / "old.tif").exists()
    assert not (tmp_path / "mid.tif").exists()
    assert (tmp_path / "new.tif").exists()


def test_stops_as_soon_as_under_limit(tmp_path):
    _write(tmp_path / "old.tif", 100, 1000.0)
    _write(tmp_path / "new.tif", 100, 2000.0)
    evict_lru(tmp_path, max_bytes=100)
    assert not (tmp_path / "old.tif").exists()
    assert (tmp_path / "new.tif").exists()


def test_disabled_when_max_bytes_zero(tmp_path):
    _write(tmp_path / "a.tif", 100, 1000.0)
    evict_lru(tmp_path, max_bytes=0)
    assert (tmp_path / "a.tif").exists()


def test_disabled_when_max_bytes_negative(tmp_path):
    _write(tmp_path / "a.tif", 100, 1000.0)
    evict_lru(tmp_path, max_bytes=-1)
    assert (tmp_path / "a.tif").exists()


def test_no_op_when_dir_missing(tmp_path):
    evict_lru(tmp_path / "nonexistent", max_bytes=1)


def test_collects_nested_files(tmp_path):
    _write(tmp_path / "a" / "b" / "file1.tif", 10, 1000.0)
    _write(tmp_path / "a" / "file2.tif", 20, 2000.0)
    _write(tmp_path / "file3.tif", 30, 3000.0)
    files = _collect_files(tmp_path)
    assert len(files) == 3
    total = sum(size for _, size, _ in files)
    assert total == 60


def test_evicts_across_subdirectories(tmp_path):
    _write(tmp_path / "provider" / "dgm1" / "old.tif", 200, 1000.0)
    _write(tmp_path / "provider" / "dom1" / "new.tif", 200, 2000.0)
    evict_lru(tmp_path, max_bytes=200)
    assert not (tmp_path / "provider" / "dgm1" / "old.tif").exists()
    assert (tmp_path / "provider" / "dom1" / "new.tif").exists()
