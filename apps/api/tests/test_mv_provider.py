import json

import pytest
from shapely.geometry import box

from multiplanner_api.mv import _tile_cells, _tile_record, locate_tiles, summarize_tiles
from multiplanner_api.providers import SERVICE_PROVIDERS, provider_dataset_names

WCS_ENDPOINT = "https://www.geodaten-mv.de/dienste/dgm_wcs"
DOM_WCS_ENDPOINT = "https://www.geodaten-mv.de/dienste/dom_wcs"

# Rostock city centre ~ EPSG:25833: x ≈ 313 000, y ≈ 5 998 000
ROSTOCK_POINT = "12.14,54.09"


def test_laiv_mv_provider_lists_dgm1_and_dom1() -> None:
    assert provider_dataset_names("laiv-mv") == ("dgm1", "dom1")


def test_tile_cells_single_point_returns_one_cell() -> None:
    pt = box(313_400, 5_998_500, 313_400, 5_998_500)
    cells = _tile_cells(pt)
    assert len(cells) == 1
    x, y = cells[0]
    assert x == 313_000
    assert y == 5_998_000


def test_tile_cells_straddles_boundary_returns_four_cells() -> None:
    area = box(313_999, 5_998_999, 314_001, 5_999_001)
    cells = _tile_cells(area)
    assert set(cells) == {
        (313_000, 5_998_000),
        (313_000, 5_999_000),
        (314_000, 5_998_000),
        (314_000, 5_999_000),
    }


def test_tile_cells_origins_are_multiples_of_1000() -> None:
    area = box(313_500, 5_998_500, 314_500, 5_999_500)
    for x, y in _tile_cells(area):
        assert x % 1000 == 0
        assert y % 1000 == 0


def test_tile_record_url_format() -> None:
    record = _tile_record("dgm1", 313_000, 5_998_000)
    assert record["tile_id"] == "mv_dgm1_313000_5998000"
    url = record["primary_url"]
    assert url.startswith(WCS_ENDPOINT + "?")
    assert "coverageid=mv_dgm" in url
    assert "FORMAT=image/tiff" in url
    assert "SUBSET=x(313000,314000)" in url
    assert "SUBSET=y(5998000,5999000)" in url
    assert "version=2.0.1" in url


def test_locate_tiles_point_geometry_returns_one_tile() -> None:
    config = SERVICE_PROVIDERS["laiv-mv"]["datasets"]["dgm1"]
    tiles = locate_tiles(
        "dgm1",
        config=config,
        geometry=ROSTOCK_POINT,
        geometry_type="esriGeometryPoint",
        timeout=1,
    )
    assert len(tiles) == 1
    tile = tiles[0]
    assert tile["tile_id"].startswith("mv_dgm1_")
    assert WCS_ENDPOINT in tile["primary_url"]
    assert "coverageid=mv_dgm" in tile["primary_url"]
    assert "SUBSET=x(" in tile["primary_url"]
    assert "SUBSET=y(" in tile["primary_url"]


def test_locate_tiles_envelope_geometry() -> None:
    geom = json.dumps({
        "xmin": 12.10, "ymin": 54.05, "xmax": 12.20, "ymax": 54.12,
        "spatialReference": {"wkid": 4326},
    })
    config = SERVICE_PROVIDERS["laiv-mv"]["datasets"]["dgm1"]
    tiles = locate_tiles("dgm1", config=config, geometry=geom,
                         geometry_type="esriGeometryEnvelope", timeout=1)
    assert len(tiles) > 1
    for tile in tiles:
        assert "SUBSET=x(" in tile["primary_url"]
        assert "SUBSET=y(" in tile["primary_url"]


def test_locate_tiles_polygon_geometry() -> None:
    geom = json.dumps({"rings": [[[12.10, 54.05], [12.20, 54.05],
                                   [12.20, 54.12], [12.10, 54.12], [12.10, 54.05]]]})
    config = SERVICE_PROVIDERS["laiv-mv"]["datasets"]["dgm1"]
    tiles = locate_tiles("dgm1", config=config, geometry=geom,
                         geometry_type="esriGeometryPolygon", timeout=1)
    assert len(tiles) >= 1


def test_summarize_tiles_has_correct_provider_and_dataset() -> None:
    config = SERVICE_PROVIDERS["laiv-mv"]["datasets"]["dgm1"]
    summaries = summarize_tiles("dgm1", config=config, geometry=ROSTOCK_POINT,
                                geometry_type="esriGeometryPoint", timeout=1)
    assert len(summaries) == 1
    s = summaries[0]
    assert s["provider"] == "laiv-mv"
    assert s["dataset"] == "dgm1"
    assert s["tile_id"].startswith("mv_dgm1_")
    assert "geodaten-mv.de" in s["source"]


def test_locate_tiles_raises_for_oversized_area() -> None:
    geom = json.dumps({
        "xmin": 10.5, "ymin": 53.0, "xmax": 14.5, "ymax": 54.8,
        "spatialReference": {"wkid": 4326},
    })
    config = SERVICE_PROVIDERS["laiv-mv"]["datasets"]["dgm1"]
    with pytest.raises(ValueError, match="200 tiles"):
        locate_tiles("dgm1", config=config, geometry=geom,
                     geometry_type="esriGeometryEnvelope", timeout=1)


# --- dom1 ---

def test_tile_record_dom1_uses_dom_endpoint() -> None:
    record = _tile_record("dom1", 313_000, 5_998_000)
    assert record["tile_id"] == "mv_dom1_313000_5998000"
    url = record["primary_url"]
    assert url.startswith(DOM_WCS_ENDPOINT + "?")
    assert "coverageid=mv_dom" in url
    assert "FORMAT=image/tiff" in url
    assert "SUBSET=x(313000,314000)" in url
    assert "SUBSET=y(5998000,5999000)" in url


def test_locate_tiles_dom1_point_returns_one_tile() -> None:
    config = SERVICE_PROVIDERS["laiv-mv"]["datasets"]["dom1"]
    tiles = locate_tiles("dom1", config=config, geometry=ROSTOCK_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert len(tiles) == 1
    tile = tiles[0]
    assert tile["tile_id"].startswith("mv_dom1_")
    assert DOM_WCS_ENDPOINT in tile["primary_url"]
    assert "coverageid=mv_dom" in tile["primary_url"]


def test_summarize_dom1_has_correct_provider_and_dataset() -> None:
    config = SERVICE_PROVIDERS["laiv-mv"]["datasets"]["dom1"]
    summaries = summarize_tiles("dom1", config=config, geometry=ROSTOCK_POINT,
                                geometry_type="esriGeometryPoint", timeout=1)
    assert len(summaries) == 1
    s = summaries[0]
    assert s["provider"] == "laiv-mv"
    assert s["dataset"] == "dom1"
    assert s["tile_id"].startswith("mv_dom1_")
