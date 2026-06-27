from shapely.geometry import Point

from multiplanner_api.geosn import locate_tiles, summarize_tiles, tile_coordinates
from multiplanner_api.providers import SERVICE_PROVIDERS, provider_dataset_names


def test_geosn_provider_lists_1m_terrain_surface_and_ortho_datasets() -> None:
    assert provider_dataset_names("geosn-sn") == ("dgm1", "dom1", "dop20")


def test_geosn_grid_derives_the_intersecting_2km_tile_from_a_point() -> None:
    # Dresden city centre ~EPSG:25833: easting ~411 000 m, northing ~5 656 000 m
    # tile SW corner: 410 km easting, 5656 km northing (multiples of 2)
    point_utm33 = Point(411_000, 5_656_500)
    assert tile_coordinates(point_utm33) == [(410, 5656)]


def test_geosn_tile_coordinates_cover_multi_tile_area() -> None:
    # Box strictly inside 4 tiles (no edges land on tile boundaries)
    from shapely.geometry import box
    area = box(279_000, 5_591_000, 281_000, 5_593_000)
    coords = tile_coordinates(area)
    assert set(coords) == {(278, 5590), (278, 5592), (280, 5590), (280, 5592)}


def test_geosn_tile_keys_are_multiples_of_two() -> None:
    from shapely.geometry import box
    area = box(279_500, 5_591_500, 280_500, 5_592_500)
    coords = tile_coordinates(area)
    for east_km, north_km in coords:
        assert east_km % 2 == 0, f"east_km {east_km} is not a multiple of 2"
        assert north_km % 2 == 0, f"north_km {north_km} is not a multiple of 2"


GEOSN_BASE = "https://geocloud.landesvermessung.sachsen.de/public.php/dav/files/S6wwnFwX7882sZm/"


def test_geosn_locate_tiles_constructs_correct_url() -> None:
    config = SERVICE_PROVIDERS["geosn-sn"]["datasets"]["dgm1"]
    tiles = locate_tiles(
        "dgm1",
        config=config,
        geometry="13.74,51.05",
        geometry_type="esriGeometryPoint",
        timeout=1,
    )
    assert len(tiles) == 1
    tile = tiles[0]
    assert tile["primary_url"].startswith(GEOSN_DGM_BASE + "dgm1_33")
    assert tile["primary_url"].endswith("_2_sn_tiff.zip")


GEOSN_DGM_BASE = "https://geocloud.landesvermessung.sachsen.de/public.php/dav/files/JCcXyifaNdLDnxZ/"


def test_geosn_tile_record_url_matches_known_good_dom1_link() -> None:
    # Verified: https://...S6wwnFwX7882sZm/dom1_33278_5590_2_sn_tiff.zip
    from multiplanner_api.geosn import _tile_record
    record = _tile_record("dom1", 278, 5590, GEOSN_BASE)
    assert record["primary_url"] == GEOSN_BASE + "dom1_33278_5590_2_sn_tiff.zip"
    assert record["tile_id"] == "dom1_33278_5590_2_sn"


def test_geosn_tile_record_url_matches_known_good_dgm1_link() -> None:
    # Verified: https://...JCcXyifaNdLDnxZ/dgm1_33278_5590_2_sn_tiff.zip
    from multiplanner_api.geosn import _tile_record
    record = _tile_record("dgm1", 278, 5590, GEOSN_DGM_BASE)
    assert record["primary_url"] == GEOSN_DGM_BASE + "dgm1_33278_5590_2_sn_tiff.zip"


def test_geosn_dgm1_and_dom1_use_different_base_urls() -> None:
    dgm_config = SERVICE_PROVIDERS["geosn-sn"]["datasets"]["dgm1"]
    dom_config = SERVICE_PROVIDERS["geosn-sn"]["datasets"]["dom1"]
    assert dgm_config["base_url"] != dom_config["base_url"]
    assert "JCcXyifaNdLDnxZ" in dgm_config["base_url"]
    assert "S6wwnFwX7882sZm" in dom_config["base_url"]


def test_geosn_summarize_tiles_includes_provider_and_dataset() -> None:
    config = SERVICE_PROVIDERS["geosn-sn"]["datasets"]["dom1"]
    summaries = summarize_tiles(
        "dom1",
        config=config,
        geometry="13.74,51.05",
        geometry_type="esriGeometryPoint",
        timeout=1,
    )
    assert len(summaries) == 1
    s = summaries[0]
    assert s["provider"] == "geosn-sn"
    assert s["dataset"] == "dom1"
    assert s["tile_id"].startswith("dom1_33")
    assert s["primary_url"].endswith("_tiff.zip")


GEOSN_DOP20_BASE = "https://geocloud.landesvermessung.sachsen.de/public.php/dav/files/sX3GPcdBMGrfXT9/"


def test_geosn_dop20_uses_correct_token() -> None:
    config = SERVICE_PROVIDERS["geosn-sn"]["datasets"]["dop20"]
    assert "sX3GPcdBMGrfXT9" in config["base_url"]


def test_geosn_dop20_tile_record_uses_dop20rgbi_prefix() -> None:
    # Verified: https://...sX3GPcdBMGrfXT9/dop20rgbi_33278_5590_2_sn_tiff.zip
    from multiplanner_api.geosn import _tile_record
    record = _tile_record("dop20rgbi", 278, 5590, GEOSN_DOP20_BASE)
    assert record["primary_url"] == GEOSN_DOP20_BASE + "dop20rgbi_33278_5590_2_sn_tiff.zip"
    assert record["tile_id"] == "dop20rgbi_33278_5590_2_sn"


def test_geosn_locate_dop20_tiles_uses_rgbi_prefix_in_url() -> None:
    config = SERVICE_PROVIDERS["geosn-sn"]["datasets"]["dop20"]
    tiles = locate_tiles(
        "dop20",
        config=config,
        geometry="13.74,51.05",
        geometry_type="esriGeometryPoint",
        timeout=1,
    )
    assert len(tiles) == 1
    tile = tiles[0]
    assert tile["primary_url"].startswith(GEOSN_DOP20_BASE + "dop20rgbi_33")
    assert tile["primary_url"].endswith("_2_sn_tiff.zip")


def test_geosn_dop20_known_tile_urls_match() -> None:
    # All four tiles verified by user from batch download listing
    from multiplanner_api.geosn import _tile_record
    expected = [
        (278, 5590, "dop20rgbi_33278_5590_2_sn_tiff.zip"),
        (280, 5602, "dop20rgbi_33280_5602_2_sn_tiff.zip"),
        (380, 5626, "dop20rgbi_33380_5626_2_sn_tiff.zip"),
        (502, 5682, "dop20rgbi_33502_5682_2_sn_tiff.zip"),
    ]
    for east_km, north_km, filename in expected:
        record = _tile_record("dop20rgbi", east_km, north_km, GEOSN_DOP20_BASE)
        assert record["primary_url"] == GEOSN_DOP20_BASE + filename
