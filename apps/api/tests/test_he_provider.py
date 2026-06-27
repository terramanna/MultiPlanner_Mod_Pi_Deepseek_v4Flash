from shapely.geometry import box

from multiplanner_api.he import _tile_cells, _tile_record, locate_tiles, summarize_tiles
from multiplanner_api.providers import SERVICE_PROVIDERS, provider_dataset_names

WCS_BASE_DGM1 = "https://inspirehessen.de/raster/dgm1/ows"
WCS_BASE_DOM1 = "https://inspirehessen.de/raster/dom1/ows"
WCS_BASE_DOP20 = "https://inspirehessen.de/raster/dop20/ows"

# Frankfurt city centre ~ EPSG:25832: e ≈ 476 300, n ≈ 5 551 400
FRANKFURT_POINT = "8.6821,50.1109"


def test_hvbg_he_provider_lists_terrain_surface_and_ortho_datasets() -> None:
    assert provider_dataset_names("hvbg-he") == ("dgm1", "dom1", "dop20")


def test_tile_cells_single_point_returns_one_cell() -> None:
    # A single point inside one 1 km cell
    pt = box(476_300, 5_551_400, 476_300, 5_551_400)
    cells = _tile_cells(pt)
    assert len(cells) == 1
    e, n = cells[0]
    assert e == 476_000
    assert n == 5_551_000


def test_tile_cells_straddles_boundary_returns_four_cells() -> None:
    # Tiny box straddling a 1 km boundary
    area = box(476_999, 5_551_999, 477_001, 5_552_001)
    cells = _tile_cells(area)
    assert set(cells) == {(476_000, 5_551_000), (476_000, 5_552_000), (477_000, 5_551_000), (477_000, 5_552_000)}


def test_tile_cells_origins_are_multiples_of_1000() -> None:
    area = box(476_500, 5_551_500, 477_500, 5_552_500)
    for e, n in _tile_cells(area):
        assert e % 1000 == 0
        assert n % 1000 == 0


def test_tile_record_dgm1_url_format() -> None:
    record = _tile_record("dgm1", 476_000, 5_551_000, WCS_BASE_DGM1, "he_dgm1")
    assert record["tile_id"] == "he_dgm1_476000_5551000"
    url = record["primary_url"]
    assert url.startswith(WCS_BASE_DGM1 + "?")
    assert "coverageid=he_dgm1" in url
    assert "FORMAT=GTIFF" in url
    assert "SUBSET=e(476000,477000)" in url
    assert "SUBSET=n(5551000,5552000)" in url
    assert "version=2.0.1" in url


def test_tile_record_dom1_uses_dom1_coverage_id() -> None:
    record = _tile_record("dom1", 476_000, 5_551_000, WCS_BASE_DOM1, "dom1")
    assert "coverageid=dom1" in record["primary_url"]
    assert record["tile_id"] == "he_dom1_476000_5551000"


def test_locate_tiles_point_geometry_returns_one_tile() -> None:
    config = SERVICE_PROVIDERS["hvbg-he"]["datasets"]["dgm1"]
    tiles = locate_tiles(
        "dgm1",
        config=config,
        geometry=FRANKFURT_POINT,
        geometry_type="esriGeometryPoint",
        timeout=1,
    )
    assert len(tiles) == 1
    tile = tiles[0]
    assert tile["tile_id"].startswith("he_dgm1_")
    assert "inspirehessen.de/raster/dgm1/ows" in tile["primary_url"]
    assert "coverageid=he_dgm1" in tile["primary_url"]


def test_locate_tiles_envelope_geometry() -> None:
    import json
    # ~3.5 km × 5.5 km box → roughly 20 tiles, well within the 200-tile limit
    geom = json.dumps({"xmin": 8.65, "ymin": 50.10, "xmax": 8.70, "ymax": 50.15, "spatialReference": {"wkid": 4326}})
    config = SERVICE_PROVIDERS["hvbg-he"]["datasets"]["dgm1"]
    tiles = locate_tiles(
        "dgm1",
        config=config,
        geometry=geom,
        geometry_type="esriGeometryEnvelope",
        timeout=1,
    )
    assert len(tiles) > 1
    for tile in tiles:
        assert "SUBSET=e(" in tile["primary_url"]
        assert "SUBSET=n(" in tile["primary_url"]


