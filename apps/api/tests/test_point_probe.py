import subprocess
from pathlib import Path
from types import SimpleNamespace

from multiplanner_api import point_probe
from multiplanner_api.models import MultiProbeRequest, PointProbeResponse


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


def test_resolve_sample_path_prefers_bw_child_tif_covering_point(tmp_path):
    wrong = tmp_path / "dgm1_32_476_5290_1_bw_2020.tif"
    right = tmp_path / "dgm1_32_475_5291_1_bw_2020.tif"
    wrong.touch()
    right.touch()

    result = point_probe._resolve_sample_path(
        [wrong, right],
        "lgl-bw",
        lon=8.676077,
        lat=47.778819,
    )

    assert result == right.resolve()


def test_resolve_sample_path_converts_xyz_for_known_provider(monkeypatch, tmp_path):
    xyz = tmp_path / "tile.xyz"
    xyz.touch()
    converted = tmp_path / "tile.tif"
    monkeypatch.setattr(point_probe, "_xyz_to_geotiff", lambda path, crs: converted)
    result = point_probe._resolve_sample_path([xyz], "lgv-hh")
    assert result == converted.resolve()


def test_resolve_sample_path_converts_bw_child_xyz_covering_point(monkeypatch, tmp_path):
    wrong = tmp_path / "dgm1_32_476_5290_1_bw_2020.xyz"
    right = tmp_path / "dgm1_32_475_5291_1_bw_2020.xyz"
    wrong.touch()
    right.touch()
    chosen = []

    def fake_convert(path, _crs):
        chosen.append(path)
        return path.with_suffix(".tif")

    monkeypatch.setattr(point_probe, "_xyz_to_geotiff", fake_convert)
    result = point_probe._resolve_sample_path(
        [wrong, right],
        "lgl-bw",
        lon=8.676077,
        lat=47.778819,
    )

    assert chosen == [right]
    assert result == right.with_suffix(".tif").resolve()


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
    for provider in ("lgl-bw", "lgv-hh", "lginf-hb", "gdi-be"):
        assert provider in point_probe._PROVIDER_XYZ_CRS


def test_bw_crs_is_utm32():
    assert point_probe._PROVIDER_XYZ_CRS["lgl-bw"] == "EPSG:25832"


def test_hh_crs_is_utm32():
    assert point_probe._PROVIDER_XYZ_CRS["lgv-hh"] == "EPSG:25832"


def test_be_crs_is_utm33():
    assert point_probe._PROVIDER_XYZ_CRS["gdi-be"] == "EPSG:25833"


def test_elevation_api_registered_for_bb_and_be():
    assert "geobasis-bb" in point_probe._ELEVATION_API
    assert "gdi-be" in point_probe._ELEVATION_API
    for url, crs in point_probe._ELEVATION_API.values():
        assert url.startswith("https://")
        assert crs.startswith("EPSG:")


def test_probe_elevation_api_calls_correct_url(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        return SimpleNamespace(text="35.29", raise_for_status=lambda: None)

    monkeypatch.setattr(point_probe, "get_with_ssl_fallback", fake_get)
    result = point_probe._probe_elevation_api(
        "https://isk.geobasis-bb.de/elevation/latlon/point", "EPSG:25833", 13.0622, 52.3906
    )
    assert abs(result - 35.29) < 0.01
    assert "coordinates" in captured["params"]
    # coordinate string should contain UTM33 easting (~369000) and northing (~5806000)
    coords = captured["params"]["coordinates"]
    east, north = (float(v) for v in coords.split(","))
    assert 368_000 < east < 370_000
    assert 5_805_000 < north < 5_807_000


def test_probe_elevation_api_raises_on_empty_response(monkeypatch):
    monkeypatch.setattr(
        point_probe, "get_with_ssl_fallback",
        lambda *a, **k: SimpleNamespace(text="  ", raise_for_status=lambda: None),
    )
    try:
        point_probe._probe_elevation_api(
            "https://isk.geobasis-bb.de/elevation/latlon/point", "EPSG:25833", 13.0622, 52.3906
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "empty response" in str(exc)


def test_elevation_api_for_point_returns_api_for_bb_coord():
    # 52.20, 12.96 is inside BB bbox (11.26–14.76, 51.36–53.56)
    result = point_probe._elevation_api_for_point(12.963, 52.197)
    assert result is not None
    api_url, crs = result
    assert "isk.geobasis-bb.de" in api_url
    assert crs == "EPSG:25833"


def test_elevation_api_for_point_returns_none_outside_coverage():
    # Munich (11.58, 48.14) is not within BB or BE bbox
    result = point_probe._elevation_api_for_point(11.58, 48.14)
    assert result is None


def test_auto_dgm1_probe_uses_elevation_api_for_bb_point(monkeypatch):
    """Auto probe at a BB coordinate should hit the elevation API, not WCS tile download."""
    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        return SimpleNamespace(text="42.5", raise_for_status=lambda: None)

    monkeypatch.setattr(point_probe, "get_with_ssl_fallback", fake_get)
    from multiplanner_api.models import PointProbeRequest
    req = PointProbeRequest(provider="auto", dataset="dgm1", lon=12.963, lat=52.197)
    result = point_probe.probe_point(req)
    assert abs(result.height_m - 42.5) < 0.01
    assert "isk.geobasis-bb.de" in captured["url"]


def test_multi_auto_probe_reports_rp_dom_as_unsupported_after_dgm_success(monkeypatch):
    calls = []

    def fake_probe(request):
        calls.append((request.provider, request.dataset))
        return PointProbeResponse(
            provider="lvermgeo-rp",
            dataset="dgm1",
            lon=request.lon,
            lat=request.lat,
            height_m=283.67,
            tile_id="dgm1_32_422_5463_1_rp_2022",
            sampled_path="tile.tif",
        )

    monkeypatch.setattr(point_probe, "probe_point", fake_probe)

    result = point_probe.probe_point_multi(
        MultiProbeRequest(provider="auto", lon=7.939253, lat=49.320367)
    )

    assert result.provider == "lvermgeo-rp"
    assert result.dgm_m == 283.67
    assert result.dom_m is None
    assert result.dom_error == "lvermgeo-rp does not support dom1 point probing."
    assert calls == [("auto", "dgm1")]
