import json

import pytest

from multiplanner_api.hb import locate_tiles, summarize_tiles
from multiplanner_api.providers import SERVICE_PROVIDERS, provider_dataset_names

HB_DGM_ZIP = (
    "https://gdi2.geo.bremen.de/inspire/download/DGM/data"
    "/Gitternetz_DGM1_2017_HB_ASCII_XYZ.zip"
)
BHV_DGM_ZIP = (
    "https://gdi2.geo.bremen.de/inspire/download/DGM/data"
    "/Gitternetz_DGM1_2015_BHV_ASCII_XYZ.zip"
)
HB_LOD2_ZIP = "https://gdi2.geo.bremen.de/inspire/download/LoD/data/LOD2_CITYGML_HB.zip"
BHV_LOD2_ZIP = "https://gdi2.geo.bremen.de/inspire/download/LoD/data/LOD2_CITYGML_BHV.zip"

# Bremen city centre
BREMEN_POINT = "8.8078,53.0753"
# Bremerhaven city centre
BREMERHAVEN_POINT = "8.5779,53.5500"
# Offshore / outside both cities
OUTSIDE_POINT = "9.5,53.9"

DGM_CONFIG = SERVICE_PROVIDERS["lginf-hb"]["datasets"]["dgm1"]
LOD2_CONFIG = SERVICE_PROVIDERS["lginf-hb"]["datasets"]["lod2"]


def test_lginf_hb_provider_dataset_names() -> None:
    assert provider_dataset_names("lginf-hb") == ("dgm1", "lod2")


# --- dgm1 tests ---

def test_bremen_point_returns_hb_dgm_zip() -> None:
    tiles = locate_tiles("dgm1", config=DGM_CONFIG, geometry=BREMEN_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"] == "hb_dgm1_HB"
    assert tiles[0]["primary_url"] == HB_DGM_ZIP


def test_bremerhaven_point_returns_bhv_dgm_zip() -> None:
    tiles = locate_tiles("dgm1", config=DGM_CONFIG, geometry=BREMERHAVEN_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"] == "hb_dgm1_BHV"
    assert tiles[0]["primary_url"] == BHV_DGM_ZIP


def test_outside_point_returns_no_dgm_tiles() -> None:
    tiles = locate_tiles("dgm1", config=DGM_CONFIG, geometry=OUTSIDE_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert tiles == []


def test_envelope_spanning_both_cities_returns_two_dgm_tiles() -> None:
    geom = json.dumps({
        "xmin": 8.49, "ymin": 52.99, "xmax": 8.63, "ymax": 53.62,
        "spatialReference": {"wkid": 4326},
    })
    tiles = locate_tiles("dgm1", config=DGM_CONFIG, geometry=geom,
                         geometry_type="esriGeometryEnvelope", timeout=1)
    ids = {t["tile_id"] for t in tiles}
    assert ids == {"hb_dgm1_HB", "hb_dgm1_BHV"}


def test_polygon_in_bremen_returns_hb_dgm_zip() -> None:
    geom = json.dumps({"rings": [[[8.77, 53.05], [8.90, 53.05],
                                   [8.90, 53.15], [8.77, 53.15], [8.77, 53.05]]]})
    tiles = locate_tiles("dgm1", config=DGM_CONFIG, geometry=geom,
                         geometry_type="esriGeometryPolygon", timeout=1)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"] == "hb_dgm1_HB"


def test_summarize_dgm1_has_correct_fields() -> None:
    summaries = summarize_tiles("dgm1", config=DGM_CONFIG, geometry=BREMEN_POINT,
                                geometry_type="esriGeometryPoint", timeout=1)
    assert len(summaries) == 1
    s = summaries[0]
    assert s["provider"] == "lginf-hb"
    assert s["dataset"] == "dgm1"
    assert s["tile_id"] == "hb_dgm1_HB"
    assert s["primary_url"] == HB_DGM_ZIP
    assert "gdi2.geo.bremen.de" in s["source"]


# --- lod2 tests ---

def test_bremen_point_returns_hb_lod2_zip() -> None:
    tiles = locate_tiles("lod2", config=LOD2_CONFIG, geometry=BREMEN_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"] == "hb_lod2_HB"
    assert tiles[0]["primary_url"] == HB_LOD2_ZIP


def test_bremerhaven_point_returns_bhv_lod2_zip() -> None:
    tiles = locate_tiles("lod2", config=LOD2_CONFIG, geometry=BREMERHAVEN_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"] == "hb_lod2_BHV"
    assert tiles[0]["primary_url"] == BHV_LOD2_ZIP


def test_outside_point_returns_no_lod2_tiles() -> None:
    tiles = locate_tiles("lod2", config=LOD2_CONFIG, geometry=OUTSIDE_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert tiles == []


def test_envelope_spanning_both_cities_returns_two_lod2_tiles() -> None:
    geom = json.dumps({
        "xmin": 8.49, "ymin": 52.99, "xmax": 8.63, "ymax": 53.62,
        "spatialReference": {"wkid": 4326},
    })
    tiles = locate_tiles("lod2", config=LOD2_CONFIG, geometry=geom,
                         geometry_type="esriGeometryEnvelope", timeout=1)
    ids = {t["tile_id"] for t in tiles}
    assert ids == {"hb_lod2_HB", "hb_lod2_BHV"}


def test_summarize_lod2_has_correct_fields() -> None:
    summaries = summarize_tiles("lod2", config=LOD2_CONFIG, geometry=BREMEN_POINT,
                                geometry_type="esriGeometryPoint", timeout=1)
    assert len(summaries) == 1
    s = summaries[0]
    assert s["provider"] == "lginf-hb"
    assert s["dataset"] == "lod2"
    assert s["tile_id"] == "hb_lod2_HB"
    assert s["primary_url"] == HB_LOD2_ZIP
    assert "gdi2.geo.bremen.de" in s["source"]
