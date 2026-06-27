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


def test_resolve_sample_path_prefers_tif(tmp_path):
    tif = tmp_path / "tile.tif"
    tif.touch()
    xyz = tmp_path / "tile.xyz"
    xyz.touch()
    result = point_probe._resolve_sample_path([xyz, tif], "lgv-hh")
    assert result == tif.resolve()


def test_resolve_sample_path_converts_xyz_for_known_provider(monkeypatch, tmp_path):
    xyz = tmp_path / "tile.xyz"
    xyz.touch()
    converted = tmp_path / "tile.tif"
    monkeypatch.setattr(point_probe, "_xyz_to_geotiff", lambda path, crs: converted)
    result = point_probe._resolve_sample_path([xyz], "lgv-hh")
    assert result == converted.resolve()


def test_resolve_sample_path_raises_for_xyz_unknown_provider(tmp_path):
    xyz = tmp_path / "tile.xyz"
    xyz.touch()
    try:
        point_probe._resolve_sample_path([xyz], "some-unknown-provider")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "no usable" in str(exc).lower()


def test_xyz_to_geotiff_skips_if_already_exists(monkeypatch, tmp_path):
    xyz = tmp_path / "tile.xyz"
    xyz.touch()
    tif = tmp_path / "tile.tif"
    tif.touch()
    calls = []
    monkeypatch.setattr(point_probe.subprocess, "run", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(point_probe, "_gdal_exe", lambda name: Path(f"/fake/{name}.exe"))
    result = point_probe._xyz_to_geotiff(xyz, "EPSG:25832")
    assert result == tif
    assert calls == []


def test_xyz_to_geotiff_calls_gdal_translate(monkeypatch, tmp_path):
    xyz = tmp_path / "tile.xyz"
    xyz.touch()
    calls = []

    def fake_run(cmd, **_kwargs):
        calls.append(cmd)
        (tmp_path / "tile.tif").touch()

    monkeypatch.setattr(point_probe.subprocess, "run", fake_run)
    monkeypatch.setattr(point_probe, "_gdal_exe", lambda name: Path(f"/fake/{name}.exe"))
    result = point_probe._xyz_to_geotiff(xyz, "EPSG:25832")
    assert result == tmp_path / "tile.tif"
    assert "-a_srs" in calls[0]
    assert "EPSG:25832" in calls[0]


def test_provider_xyz_crs_covers_known_xyz_providers():
    for provider in ("lgv-hh", "lginf-hb", "gdi-be"):
        assert provider in point_probe._PROVIDER_XYZ_CRS


def test_hh_crs_is_utm32():
    assert point_probe._PROVIDER_XYZ_CRS["lgv-hh"] == "EPSG:25832"


def test_be_crs_is_utm33():
    assert point_probe._PROVIDER_XYZ_CRS["gdi-be"] == "EPSG:25833"
