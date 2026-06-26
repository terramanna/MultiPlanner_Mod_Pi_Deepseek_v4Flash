import json
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from multiplanner_api.be import (
    _cache_path,
    _intersecting_tiles,
    _load_index,
    _parse_atom,
    _parse_coords,
    locate_tiles,
    summarize_tiles,
)
from multiplanner_api.providers import SERVICE_PROVIDERS, provider_dataset_names

ATOM_BASE = "https://gdi.berlin.de/data/dgm1/atom"

# Tile 390_5820 is in central Berlin (EPSG:25833 x~390000-392000, y~5820000-5822000).
SAMPLE_ATOM_XML = """\
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
""".format(base=ATOM_BASE)

# WGS84 point at Berlin Mitte (Alexanderplatz ~13.41°E, 52.52°N)
BERLIN_POINT = "13.41,52.52"

CONFIG = SERVICE_PROVIDERS["gdi-be"]["datasets"]["dgm1"]


def _mock_atom_response():
    return SimpleNamespace(
        raise_for_status=lambda: None,
        text=SAMPLE_ATOM_XML,
    )


def test_gdi_be_provider_lists_dgm1_only() -> None:
    assert provider_dataset_names("gdi-be") == ("dgm1",)


def test_parse_coords_valid_url() -> None:
    assert _parse_coords(f"{ATOM_BASE}/DGM1_390_5820.zip") == (390, 5820)
    assert _parse_coords(f"{ATOM_BASE}/DGM1_368_5808.zip") == (368, 5808)


def test_parse_coords_invalid_url() -> None:
    assert _parse_coords(f"{ATOM_BASE}/2X2_EPSG_25833.gif") is None
    assert _parse_coords("https://example.com/other.zip") is None


def test_parse_atom_extracts_section_links() -> None:
    entries = _parse_atom(SAMPLE_ATOM_XML)
    assert len(entries) == 4
    coords = {(e["x_km"], e["y_km"]) for e in entries}
    assert coords == {(388, 5818), (390, 5818), (390, 5820), (392, 5820)}
    urls = {e["url"] for e in entries}
    assert f"{ATOM_BASE}/DGM1_390_5818.zip" in urls


def test_intersecting_tiles_finds_matching_tile() -> None:
    index = {(388, 5818): f"{ATOM_BASE}/DGM1_388_5818.zip",
             (390, 5820): f"{ATOM_BASE}/DGM1_390_5820.zip",
             (392, 5822): f"{ATOM_BASE}/DGM1_392_5822.zip"}
    from shapely.geometry import box
    # A box squarely inside tile (390, 5820): x=[390000,392000], y=[5820000,5822000]
    geom = box(390_500, 5_820_500, 391_500, 5_821_500)
    tiles = _intersecting_tiles(geom, index)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"] == "be_dgm1_390_5820"
    assert tiles[0]["primary_url"] == f"{ATOM_BASE}/DGM1_390_5820.zip"


def test_intersecting_tiles_excludes_non_index_cells() -> None:
    index = {(390, 5820): f"{ATOM_BASE}/DGM1_390_5820.zip"}
    from shapely.geometry import box
    # Box that would touch (388, 5818) — not in index → not returned
    geom = box(388_000, 5_818_000, 389_000, 5_819_000)
    tiles = _intersecting_tiles(geom, index)
    assert tiles == []


def test_load_index_parses_atom_when_no_cache(tmp_path, monkeypatch) -> None:
    cache = tmp_path / "gdi_be_dgm1.json"
    monkeypatch.setattr("multiplanner_api.be._cache_path", lambda: cache)
    with patch("multiplanner_api.be.requests.get", return_value=_mock_atom_response()):
        index = _load_index(timeout=5)
    assert (390, 5820) in index
    assert cache.exists()


def test_load_index_uses_cache_when_fresh(tmp_path, monkeypatch) -> None:
    cache = tmp_path / "gdi_be_dgm1.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    entries = [{"x_km": 390, "y_km": 5818, "url": f"{ATOM_BASE}/DGM1_390_5818.zip"}]
    cache.write_text(json.dumps(entries), encoding="utf-8")
    monkeypatch.setattr("multiplanner_api.be._cache_path", lambda: cache)
    with patch("multiplanner_api.be.requests.get", side_effect=AssertionError("should not fetch")):
        index = _load_index(timeout=5)
    assert (390, 5818) in index


def test_locate_tiles_point_in_berlin(monkeypatch, tmp_path) -> None:
    cache = tmp_path / "gdi_be_dgm1.json"
    monkeypatch.setattr("multiplanner_api.be._cache_path", lambda: cache)
    with patch("multiplanner_api.be.requests.get", return_value=_mock_atom_response()):
        tiles = locate_tiles(
            "dgm1",
            config=CONFIG,
            geometry=BERLIN_POINT,
            geometry_type="esriGeometryPoint",
            timeout=5,
        )
    assert len(tiles) == 1
    assert tiles[0]["tile_id"].startswith("be_dgm1_")
    assert "gdi.berlin.de" in tiles[0]["primary_url"]


def test_locate_tiles_envelope_may_return_multiple(monkeypatch, tmp_path) -> None:
    cache = tmp_path / "gdi_be_dgm1.json"
    monkeypatch.setattr("multiplanner_api.be._cache_path", lambda: cache)
    geom = json.dumps({"xmin": 13.38, "ymin": 52.50, "xmax": 13.45, "ymax": 52.54,
                        "spatialReference": {"wkid": 4326}})
    with patch("multiplanner_api.be.requests.get", return_value=_mock_atom_response()):
        tiles = locate_tiles(
            "dgm1",
            config=CONFIG,
            geometry=geom,
            geometry_type="esriGeometryEnvelope",
            timeout=5,
        )
    assert len(tiles) >= 1


def test_locate_tiles_outside_berlin_returns_empty(monkeypatch, tmp_path) -> None:
    cache = tmp_path / "gdi_be_dgm1.json"
    monkeypatch.setattr("multiplanner_api.be._cache_path", lambda: cache)
    # Munich — far from Berlin tiles in sample ATOM
    geom = "11.58,48.14"
    with patch("multiplanner_api.be.requests.get", return_value=_mock_atom_response()):
        tiles = locate_tiles(
            "dgm1",
            config=CONFIG,
            geometry=geom,
            geometry_type="esriGeometryPoint",
            timeout=5,
        )
    assert tiles == []


def test_summarize_tiles_has_correct_fields(monkeypatch, tmp_path) -> None:
    cache = tmp_path / "gdi_be_dgm1.json"
    monkeypatch.setattr("multiplanner_api.be._cache_path", lambda: cache)
    with patch("multiplanner_api.be.requests.get", return_value=_mock_atom_response()):
        summaries = summarize_tiles(
            "dgm1",
            config=CONFIG,
            geometry=BERLIN_POINT,
            geometry_type="esriGeometryPoint",
            timeout=5,
        )
    assert len(summaries) == 1
    s = summaries[0]
    assert s["provider"] == "gdi-be"
    assert s["dataset"] == "dgm1"
    assert s["tile_id"].startswith("be_dgm1_")
    assert "gdi.berlin.de" in s["source"]
