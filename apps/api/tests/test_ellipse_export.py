from pathlib import Path
import zipfile

import pytest

from multiplanner_api.downloads import (
    _expanded_download_paths,
    _extract_supported_sources,
)
from multiplanner_api.ellipse_exports import (
    GRD_DRIVER,
    MAPINFO_WGS84_UTM32,
    WGS84_UTM32,
    _export_for_ellipse,
    _export_grd,
    _export_grd_elevation,
    _prepare_export_source,
    _translate_to_grd,
    _warp_vrt,
    _write_mapinfo_tab,
)


def test_sh_downloaded_ascii_source_uses_utm32_crs(monkeypatch, tmp_path) -> None:
    source = tmp_path / "sh_dgm1_325935953.xyz"
    source.write_text("593000 5953000 75\n", encoding="ascii")
    commands = []

    def fake_run_gdal(command, _environment):
        commands.append(command)
        Path(command[-1]).write_bytes(b"tif")

    monkeypatch.setattr("multiplanner_api.ellipse_exports._run_gdal", fake_run_gdal)
    _prepare_export_source(source, tmp_path / "gdal_translate.exe", {})

    assert commands[0][commands[0].index("-a_srs") + 1] == "EPSG:25832"


def test_warp_reprojects_the_ellipse_tiff_to_wgs84_utm32(monkeypatch, tmp_path) -> None:
    command = []

    monkeypatch.setattr(
        "multiplanner_api.ellipse_exports.subprocess.run",
        lambda args, **_kwargs: command.extend(args),
    )

    _warp_vrt(Path("gdalwarp.exe"), tmp_path / "dgm1.vrt", tmp_path / "dgm1.tif", {})

    assert command[command.index("-t_srs") + 1] == WGS84_UTM32


def test_grd_translate_uses_createcopy_with_the_northwood_driver(monkeypatch, tmp_path) -> None:
    command = []
    grd_path = tmp_path / "dgm1.grd"
    grd_path.write_bytes(b"\x00" * 520)  # stub for _patch_grd_style

    monkeypatch.setattr(
        "multiplanner_api.ellipse_exports.subprocess.run",
        lambda args, **_kwargs: command.extend(args),
    )

    _translate_to_grd(Path("gdal_translate.exe"), tmp_path / "dgm1.tif", grd_path, {})

    # NWT_GRD must be built by gdal_translate (CreateCopy) reading the warped
    # GeoTIFF, so the driver derives the real Z min/max instead of garbage defaults.
    # Explicit -ot Float32 -b 1 because NWT_GRD only supports single-band Float32.
    assert command[0] == "gdal_translate.exe"
    assert command[command.index("-of") + 1] == GRD_DRIVER
    assert command[command.index("-ot") + 1] == "Float32"
    assert command[command.index("-b") + 1] == "1"
    assert str(tmp_path / "dgm1.tif") in command


def _make_stub_grd(path: Path, fz_min: float, fz_max: float, proj: str, mid_z: float) -> None:
    import struct as _s
    b = bytearray(1024)
    b[0:6] = b"HGPC1\x00"
    _s.pack_into("<f", b, 45, fz_min)
    _s.pack_into("<f", b, 49, fz_max)
    proj_enc = proj.encode("ascii") + b"\x00"
    b[256:256 + len(proj_enc)] = proj_enc
    _s.pack_into("<H", b, 516, 3)                    # nColorInflections = 3
    _s.pack_into("<f", b, 518, fz_min)               # entry[0] z = fZMin
    b[522:525] = bytes([0, 0, 255])
    _s.pack_into("<f", b, 525, mid_z)                # entry[1] z = mid (GDAL bug value)
    b[529:532] = bytes([255, 255, 0])
    _s.pack_into("<f", b, 532, fz_max)               # entry[2] z = fZMax
    b[536:539] = bytes([255, 0, 0])
    path.write_bytes(bytes(b))