def test_locate_tiles_polygon_geometry() -> None:
    import json
    # Small polygon around Frankfurt centre
    geom = json.dumps({"rings": [[[8.65, 50.09], [8.70, 50.09], [8.70, 50.13], [8.65, 50.13], [8.65, 50.09]]]})
    config = SERVICE_PROVIDERS["hvbg-he"]["datasets"]["dgm1"]
    tiles = locate_tiles(
        "dgm1",
        config=config,
        geometry=geom,
        geometry_type="esriGeometryPolygon",
        timeout=1,
    )
    assert len(tiles) >= 1


def test_summarize_tiles_has_correct_provider_and_dataset() -> None:
    config = SERVICE_PROVIDERS["hvbg-he"]["datasets"]["dgm1"]
    summaries = summarize_tiles(
        "dgm1",
        config=config,
        geometry=FRANKFURT_POINT,
        geometry_type="esriGeometryPoint",
        timeout=1,
    )
    assert len(summaries) == 1
    s = summaries[0]
    assert s["provider"] == "hvbg-he"
    assert s["dataset"] == "dgm1"
    assert s["tile_id"].startswith("he_dgm1_")
    assert s["source"] == "https://inspirehessen.de/"


def test_locate_tiles_raises_for_oversized_area() -> None:
    import json
    import pytest
    # Bbox spanning ~500 km × 500 km → far more than 200 tiles
    geom = json.dumps({"xmin": 7.0, "ymin": 47.0, "xmax": 12.0, "ymax": 52.0, "spatialReference": {"wkid": 4326}})
    config = SERVICE_PROVIDERS["hvbg-he"]["datasets"]["dgm1"]
    with pytest.raises(ValueError, match="200 tiles"):
        locate_tiles("dgm1", config=config, geometry=geom, geometry_type="esriGeometryEnvelope", timeout=1)


# --- dop20 ---

def test_tile_record_dop20_url_format() -> None:
    record = _tile_record("dop20", 476_000, 5_551_000, WCS_BASE_DOP20, "he_dop20")
    assert record["tile_id"] == "he_dop20_476000_5551000"
    url = record["primary_url"]
    assert url.startswith(WCS_BASE_DOP20 + "?")
    assert "coverageid=he_dop20" in url
    assert "FORMAT=GTIFF" in url
    assert "SUBSET=e(476000,477000)" in url
    assert "SUBSET=n(5551000,5552000)" in url
    assert "version=2.0.1" in url


def test_locate_tiles_dop20_point_returns_one_tile() -> None:
    config = SERVICE_PROVIDERS["hvbg-he"]["datasets"]["dop20"]
    tiles = locate_tiles(
        "dop20",
        config=config,
        geometry=FRANKFURT_POINT,
        geometry_type="esriGeometryPoint",
        timeout=1,
    )
    assert len(tiles) == 1
    tile = tiles[0]
    assert tile["tile_id"].startswith("he_dop20_")
    assert "inspirehessen.de/raster/dop20/ows" in tile["primary_url"]
    assert "coverageid=he_dop20" in tile["primary_url"]


def test_summarize_dop20_has_correct_provider_and_dataset() -> None:
    config = SERVICE_PROVIDERS["hvbg-he"]["datasets"]["dop20"]
    summaries = summarize_tiles(
        "dop20",
        config=config,
        geometry=FRANKFURT_POINT,
        geometry_type="esriGeometryPoint",
        timeout=1,
    )
    assert len(summaries) == 1
    s = summaries[0]
    assert s["provider"] == "hvbg-he"
    assert s["dataset"] == "dop20"
    assert s["tile_id"].startswith("he_dop20_")
