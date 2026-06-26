import json

import pytest

from multiplanner_api.hb import locate_tiles, summarize_tiles
from multiplanner_api.providers import SERVICE_PROVIDERS, provider_dataset_names

HB_ZIP = (
    "https://gdi2.geo.bremen.de/inspire/download/DGM/data"
    "/Gitternetz_DGM1_2017_HB_ASCII_XYZ.zip"
)
BHV_ZIP = (
    "https://gdi2.geo.bremen.de/inspire/download/DGM/data"
    "/Gitternetz_DGM1_2015_BHV_ASCII_XYZ.zip"
)

# Bremen city centre
BREMEN_POINT = "8.8078,53.0753"
# Bremerhaven city centre
BREMERHAVEN_POINT = "8.5779,53.5500"
# Offshore / outside both cities
OUTSIDE_POINT = "9.5,53.9"

CONFIG = SERVICE_PROVIDERS["lginf-hb"]["datasets"]["dgm1"]


def test_lginf_hb_provider_lists_dgm1_only() -> None:
    assert provider_dataset_names("lginf-hb") == ("dgm1",)


def test_bremen_point_returns_hb_zip() -> None:
    tiles = locate_tiles("dgm1", config=CONFIG, geometry=BREMEN_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"] == "hb_dgm1_HB"
    assert tiles[0]["primary_url"] == HB_ZIP


def test_bremerhaven_point_returns_bhv_zip() -> None:
    tiles = locate_tiles("dgm1", config=CONFIG, geometry=BREMERHAVEN_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"] == "hb_dgm1_BHV"
    assert tiles[0]["primary_url"] == BHV_ZIP


def test_outside_point_returns_no_tiles() -> None:
    tiles = locate_tiles("dgm1", config=CONFIG, geometry=OUTSIDE_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert tiles == []


def test_envelope_spanning_both_cities_returns_two_tiles() -> None:
    geom = json.dumps({
        "xmin": 8.49, "ymin": 52.99, "xmax": 8.63, "ymax": 53.62,
        "spatialReference": {"wkid": 4326},
    })
    tiles = locate_tiles("dgm1", config=CONFIG, geometry=geom,
                         geometry_type="esriGeometryEnvelope", timeout=1)
    ids = {t["tile_id"] for t in tiles}
    assert ids == {"hb_dgm1_HB", "hb_dgm1_BHV"}


def test_polygon_in_bremen_returns_hb_zip() -> None:
    geom = json.dumps({"rings": [[[8.77, 53.05], [8.90, 53.05],
                                   [8.90, 53.15], [8.77, 53.15], [8.77, 53.05]]]})
    tiles = locate_tiles("dgm1", config=CONFIG, geometry=geom,
                         geometry_type="esriGeometryPolygon", timeout=1)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"] == "hb_dgm1_HB"


def test_summarize_tiles_has_correct_fields() -> None:
    summaries = summarize_tiles("dgm1", config=CONFIG, geometry=BREMEN_POINT,
                                geometry_type="esriGeometryPoint", timeout=1)
    assert len(summaries) == 1
    s = summaries[0]
    assert s["provider"] == "lginf-hb"
    assert s["dataset"] == "dgm1"
    assert s["tile_id"] == "hb_dgm1_HB"
    assert s["primary_url"] == HB_ZIP
    assert "gdi2.geo.bremen.de" in s["source"]
