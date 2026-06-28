import json

import pytest
from shapely.geometry import box

from multiplanner_api.bb import _tile_cells, _tile_record, locate_tiles, summarize_tiles
from multiplanner_api.providers import SERVICE_PROVIDERS, provider_dataset_names

DGM_WCS_ENDPOINT = "https://isk.geobasis-bb.de/ows/dgm_wcs"
BDOM_WCS_ENDPOINT = "https://isk.geobasis-bb.de/ows/bdom_wcs"
LOD2_BASE = "https://data.geobasis-bb.de/geobasis/daten/3d_gebaeude/lod2_gml/"

# Potsdam city centre ~ EPSG:25833: x ≈ 369 000, y ≈ 5 806 000
POTSDAM_POINT = "13.0622,52.3906"


def test_geobasis_bb_provider_dataset_names() -> None:
    assert provider_dataset_names("geobasis-bb") == ("dgm1", "dom1", "bdom", "lod2")


def test_tile_cells_single_point_returns_one_cell() -> None:
    pt = box(369_300, 5_806_400, 369_300, 5_806_400)
    cells = _tile_cells(pt)
    assert len(cells) == 1
    x, y = cells[0]
    assert x == 369_000
    assert y == 5_806_000


def test_tile_cells_straddles_boundary_returns_four_cells() -> None:
    area = box(369_999, 5_806_999, 370_001, 5_807_001)
    cells = _tile_cells(area)
    assert set(cells) == {
        (369_000, 5_806_000),
        (369_000, 5_807_000),
        (370_000, 5_806_000),
        (370_000, 5_807_000),
    }


def test_tile_cells_origins_are_multiples_of_1000() -> None:
    area = box(369_500, 5_806_500, 370_500, 5_807_500)
    for x, y in _tile_cells(area):
        assert x % 1000 == 0
        assert y % 1000 == 0


def test_tile_record_dgm1_url_format() -> None:
    record = _tile_record("dgm1", 369_000, 5_806_000)
    assert record["tile_id"] == "bb_dgm1_369000_5806000"
    url = record["primary_url"]
    assert url.startswith(DGM_WCS_ENDPOINT + "?")
    assert "coverageid=bb_dgm" in url
    assert "FORMAT=image/tiff" in url
    assert "SUBSET=x(369000,370000)" in url
    assert "SUBSET=y(5806000,5807000)" in url
    assert "version=2.0.1" in url


def test_tile_record_bdom_url_format() -> None:
    record = _tile_record("bdom", 369_000, 5_806_000)
    assert record["tile_id"] == "bb_bdom_369000_5806000"
    url = record["primary_url"]
    assert url.startswith(BDOM_WCS_ENDPOINT + "?")
    assert "coverageid=bb_bdom" in url
    assert "FORMAT=image/tiff" in url
    assert "SUBSET=x(369000,370000)" in url
    assert "SUBSET=y(5806000,5807000)" in url
    assert "version=2.0.1" in url


def test_tile_record_lod2_url_format() -> None:
    record = _tile_record("lod2", 369_000, 5_806_000)
    assert record["tile_id"] == "bb_lod2_369000_5806000"
    url = record["primary_url"]
    assert url == f"{LOD2_BASE}lod2_33369-5806.zip"


def test_tile_record_lod2_zero_padding() -> None:
    # easting 50 km → :03d → "050"; northing 5700 km → :04d → "5700"
    record = _tile_record("lod2", 50_000, 5_700_000)
    assert "lod2_33050-5700.zip" in record["primary_url"]


def test_locate_tiles_point_geometry_returns_one_tile() -> None:
    config = SERVICE_PROVIDERS["geobasis-bb"]["datasets"]["dgm1"]
    tiles = locate_tiles(
        "dgm1",
        config=config,
        geometry=POTSDAM_POINT,
        geometry_type="esriGeometryPoint",
        timeout=1,
    )
    assert len(tiles) == 1
    tile = tiles[0]
    assert tile["tile_id"].startswith("bb_dgm1_")
    assert DGM_WCS_ENDPOINT in tile["primary_url"]
    assert "coverageid=bb_dgm" in tile["primary_url"]
    assert "SUBSET=x(" in tile["primary_url"]
    assert "SUBSET=y(" in tile["primary_url"]


