from shapely.geometry import box

from multiplanner_api.st import (
    WCS_TILE_SIZE_M,
    DOP20_TILE_SIZE_M,
    _dop20_tile_record,
    _tile_cells,
    _tile_record,
    locate_tiles,
    summarize_tiles,
)
from multiplanner_api.providers import SERVICE_PROVIDERS, provider_dataset_names

DGM1_WCS_ENDPOINT = "https://www.geodatenportal.sachsen-anhalt.de/wss/service/ST_LVermGeo_DGM1_WCS_OpenData/guest"
DOM1_WCS_ENDPOINT = "https://geodatenportal.sachsen-anhalt.de/ows_WCS_ST_DOM1"
DOP20_BASE = "https://www.geodatenportal.sachsen-anhalt.de/gfds_webshare/sec-download/LVermGeo/DOP20"

# Halle (Saale) city centre ~ EPSG:25832: x ≈ 704 000, y ≈ 5 717 000
HALLE_POINT = "11.9668,51.4825"


def test_lvermgeo_st_provider_lists_all_datasets() -> None:
    assert provider_dataset_names("lvermgeo-st") == ("dgm1", "dom1", "dop20", "lod2")


def test_tile_cells_single_point_returns_one_cell() -> None:
    pt = box(704_300, 5_717_400, 704_300, 5_717_400)
    cells = _tile_cells(pt, WCS_TILE_SIZE_M)
    assert len(cells) == 1
    x, y = cells[0]
    assert x == 704_000
    assert y == 5_717_000


def test_tile_cells_straddles_boundary_returns_four_cells() -> None:
    area = box(704_999, 5_717_999, 705_001, 5_718_001)
    cells = _tile_cells(area, WCS_TILE_SIZE_M)
    assert set(cells) == {(704_000, 5_717_000), (704_000, 5_718_000), (705_000, 5_717_000), (705_000, 5_718_000)}


def test_tile_cells_origins_are_multiples_of_1000() -> None:
    area = box(704_500, 5_717_500, 705_500, 5_718_500)
    for x, y in _tile_cells(area, WCS_TILE_SIZE_M):
        assert x % 1000 == 0
        assert y % 1000 == 0


def test_tile_record_dgm1_url_format() -> None:
    record = _tile_record("dgm1", 704_000, 5_717_000)
    assert record["tile_id"] == "st_dgm1_704000_5717000"
    url = record["primary_url"]
    assert url.startswith(DGM1_WCS_ENDPOINT + "?")
    assert "coverageid=Coverage1" in url
    assert "FORMAT=image/tiff" in url
    assert "SUBSET=x(704000,705000)" in url
    assert "SUBSET=y(5717000,5718000)" in url
    assert "version=2.0.1" in url


def test_locate_tiles_point_geometry_returns_one_tile() -> None:
    config = SERVICE_PROVIDERS["lvermgeo-st"]["datasets"]["dgm1"]
    tiles = locate_tiles(
        "dgm1",
        config=config,
        geometry=HALLE_POINT,
        geometry_type="esriGeometryPoint",
        timeout=1,
    )
    assert len(tiles) == 1
    tile = tiles[0]
    assert tile["tile_id"].startswith("st_dgm1_")
    assert "ST_LVermGeo_DGM1_WCS_OpenData" in tile["primary_url"]
    assert "coverageid=Coverage1" in tile["primary_url"]
    assert "SUBSET=x(" in tile["primary_url"]
    assert "SUBSET=y(" in tile["primary_url"]


def test_locate_tiles_envelope_geometry() -> None:
    import json
    geom = json.dumps({"xmin": 11.92, "ymin": 51.46, "xmax": 11.97, "ymax": 51.50,
                       "spatialReference": {"wkid": 4326}})
    config = SERVICE_PROVIDERS["lvermgeo-st"]["datasets"]["dgm1"]
    tiles = locate_tiles("dgm1", config=config, geometry=geom,
                         geometry_type="esriGeometryEnvelope", timeout=1)
    assert len(tiles) > 1
    for tile in tiles:
        assert "SUBSET=x(" in tile["primary_url"]
        assert "SUBSET=y(" in tile["primary_url"]


def test_locate_tiles_polygon_geometry() -> None:
    import json
    geom = json.dumps({"rings": [[[11.93, 51.47], [11.96, 51.47],
                                   [11.96, 51.50], [11.93, 51.50], [11.93, 51.47]]]})
    config = SERVICE_PROVIDERS["lvermgeo-st"]["datasets"]["dgm1"]
    tiles = locate_tiles("dgm1", config=config, geometry=geom,
                         geometry_type="esriGeometryPolygon", timeout=1)
    assert len(tiles) >= 1


def test_summarize_tiles_has_correct_provider_and_dataset() -> None:
    config = SERVICE_PROVIDERS["lvermgeo-st"]["datasets"]["dgm1"]
    summaries = summarize_tiles("dgm1", config=config, geometry=HALLE_POINT,
                                geometry_type="esriGeometryPoint", timeout=1)
    assert len(summaries) == 1
    s = summaries[0]
    assert s["provider"] == "lvermgeo-st"
    assert s["dataset"] == "dgm1"
    assert s["tile_id"].startswith("st_dgm1_")
    assert "geodatenportal.sachsen-anhalt.de" in s["source"]


