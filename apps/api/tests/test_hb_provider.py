import json

import pytest

from multiplanner_api.hb import locate_tiles, summarize_tiles
from multiplanner_api.providers import SERVICE_PROVIDERS, provider_dataset_names

_BASE = "https://gdi2.geo.bremen.de/inspire/download"
HB_DGM_ZIP  = f"{_BASE}/DGM/data/Gitternetz_DGM1_2017_HB_ASCII_XYZ.zip"
BHV_DGM_ZIP = f"{_BASE}/DGM/data/Gitternetz_DGM1_2015_BHV_ASCII_XYZ.zip"
HB_DOM_ZIP  = f"{_BASE}/DOM/data/Gitternetz_DOM1_2017_HB_ASCII_XYZ.zip"
BHV_DOM_ZIP = f"{_BASE}/DOM/data/Gitternetz_DOM1_2015_BHV_ASCII_XYZ.zip"
HB_LOD2_ZIP  = f"{_BASE}/LoD/data/LOD2_CITYGML_HB.zip"
BHV_LOD2_ZIP = f"{_BASE}/LoD/data/LOD2_CITYGML_BHV.zip"

BREMEN_POINT      = "8.8078,53.0753"
BREMERHAVEN_POINT = "8.5779,53.5500"
OUTSIDE_POINT     = "9.5,53.9"
BOTH_ENVELOPE = json.dumps({
    "xmin": 8.49, "ymin": 52.99, "xmax": 8.63, "ymax": 53.62,
    "spatialReference": {"wkid": 4326},
})

DGM_CONFIG  = SERVICE_PROVIDERS["lginf-hb"]["datasets"]["dgm1"]
DOM_CONFIG  = SERVICE_PROVIDERS["lginf-hb"]["datasets"]["dom1"]
LOD2_CONFIG = SERVICE_PROVIDERS["lginf-hb"]["datasets"]["lod2"]


def test_lginf_hb_provider_dataset_names() -> None:
    assert provider_dataset_names("lginf-hb") == ("dgm1", "dom1", "lod2")


# --- dgm1 ---

def test_dgm1_bremen_point() -> None:
    tiles = locate_tiles("dgm1", config=DGM_CONFIG, geometry=BREMEN_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"] == "hb_dgm1_HB"
    assert tiles[0]["primary_url"] == HB_DGM_ZIP


def test_dgm1_bremerhaven_point() -> None:
    tiles = locate_tiles("dgm1", config=DGM_CONFIG, geometry=BREMERHAVEN_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert tiles[0]["tile_id"] == "hb_dgm1_BHV"
    assert tiles[0]["primary_url"] == BHV_DGM_ZIP


def test_dgm1_outside_returns_empty() -> None:
    tiles = locate_tiles("dgm1", config=DGM_CONFIG, geometry=OUTSIDE_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert tiles == []


def test_dgm1_envelope_returns_both_cities() -> None:
    tiles = locate_tiles("dgm1", config=DGM_CONFIG, geometry=BOTH_ENVELOPE,
                         geometry_type="esriGeometryEnvelope", timeout=1)
    assert {t["tile_id"] for t in tiles} == {"hb_dgm1_HB", "hb_dgm1_BHV"}


def test_dgm1_polygon_in_bremen() -> None:
    geom = json.dumps({"rings": [[[8.77, 53.05], [8.90, 53.05],
                                   [8.90, 53.15], [8.77, 53.15], [8.77, 53.05]]]})
    tiles = locate_tiles("dgm1", config=DGM_CONFIG, geometry=geom,
                         geometry_type="esriGeometryPolygon", timeout=1)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"] == "hb_dgm1_HB"


def test_summarize_dgm1_fields() -> None:
    summaries = summarize_tiles("dgm1", config=DGM_CONFIG, geometry=BREMEN_POINT,
                                geometry_type="esriGeometryPoint", timeout=1)
    s = summaries[0]
    assert s["provider"] == "lginf-hb"
    assert s["dataset"] == "dgm1"
    assert s["primary_url"] == HB_DGM_ZIP
    assert "gdi2.geo.bremen.de" in s["source"]


# --- dom1 ---

def test_dom1_bremen_point() -> None:
    tiles = locate_tiles("dom1", config=DOM_CONFIG, geometry=BREMEN_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"] == "hb_dom1_HB"
    assert tiles[0]["primary_url"] == HB_DOM_ZIP


def test_dom1_bremerhaven_point() -> None:
    tiles = locate_tiles("dom1", config=DOM_CONFIG, geometry=BREMERHAVEN_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert tiles[0]["tile_id"] == "hb_dom1_BHV"
    assert tiles[0]["primary_url"] == BHV_DOM_ZIP


def test_dom1_outside_returns_empty() -> None:
    tiles = locate_tiles("dom1", config=DOM_CONFIG, geometry=OUTSIDE_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert tiles == []


def test_dom1_envelope_returns_both_cities() -> None:
    tiles = locate_tiles("dom1", config=DOM_CONFIG, geometry=BOTH_ENVELOPE,
                         geometry_type="esriGeometryEnvelope", timeout=1)
    assert {t["tile_id"] for t in tiles} == {"hb_dom1_HB", "hb_dom1_BHV"}


def test_summarize_dom1_fields() -> None:
    summaries = summarize_tiles("dom1", config=DOM_CONFIG, geometry=BREMEN_POINT,
                                geometry_type="esriGeometryPoint", timeout=1)
    s = summaries[0]
    assert s["provider"] == "lginf-hb"
    assert s["dataset"] == "dom1"
    assert s["primary_url"] == HB_DOM_ZIP


# --- lod2 ---

def test_lod2_bremen_point() -> None:
    tiles = locate_tiles("lod2", config=LOD2_CONFIG, geometry=BREMEN_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"] == "hb_lod2_HB"
    assert tiles[0]["primary_url"] == HB_LOD2_ZIP


def test_lod2_bremerhaven_point() -> None:
    tiles = locate_tiles("lod2", config=LOD2_CONFIG, geometry=BREMERHAVEN_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert tiles[0]["tile_id"] == "hb_lod2_BHV"
    assert tiles[0]["primary_url"] == BHV_LOD2_ZIP


def test_lod2_outside_returns_empty() -> None:
    tiles = locate_tiles("lod2", config=LOD2_CONFIG, geometry=OUTSIDE_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert tiles == []


def test_lod2_envelope_returns_both_cities() -> None:
    tiles = locate_tiles("lod2", config=LOD2_CONFIG, geometry=BOTH_ENVELOPE,
                         geometry_type="esriGeometryEnvelope", timeout=1)
    assert {t["tile_id"] for t in tiles} == {"hb_lod2_HB", "hb_lod2_BHV"}


def test_summarize_lod2_fields() -> None:
    summaries = summarize_tiles("lod2", config=LOD2_CONFIG, geometry=BREMEN_POINT,
                                geometry_type="esriGeometryPoint", timeout=1)
    s = summaries[0]
    assert s["provider"] == "lginf-hb"
    assert s["dataset"] == "lod2"
    assert s["primary_url"] == HB_LOD2_ZIP
