import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from shapely.geometry import box

from multiplanner_api.be import (
    _DATASET_CONFIG,
    _intersecting_tiles,
    _load_index,
    _parse_atom,
    _parse_coords,
    locate_tiles,
    summarize_tiles,
)
from multiplanner_api.providers import SERVICE_PROVIDERS, provider_dataset_names

DGM1_BASE = "https://gdi.berlin.de/data/dgm1/atom"
DOM1_BASE = "https://gdi.berlin.de/data/dom/atom"
BDOM_BASE = "https://gdi.berlin.de/data/bdom/atom"

# Tile 390_5818 is in central Berlin (Alexanderplatz ~13.41°E, 52.52°N).
SAMPLE_DGM1_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>ATKIS® DGM (1m-Rasterweite)</title>
  <entry>
    <title>ATKIS® DGM</title>
    <link href="{base}/DGM1_388_5818.zip" rel="section" type="text/csv"/>
    <link href="{base}/DGM1_390_5818.zip" rel="section" type="text/csv"/>
    <link href="{base}/DGM1_390_5820.zip" rel="section" type="text/csv"/>
    <link href="{base}/DGM1_392_5820.zip" rel="section" type="text/csv"/>
    <link href="{base}/2X2_EPSG_25833.gif" rel="alternate" type="gif"/>
  </entry>
</feed>
""".format(base=DGM1_BASE)

SAMPLE_DOM1_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>DOM</title>
  <entry>
    <link href="{base}/DOM1_390_5818.zip" rel="section" type="text/csv"/>
    <link href="{base}/DOM1_392_5820.zip" rel="section" type="text/csv"/>
    <link href="{base}/2X2.gif" rel="alternate" type="gif"/>
  </entry>
</feed>
""".format(base=DOM1_BASE)

SAMPLE_BDOM_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>bDOM</title>
  <entry>
    <link href="{base}/390_5818.zip" rel="section" type="text/csv"/>
    <link href="{base}/392_5820.zip" rel="section" type="text/csv"/>
    <link href="{base}/legend.gif" rel="alternate" type="gif"/>
  </entry>
