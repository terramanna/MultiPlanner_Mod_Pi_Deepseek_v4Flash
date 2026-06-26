from pathlib import Path

from multiplanner_api.downloads import (
    GRD_DRIVER,
    MAPINFO_WGS84_UTM32,
    WGS84_UTM32,
    _export_for_ellipse,
    _export_grd,
    _warp_vrt,
    _write_mapinfo_tab,
)


def test_warp_reprojects_the_ellipse_tiff_to_wgs84_utm32(monkeypatch, tmp_path) -> None:
    command = []

    monkeypatch.setattr(
        "multiplanner_api.downloads.subprocess.run",
        lambda args, check, env: command.extend(args),
    )

    _warp_vrt(Path("gdalwarp.exe"), tmp_path / "dgm1.vrt", tmp_path / "dgm1.tif", {})

    assert command[command.index("-t_srs") + 1] == WGS84_UTM32


def test_grd_translate_uses_createcopy_with_the_northwood_driver(monkeypatch, tmp_path) -> None:
    command = []

    monkeypatch.setattr(
        "multiplanner_api.downloads.subprocess.run",
        lambda args, check, env: command.extend(args),
    )

    from multiplanner_api.downloads import _translate_to_grd

    _translate_to_grd(Path("gdal_translate.exe"), tmp_path / "dgm1.tif", tmp_path / "dgm1.grd", {})

    # NWT_GRD must be built by gdal_translate (CreateCopy) reading the warped
    # GeoTIFF, so the driver derives the real Z min/max instead of garbage defaults.
    assert command[0] == "gdal_translate.exe"
    assert command[command.index("-of") + 1] == GRD_DRIVER
    assert str(tmp_path / "dgm1.tif") in command


def test_grd_elevation_warps_to_geotiff_then_createcopies_to_grd(monkeypatch, tmp_path) -> None:
    calls = []

    monkeypatch.setattr(
        "multiplanner_api.downloads._warp_vrt",
        lambda _gdalwarp, _vrt, tif, _env: calls.append(("warp", Path(tif).suffix)),
    )
    monkeypatch.setattr(
        "multiplanner_api.downloads._translate_to_grd",
        lambda _translate, tif, grd, _env: calls.append(("translate", Path(tif).suffix, Path(grd).suffix)),
    )
    monkeypatch.setattr("multiplanner_api.downloads._write_mapinfo_tab", lambda *_args: None)

    from multiplanner_api.downloads import _export_grd_elevation

    exports = _export_grd_elevation(
        "sel_dgm1_3tiles",
        tmp_path,
        Path("gdalwarp.exe"),
        Path("gdalinfo.exe"),
        {},
        tmp_path / "sel_dgm1_3tiles.vrt",
    )

    # Elevation export must warp to a Float32 GeoTIFF first, then CreateCopy that
    # into NWT_GRD -- never warp straight into the grid (the flat-surface bug).
    assert calls == [("warp", ".tif"), ("translate", ".tif", ".grd")]
    assert any(path.endswith("_utm32.grd") for path in exports)


def test_tab_declares_wgs84_utm32(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "multiplanner_api.downloads.subprocess.run",
        lambda *_args, **_kwargs: type("Result", (), {
            "stdout": '{"size":[2,3],"cornerCoordinates":{"upperLeft":[1,2],"upperRight":[3,2],"lowerRight":[3,0],"lowerLeft":[1,0]}}'
        })(),
    )
    tab_path = tmp_path / "dgm1.TAB"

    _write_mapinfo_tab(Path("gdalinfo.exe"), tmp_path / "dgm1.tif", tab_path, {})

    assert MAPINFO_WGS84_UTM32 in tab_path.read_text(encoding="ascii")


def test_ellipse_export_filename_identifies_selection_dataset_and_tile_count(monkeypatch, tmp_path) -> None:
    gdal_dir = tmp_path / "gdal"
    gdal_dir.mkdir()
    for executable in ("gdalbuildvrt.exe", "gdalwarp.exe", "gdalinfo.exe"):
        (gdal_dir / executable).write_text("", encoding="ascii")

    monkeypatch.setattr("multiplanner_api.downloads._build_vrt", lambda *_args: None)
    monkeypatch.setattr("multiplanner_api.downloads._warp_vrt", lambda *_args: None)
    monkeypatch.setattr("multiplanner_api.downloads._write_mapinfo_tab", lambda *_args: None)

    exports = _export_for_ellipse(
        {"dom1": [tmp_path / "a.tif", tmp_path / "b.tif"]},
        tmp_path / "leaflet_polygon",
        str(gdal_dir),
    )

    assert Path(exports[0]).name == "leaflet_polygon_dom1_2tiles_utm32n_ellipse.tif"
    assert Path(exports[1]).name == "leaflet_polygon_dom1_2tiles_utm32n_ellipse.TAB"


def test_grd_export_writes_a_real_orthophoto_file(monkeypatch, tmp_path) -> None:
    gdal_dir = tmp_path / "gdal"
    gdal_dir.mkdir()
    for executable in ("gdalbuildvrt.exe", "gdalwarp.exe", "gdalinfo.exe"):
        (gdal_dir / executable).write_text("", encoding="ascii")

    monkeypatch.setattr("multiplanner_api.downloads._build_vrt", lambda *_args: None)
    monkeypatch.setattr("multiplanner_api.downloads._warp_vrt", lambda *_args: None)
    monkeypatch.setattr("multiplanner_api.downloads._write_mapinfo_tab", lambda *_args: None)

    exports, warnings = _export_grd(
        {"dop20": [tmp_path / "a.tif"]},
        tmp_path / "selection",
        str(gdal_dir),
    )

    assert not warnings
    assert {Path(path).suffix for path in exports} == {".tif", ".TAB"}
    assert any(Path(path).name.endswith("_utm32.tif") for path in exports)