def test_locate_tiles_raises_for_oversized_area() -> None:
    import json
    import pytest
    geom = json.dumps({"xmin": 10.5, "ymin": 50.8, "xmax": 13.4, "ymax": 53.1,
                       "spatialReference": {"wkid": 4326}})
    config = SERVICE_PROVIDERS["lvermgeo-st"]["datasets"]["dgm1"]
    with pytest.raises(ValueError, match="200 tiles"):
        locate_tiles("dgm1", config=config, geometry=geom,
                     geometry_type="esriGeometryEnvelope", timeout=1)


# --- dom1 ---

def test_tile_record_dom1_uses_corrected_wcs_endpoint() -> None:
    # Verified: ows_WCS_ST_DOM1 (previously inferred ST_LVermGeo_DOM1_WCS_OpenData was wrong)
    record = _tile_record("dom1", 704_000, 5_717_000)
    assert record["tile_id"] == "st_dom1_704000_5717000"
    url = record["primary_url"]
    assert url.startswith(DOM1_WCS_ENDPOINT + "?")
    assert "coverageid=Coverage1" in url
    assert "FORMAT=image/tiff" in url
    assert "SUBSET=x(704000,705000)" in url
    assert "SUBSET=y(5717000,5718000)" in url


def test_locate_tiles_dom1_point_returns_one_tile() -> None:
    config = SERVICE_PROVIDERS["lvermgeo-st"]["datasets"]["dom1"]
    tiles = locate_tiles("dom1", config=config, geometry=HALLE_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert len(tiles) == 1
    tile = tiles[0]
    assert tile["tile_id"].startswith("st_dom1_")
    assert "ows_WCS_ST_DOM1" in tile["primary_url"]
    assert "coverageid=Coverage1" in tile["primary_url"]


def test_summarize_dom1_has_correct_provider_and_dataset() -> None:
    config = SERVICE_PROVIDERS["lvermgeo-st"]["datasets"]["dom1"]
    summaries = summarize_tiles("dom1", config=config, geometry=HALLE_POINT,
                                geometry_type="esriGeometryPoint", timeout=1)
    assert len(summaries) == 1
    s = summaries[0]
    assert s["provider"] == "lvermgeo-st"
    assert s["dataset"] == "dom1"
    assert s["tile_id"].startswith("st_dom1_")


# --- dop20 ---

def test_dop20_tile_record_builds_correct_url() -> None:
    # Tile SW corner (724 km easting, 5646 km northing) matches WFS truedop_kacheln NAME=327245646
    record = _dop20_tile_record(724_000, 5_646_000)
    assert record["tile_id"] == "st_dop20_327245646"
    assert record["primary_url"] == f"{DOP20_BASE}/327245646.tif"


def test_dop20_tile_cells_are_2km_multiples() -> None:
    area = box(724_500, 5_646_500, 725_500, 5_647_500)
    cells = _tile_cells(area, DOP20_TILE_SIZE_M)
    for x, y in cells:
        assert x % 2000 == 0
        assert y % 2000 == 0


def test_locate_tiles_dop20_point_returns_one_2km_tile() -> None:
    config = SERVICE_PROVIDERS["lvermgeo-st"]["datasets"]["dop20"]
    tiles = locate_tiles("dop20", config=config, geometry=HALLE_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert len(tiles) == 1
    tile = tiles[0]
    assert tile["tile_id"].startswith("st_dop20_32")
    assert tile["primary_url"].startswith(DOP20_BASE + "/32")
    assert tile["primary_url"].endswith(".tif")


def test_dop20_known_tile_names_match_wfs_naming() -> None:
    # WFS truedop_kacheln: Feature 0 bounds (724000,5646000)-(726000,5648000) NAME=327245646
    # Feature 1 bounds (726000,5646000)-(728000,5648000) NAME=327265646
    # Feature 2 bounds (722000,5648000)-(724000,5650000) NAME=327225648
    expected = [
        (724_000, 5_646_000, "327245646"),
        (726_000, 5_646_000, "327265646"),
        (722_000, 5_648_000, "327225648"),
    ]
    for x_m, y_m, tile_name in expected:
        record = _dop20_tile_record(x_m, y_m)
        assert record["tile_id"] == f"st_dop20_{tile_name}"
        assert record["primary_url"] == f"{DOP20_BASE}/{tile_name}.tif"


# --- lod2 ---

def test_locate_tiles_lod2_always_returns_four_bulk_zips() -> None:
    config = SERVICE_PROVIDERS["lvermgeo-st"]["datasets"]["lod2"]
    tiles = locate_tiles("lod2", config=config, geometry=HALLE_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert len(tiles) == 4
    for i, tile in enumerate(tiles, start=1):
        assert tile["tile_id"] == f"st_lod2_{i}"
        assert tile["primary_url"].endswith(f"LoD2-{i}.zip")
        assert "geodatenportal.sachsen-anhalt.de" in tile["primary_url"]


def test_lod2_urls_are_all_distinct() -> None:
    config = SERVICE_PROVIDERS["lvermgeo-st"]["datasets"]["lod2"]
    tiles = locate_tiles("lod2", config=config, geometry=HALLE_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    urls = [t["primary_url"] for t in tiles]
    assert len(set(urls)) == 4
