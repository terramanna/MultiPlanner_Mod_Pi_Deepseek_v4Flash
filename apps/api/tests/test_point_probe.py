import subprocess
from pathlib import Path
from types import SimpleNamespace

from multiplanner_api import point_probe


def test_sample_height_calls_gdallocationinfo(monkeypatch, tmp_path):
    sample_path = tmp_path / "dgm1_tile.tif"
    sample_path.touch()
    calls = []

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        return SimpleNamespace(stdout="123.45\n")

    monkeypatch.setattr(point_probe.subprocess, "run", fake_run)
    monkeypatch.setattr(point_probe, "_gdal_exe", lambda name: Path(f"/fake/{name}.exe"))

    height = point_probe._sample_height(sample_path, 11.5, 48.1)

    assert height == 123.45
    assert calls[0][1] == "-wgs84"
    assert calls[0][2] == "-valonly"


def test_sample_height_raises_on_empty_output(monkeypatch, tmp_path):
    sample_path = tmp_path / "dgm1_tile.tif"
    sample_path.touch()
    monkeypatch.setattr(point_probe.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout="  "))
    monkeypatch.setattr(point_probe, "_gdal_exe", lambda name: Path(f"/fake/{name}.exe"))

    try:
        point_probe._sample_height(sample_path, 11.5, 48.1)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "No data value" in str(exc)
