from shapely.geometry import box

from multiplanner_api.sl import (
    TILE_SIZE_M,
    _tile_cells,
    _tile_record,
    locate_tiles,
    summarize_tiles,
)
from multiplanner_api.providers import SERVICE_PROVIDERS, provider_dataset_names

WCS_BASE = "https://geoportal.saarland.de/gdi-sl/inspireraster/inspirewcsel"
COVERAGE_ID = "EL.GridCoverage"

# Saarbrücken city centre ~ EPSG:25832: e ≈ 340 500, n ≈ 5 449 500
SAARBRUECKEN_POINT = "6.9969,49.2354"


def test_lvgl_sl_provider_lists_dgm1_dataset() -> None:
    assert provider_dataset_names("lvgl-sl") == ("dgm1",)


def test_tile_cells_single_point_returns_one_cell() -> None:
    pt = box(340_500, 5_449_500, 340_500, 5_449_500)
    cells = _tile_cells(pt)
    assert len(cells) == 1
    e, n = cells[0]
    assert e == 340_000
    assert n == 5_449_000


def test_tile_cells_straddles_boundary_returns_four_cells() -> None:
    area = box(340_999, 5_449_999, 341_001, 5_450_001)
    cells = _tile_cells(area)
    assert set(cells) == {(340_000, 5_449_000), (340_000, 5_450_000), (341_000, 5_449_000), (341_000, 5_450_000)}


def test_tile_cells_origins_are_multiples_of_1000() -> None:
    area = box(340_500, 5_449_500, 341_500, 5_450_500)
    for e, n in _tile_cells(area):
        assert e % 1000 == 0
        assert n % 1000 == 0


def test_tile_record_dgm1_url_format() -> None:
    record = _tile_record(340_000, 5_449_000)
    assert record["tile_id"] == "sl_dgm1_340000_5449000"
    url = record["primary_url"]
    assert url.startswith(WCS_BASE + "?")
    assert f"coverageid={COVERAGE_ID}" in url
    assert "FORMAT=image/tiff" in url
    assert "SUBSET=E(340000,341000)" in url
    assert "SUBSET=N(5449000,5450000)" in url
    assert "version=2.0.1" in url


def test_locate_tiles_point_geometry_returns_one_tile() -> None:
    config = SERVICE_PROVIDERS["lvgl-sl"]["datasets"]["dgm1"]
    tiles = locate_tiles(
        "dgm1",
        config=config,
        geometry=SAARBRUECKEN_POINT,
        geometry_type="esriGeometryPoint",
        timeout=1,
    )
    assert len(tiles) == 1
    tile = tiles[0]
    assert tile["tile_id"].startswith("sl_dgm1_")
    assert WCS_BASE in tile["primary_url"]
    assert f"coverageid={COVERAGE_ID}" in tile["primary_url"]
    assert "SUBSET=E(" in tile["primary_url"]
    assert "SUBSET=N(" in tile["primary_url"]


def test_locate_tiles_envelope_geometry() -> None:
    import json
    geom = json.dumps({"xmin": 6.95, "ymin": 49.20, "xmax": 7.05, "ymax": 49.28,
                       "spatialReference": {"wkid": 4326}})
    config = SERVICE_PROVIDERS["lvgl-sl"]["datasets"]["dgm1"]
    tiles = locate_tiles("dgm1", config=config, geometry=geom,
                         geometry_type="esriGeometryEnvelope", timeout=1)
    assert len(tiles) > 1
    for tile in tiles:
        assert "SUBSET=E(" in tile["primary_url"]
        assert "SUBSET=N(" in tile["primary_url"]


def test_locate_tiles_polygon_geometry() -> None:
    import json
    geom = json.dumps({"rings": [[[6.95, 49.20], [7.05, 49.20],
                                   [7.05, 49.28], [6.95, 49.28], [6.95, 49.20]]]})
    config = SERVICE_PROVIDERS["lvgl-sl"]["datasets"]["dgm1"]
    tiles = locate_tiles("dgm1", config=config, geometry=geom,
                         geometry_type="esriGeometryPolygon", timeout=1)
    assert len(tiles) >= 1


def test_summarize_tiles_has_correct_provider_and_dataset() -> None:
    config = SERVICE_PROVIDERS["lvgl-sl"]["datasets"]["dgm1"]
    summaries = summarize_tiles("dgm1", config=config, geometry=SAARBRUECKEN_POINT,
                                geometry_type="esriGeometryPoint", timeout=1)
    assert len(summaries) == 1
    s = summaries[0]
    assert s["provider"] == "lvgl-sl"
    assert s["dataset"] == "dgm1"
    assert s["tile_id"].startswith("sl_dgm1_")
    assert "geoportal.saarland.de" in s["source"]


def test_locate_tiles_raises_for_oversized_area() -> None:
    import json
    import pytest
    geom = json.dumps({"xmin": 5.0, "ymin": 47.0, "xmax": 10.0, "ymax": 52.0,
                       "spatialReference": {"wkid": 4326}})
    config = SERVICE_PROVIDERS["lvgl-sl"]["datasets"]["dgm1"]
    with pytest.raises(ValueError, match="200 tiles"):
        locate_tiles("dgm1", config=config, geometry=geom,
                     geometry_type="esriGeometryEnvelope", timeout=1)