def test_grd_style_flags_patched_to_gradient_after_translate(monkeypatch, tmp_path) -> None:
    grd_path = tmp_path / "dgm1.grd"
    _make_stub_grd(grd_path, 33.53, 68.08,
                   'Earth Projection 8, 104, "m", 9, 0, 0.9996, 500000, 0',
                   17.275)

    monkeypatch.setattr("multiplanner_api.ellipse_exports.subprocess.run", lambda *a, **k: None)

    _translate_to_grd(Path("gdal_translate.exe"), tmp_path / "dgm1.tif", grd_path, {})

    data = grd_path.read_bytes()
    import struct as _s

    # 1. Style flags = 7 so Ellipse reads Float32 Z band, not byte color-ramp bands.
    assert data[512:516] == b"\x07\x00\x00\x00"

    # 2. Color entry[1] Z corrected from relative offset to absolute elevation.
    fixed_z = _s.unpack_from("<f", data, 525)[0]
    assert abs(fixed_z - (33.53 + 17.275)) < 0.001

    # 3. Projection string prefixed with "CoordSys " for MapInfo/Ellipse parsing.
    proj = data[256:data.index(b"\x00", 256)].decode("ascii")
    assert proj.startswith("CoordSys ")


def test_grd_elevation_warps_to_geotiff_then_createcopies_to_grd(monkeypatch, tmp_path) -> None:
    calls = []

    monkeypatch.setattr(
        "multiplanner_api.ellipse_exports._warp_vrt",
        lambda _gdalwarp, _vrt, tif, _env: calls.append(("warp", Path(tif).suffix)),
    )
    monkeypatch.setattr(
        "multiplanner_api.ellipse_exports._translate_to_grd",
        lambda _translate, tif, grd, _env: calls.append(("translate", Path(tif).suffix, Path(grd).suffix)),
    )
    monkeypatch.setattr("multiplanner_api.ellipse_exports._write_mapinfo_tab", lambda *_args, **_kwargs: None)

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
        "multiplanner_api.ellipse_exports.subprocess.run",
        lambda *_args, **_kwargs: type("Result", (), {
            "stdout": '{"size":[2,3],"cornerCoordinates":{"upperLeft":[1,2],"upperRight":[3,2],"lowerRight":[3,0],"lowerLeft":[1,0]}}'
        })(),
    )
    tab_path = tmp_path / "dgm1.TAB"

    _write_mapinfo_tab(Path("gdalinfo.exe"), tmp_path / "dgm1.tif", tab_path, {})

    assert MAPINFO_WGS84_UTM32 in tab_path.read_text(encoding="ascii")


def test_tab_validation_rejects_non_utm32_geotiff(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "multiplanner_api.ellipse_exports.subprocess.run",
        lambda *_args, **_kwargs: type("Result", (), {
            "stdout": '{"coordinateSystem":{"wkt":"ID[\\"EPSG\\",25832]"}}'
        })(),
    )

    with pytest.raises(ValueError, match="was not reprojected to EPSG:32632"):
        _write_mapinfo_tab(Path("gdalinfo.exe"), tmp_path / "dgm1.tif", tmp_path / "dgm1.TAB", {}, require_utm32=True)


def test_ellipse_export_filename_identifies_selection_dataset_and_tile_count(monkeypatch, tmp_path) -> None:
    gdal_dir = tmp_path / "gdal"
    gdal_dir.mkdir()
    for executable in ("gdalbuildvrt.exe", "gdalwarp.exe", "gdalinfo.exe"):
        (gdal_dir / executable).write_text("", encoding="ascii")

    monkeypatch.setattr("multiplanner_api.ellipse_exports._build_vrt", lambda *_args: None)
    monkeypatch.setattr("multiplanner_api.ellipse_exports._warp_vrt", lambda *_args: None)
    monkeypatch.setattr("multiplanner_api.ellipse_exports._write_mapinfo_tab", lambda *_args, **_kwargs: None)

    exports, warnings = _export_for_ellipse(
        {"dom1": [tmp_path / "a.tif", tmp_path / "b.tif"]},
        tmp_path / "leaflet_polygon",
        str(gdal_dir),
        build_pyramids=False,
    )

    assert not warnings
    assert Path(exports[0]).name == "leaflet_polygon_dom1_2tiles_utm32n_ellipse.tif"
    assert Path(exports[1]).name == "leaflet_polygon_dom1_2tiles_utm32n_ellipse.TAB"


