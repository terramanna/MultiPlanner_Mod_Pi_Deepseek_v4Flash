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


def test_grd_warp_uses_the_northwood_numeric_grid_driver(monkeypatch, tmp_path) -> None:
    command = []

    monkeypatch.setattr(
        "multiplanner_api.downloads.subprocess.run",
        lambda args, check, env: command.extend(args),
    )

    from multiplanner_api.downloads import _warp_to_grd

    _warp_to_grd(Path("gdalwarp.exe"), tmp_path / "dgm1.vrt", tmp_path / "dgm1.grd", {})

    assert command[command.index("-of") + 1] == GRD_DRIVER


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