</feed>
""".format(base=BDOM_BASE)

BERLIN_POINT = "13.41,52.52"

DGM1_CONFIG = SERVICE_PROVIDERS["gdi-be"]["datasets"]["dgm1"]
DOM1_CONFIG = SERVICE_PROVIDERS["gdi-be"]["datasets"]["dom1"]
BDOM_CONFIG = SERVICE_PROVIDERS["gdi-be"]["datasets"]["bdom"]


def _mock_response(xml_text: str):
    return SimpleNamespace(raise_for_status=lambda: None, text=xml_text)


def test_gdi_be_provider_lists_all_datasets() -> None:
    assert set(provider_dataset_names("gdi-be")) == {"dgm1", "dom1", "bdom"}


# --- _parse_coords ---

def test_parse_coords_dgm1() -> None:
    assert _parse_coords(f"{DGM1_BASE}/DGM1_390_5820.zip", "DGM1_") == (390, 5820)
    assert _parse_coords(f"{DGM1_BASE}/DGM1_368_5808.zip", "DGM1_") == (368, 5808)


def test_parse_coords_dom1() -> None:
    assert _parse_coords(f"{DOM1_BASE}/DOM1_390_5818.zip", "DOM1_") == (390, 5818)


def test_parse_coords_bdom() -> None:
    assert _parse_coords(f"{BDOM_BASE}/390_5818.zip", "") == (390, 5818)


def test_parse_coords_rejects_wrong_prefix() -> None:
    assert _parse_coords(f"{DGM1_BASE}/DGM1_390_5820.zip", "DOM1_") is None
    assert _parse_coords(f"{DGM1_BASE}/2X2_EPSG_25833.gif", "DGM1_") is None


# --- _parse_atom ---

def test_parse_atom_dgm1() -> None:
    entries = _parse_atom(SAMPLE_DGM1_XML, "DGM1_")
    assert len(entries) == 4
    coords = {(e["x_km"], e["y_km"]) for e in entries}
    assert coords == {(388, 5818), (390, 5818), (390, 5820), (392, 5820)}


def test_parse_atom_dom1() -> None:
    entries = _parse_atom(SAMPLE_DOM1_XML, "DOM1_")
    assert len(entries) == 2
    assert {(e["x_km"], e["y_km"]) for e in entries} == {(390, 5818), (392, 5820)}


def test_parse_atom_bdom() -> None:
    entries = _parse_atom(SAMPLE_BDOM_XML, "")
    assert len(entries) == 2
    assert {(e["x_km"], e["y_km"]) for e in entries} == {(390, 5818), (392, 5820)}


# --- _intersecting_tiles ---

def test_intersecting_tiles_dgm1_finds_correct_tile() -> None:
    index = {(390, 5818): f"{DGM1_BASE}/DGM1_390_5818.zip",
             (392, 5820): f"{DGM1_BASE}/DGM1_392_5820.zip"}
    geom = box(390_500, 5_818_500, 391_500, 5_819_500)
    tiles = _intersecting_tiles("dgm1", geom, index)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"] == "be_dgm1_390_5818"


def test_intersecting_tiles_dom1_uses_correct_prefix() -> None:
    index = {(390, 5818): f"{DOM1_BASE}/DOM1_390_5818.zip"}
    geom = box(390_500, 5_818_500, 391_500, 5_819_500)
    tiles = _intersecting_tiles("dom1", geom, index)
    assert tiles[0]["tile_id"] == "be_dom1_390_5818"


def test_intersecting_tiles_excludes_missing_index_cells() -> None:
    index = {(390, 5818): f"{DGM1_BASE}/DGM1_390_5818.zip"}
    geom = box(392_000, 5_820_000, 393_000, 5_821_000)
    assert _intersecting_tiles("dgm1", geom, index) == []


# --- _load_index ---

def test_load_index_fetches_and_caches(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("multiplanner_api.be._cache_path",
                        lambda ds_cfg: tmp_path / ds_cfg["cache_file"])
    ds_cfg = _DATASET_CONFIG["dgm1"]
    with patch("multiplanner_api.be.get_with_ssl_fallback",
               return_value=_mock_response(SAMPLE_DGM1_XML)):
        index = _load_index("dgm1", ds_cfg, timeout=5)
    assert (390, 5818) in index
    assert (tmp_path / "gdi_be_dgm1.json").exists()


def test_load_index_uses_cache_when_fresh(tmp_path, monkeypatch) -> None:
    cache = tmp_path / "gdi_be_dgm1.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    entries = [{"x_km": 390, "y_km": 5818, "url": f"{DGM1_BASE}/DGM1_390_5818.zip"}]
    cache.write_text(json.dumps(entries), encoding="utf-8")
    monkeypatch.setattr("multiplanner_api.be._cache_path", lambda _: cache)
    with patch("multiplanner_api.be.get_with_ssl_fallback",
               side_effect=AssertionError("should not fetch")):
        index = _load_index("dgm1", _DATASET_CONFIG["dgm1"], timeout=5)
    assert (390, 5818) in index


# --- locate_tiles / summarize_tiles ---

def test_locate_dgm1_point_in_berlin(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("multiplanner_api.be._cache_path",
                        lambda ds_cfg: tmp_path / ds_cfg["cache_file"])
    with patch("multiplanner_api.be.get_with_ssl_fallback",
               return_value=_mock_response(SAMPLE_DGM1_XML)):
        tiles = locate_tiles("dgm1", config=DGM1_CONFIG, geometry=BERLIN_POINT,
                             geometry_type="esriGeometryPoint", timeout=5)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"].startswith("be_dgm1_")
    assert "dgm1" in tiles[0]["primary_url"]


def test_locate_dom1_point_in_berlin(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("multiplanner_api.be._cache_path",
                        lambda ds_cfg: tmp_path / ds_cfg["cache_file"])
    with patch("multiplanner_api.be.get_with_ssl_fallback",
               return_value=_mock_response(SAMPLE_DOM1_XML)):
        tiles = locate_tiles("dom1", config=DOM1_CONFIG, geometry=BERLIN_POINT,
                             geometry_type="esriGeometryPoint", timeout=5)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"].startswith("be_dom1_")
    assert "dom" in tiles[0]["primary_url"]


def test_locate_bdom_point_in_berlin(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("multiplanner_api.be._cache_path",
                        lambda ds_cfg: tmp_path / ds_cfg["cache_file"])
    with patch("multiplanner_api.be.get_with_ssl_fallback",
               return_value=_mock_response(SAMPLE_BDOM_XML)):
        tiles = locate_tiles("bdom", config=BDOM_CONFIG, geometry=BERLIN_POINT,
                             geometry_type="esriGeometryPoint", timeout=5)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"].startswith("be_bdom_")
    assert "bdom" in tiles[0]["primary_url"]


def test_locate_tiles_outside_berlin_returns_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("multiplanner_api.be._cache_path",
                        lambda ds_cfg: tmp_path / ds_cfg["cache_file"])
    with patch("multiplanner_api.be.get_with_ssl_fallback",
               return_value=_mock_response(SAMPLE_DGM1_XML)):
        tiles = locate_tiles("dgm1", config=DGM1_CONFIG, geometry="11.58,48.14",
                             geometry_type="esriGeometryPoint", timeout=5)
    assert tiles == []


def test_summarize_tiles_has_correct_fields(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("multiplanner_api.be._cache_path",
                        lambda ds_cfg: tmp_path / ds_cfg["cache_file"])
    with patch("multiplanner_api.be.get_with_ssl_fallback",
               return_value=_mock_response(SAMPLE_DGM1_XML)):
        summaries = summarize_tiles("dgm1", config=DGM1_CONFIG, geometry=BERLIN_POINT,
                                    geometry_type="esriGeometryPoint", timeout=5)
    assert len(summaries) == 1
    s = summaries[0]
    assert s["provider"] == "gdi-be"
    assert s["dataset"] == "dgm1"
    assert s["tile_id"].startswith("be_dgm1_")
    assert "gdi.berlin.de" in s["source"]


def test_unknown_dataset_raises() -> None:
    with pytest.raises(ValueError, match="Unknown Berlin dataset"):
        locate_tiles("xyz", config={}, geometry=BERLIN_POINT,
                     geometry_type="esriGeometryPoint", timeout=1)