def test_ellipse_geotiff_tab_export_reports_gdal_failures_as_warnings(monkeypatch, tmp_path) -> None:
    gdal_dir = tmp_path / "gdal"
    gdal_dir.mkdir()
    for executable in ("gdalbuildvrt.exe", "gdalwarp.exe", "gdalinfo.exe"):
        (gdal_dir / executable).write_text("", encoding="ascii")

    def raise_warp_error(*_args):
        raise ValueError("gdalwarp failed: reprojection failed")

    monkeypatch.setattr("multiplanner_api.ellipse_exports._build_vrt", lambda *_args: None)
    monkeypatch.setattr("multiplanner_api.ellipse_exports._warp_vrt", raise_warp_error)

    exports, warnings = _export_for_ellipse(
        {"dgm1": [tmp_path / "a.tif"]},
        tmp_path / "leaflet_polygon",
        str(gdal_dir),
        build_pyramids=False,
    )

    assert exports == []
    assert warnings == ["UTM32N GeoTIFF + TAB export failed for dgm1: gdalwarp failed: reprojection failed"]


def test_grd_export_writes_a_real_orthophoto_file(monkeypatch, tmp_path) -> None:
    gdal_dir = tmp_path / "gdal"
    gdal_dir.mkdir()
    for executable in ("gdalbuildvrt.exe", "gdalwarp.exe", "gdalinfo.exe"):
        (gdal_dir / executable).write_text("", encoding="ascii")

    monkeypatch.setattr("multiplanner_api.ellipse_exports._build_vrt", lambda *_args: None)
    monkeypatch.setattr("multiplanner_api.ellipse_exports._warp_vrt", lambda *_args: None)
    monkeypatch.setattr("multiplanner_api.ellipse_exports._write_mapinfo_tab", lambda *_args: None)

    exports, warnings = _export_grd(
        {"dop20": [tmp_path / "a.tif"]},
        tmp_path / "selection",
        str(gdal_dir),
    )

    assert not warnings
    assert {Path(path).suffix for path in exports} == {".tif", ".TAB"}
    assert any(Path(path).name.endswith("_utm32.tif") for path in exports)


def test_extract_supported_sources_prefers_all_tiffs_from_zip(tmp_path) -> None:
    zip_path = tmp_path / "tiles.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("tile/a.tif", b"tif-a")
        zf.writestr("tile/b.tif", b"tif-b")
        zf.writestr("tile/c.xyz", b"x y z")

    extracted = _extract_supported_sources(zip_path, tmp_path)

    assert [path.as_posix() for path in extracted] == [
        (tmp_path / "tile" / "a.tif").as_posix(),
        (tmp_path / "tile" / "b.tif").as_posix(),
    ]


def test_extract_supported_sources_falls_back_to_xyz_files(tmp_path) -> None:
    zip_path = tmp_path / "tiles.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("tile/a.xyz", b"x y z")
        zf.writestr("tile/b.xyz", b"x y z")
        zf.writestr("tile/c.csv", b"x,y,z")

    extracted = _extract_supported_sources(zip_path, tmp_path)

    assert [path.as_posix() for path in extracted] == [
        (tmp_path / "tile" / "a.xyz").as_posix(),
        (tmp_path / "tile" / "b.xyz").as_posix(),
    ]


def test_expanded_download_paths_returns_original_file_when_zip_has_no_supported_sources(tmp_path) -> None:
    zip_path = tmp_path / "tiles.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("tile/readme.txt", b"hello")

    expanded = _expanded_download_paths(zip_path, tmp_path)

    assert expanded == [zip_path]


def test_extract_supported_sources_falls_back_to_gml_files(tmp_path) -> None:
    zip_path = tmp_path / "tiles.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("tile/a.gml", b"<CityModel />")
        zf.writestr("tile/b.gml", b"<CityModel />")
        zf.writestr("tile/readme.txt", b"hello")

    extracted = _extract_supported_sources(zip_path, tmp_path)

    assert [path.as_posix() for path in extracted] == [
        (tmp_path / "tile" / "a.gml").as_posix(),
        (tmp_path / "tile" / "b.gml").as_posix(),
    ]