def test_locate_tiles_bdom_point_geometry() -> None:
    config = SERVICE_PROVIDERS["geobasis-bb"]["datasets"]["bdom"]
    tiles = locate_tiles(
        "bdom",
        config=config,
        geometry=POTSDAM_POINT,
        geometry_type="esriGeometryPoint",
        timeout=1,
    )
    assert len(tiles) == 1
    tile = tiles[0]
    assert tile["tile_id"].startswith("bb_bdom_")
    assert BDOM_WCS_ENDPOINT in tile["primary_url"]
    assert "coverageid=bb_bdom" in tile["primary_url"]


def test_locate_tiles_lod2_point_geometry() -> None:
    config = SERVICE_PROVIDERS["geobasis-bb"]["datasets"]["lod2"]
    tiles = locate_tiles(
        "lod2",
        config=config,
        geometry=POTSDAM_POINT,
        geometry_type="esriGeometryPoint",
        timeout=1,
    )
    assert len(tiles) == 1
    tile = tiles[0]
    assert tile["tile_id"].startswith("bb_lod2_")
    assert LOD2_BASE in tile["primary_url"]
    assert tile["primary_url"].endswith(".zip")


def test_locate_tiles_envelope_geometry() -> None:
    geom = json.dumps({
        "xmin": 13.05, "ymin": 52.38, "xmax": 13.10, "ymax": 52.42,
        "spatialReference": {"wkid": 4326},
    })
    config = SERVICE_PROVIDERS["geobasis-bb"]["datasets"]["dgm1"]
    tiles = locate_tiles("dgm1", config=config, geometry=geom,
                         geometry_type="esriGeometryEnvelope", timeout=1)
    assert len(tiles) > 1
    for tile in tiles:
        assert "SUBSET=x(" in tile["primary_url"]
        assert "SUBSET=y(" in tile["primary_url"]


def test_locate_tiles_polygon_geometry() -> None:
    geom = json.dumps({"rings": [[[13.05, 52.38], [13.10, 52.38],
                                   [13.10, 52.42], [13.05, 52.42], [13.05, 52.38]]]})
    config = SERVICE_PROVIDERS["geobasis-bb"]["datasets"]["dgm1"]
    tiles = locate_tiles("dgm1", config=config, geometry=geom,
                         geometry_type="esriGeometryPolygon", timeout=1)
    assert len(tiles) >= 1


def test_summarize_tiles_dgm1_has_correct_provider_and_dataset() -> None:
    config = SERVICE_PROVIDERS["geobasis-bb"]["datasets"]["dgm1"]
    summaries = summarize_tiles("dgm1", config=config, geometry=POTSDAM_POINT,
                                geometry_type="esriGeometryPoint", timeout=1)
    assert len(summaries) == 1
    s = summaries[0]
    assert s["provider"] == "geobasis-bb"
    assert s["dataset"] == "dgm1"
    assert s["tile_id"].startswith("bb_dgm1_")
    assert "geobasis-bb.de" in s["source"]


def test_summarize_tiles_lod2_source_url() -> None:
    config = SERVICE_PROVIDERS["geobasis-bb"]["datasets"]["lod2"]
    summaries = summarize_tiles("lod2", config=config, geometry=POTSDAM_POINT,
                                geometry_type="esriGeometryPoint", timeout=1)
    assert len(summaries) == 1
    s = summaries[0]
    assert s["dataset"] == "lod2"
    assert "geobasis-bb.de" in s["source"]
    assert s["primary_url"].endswith(".zip")


def test_locate_tiles_raises_for_oversized_area() -> None:
    geom = json.dumps({
        "xmin": 12.0, "ymin": 51.5, "xmax": 14.5, "ymax": 53.5,
        "spatialReference": {"wkid": 4326},
    })
    config = SERVICE_PROVIDERS["geobasis-bb"]["datasets"]["dgm1"]
    with pytest.raises(ValueError, match="200 tiles"):
        locate_tiles("dgm1", config=config, geometry=geom,
                     geometry_type="esriGeometryEnvelope", timeout=1)
