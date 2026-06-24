from pathlib import Path

from multiplanner_api.downloads import (
    MAPINFO_WGS84_UTM32,
    WGS84_UTM32,
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
