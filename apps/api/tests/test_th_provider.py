"""Tests for the Thüringen TLBG ATOM adapter (th.py)."""

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from shapely.geometry import Point

from multiplanner_api.th import (
    _DATASET_CONFIG,
    _intersecting_tiles,
    _load_index,
    _parse_atom,
    _parse_bbox,
    _parse_coords,
    locate_tiles,
    summarize_tiles,
)
from multiplanner_api.providers import SERVICE_PROVIDERS, provider_dataset_names

_BASE = "https://geoportal.geoportal-th.de"

# Tile 628_5651 is near Erfurt (~11.03°E, ~50.98°N).
# Vintage 2010-2013 appears first; 2020-2025 appears second — dedup must keep 2020-2025.
SAMPLE_DGM_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <link rel="section"
          href="{b}/hoehendaten/DGM/dgm_2010-2013/dgm2_628_5651_1_th_2010-2013.zip"
          type="application/zip" title="628_5651_1x1km"
          bbox="50.970 11.020 50.980 11.040"/>
    <link rel="section"
          href="{b}/hoehendaten/DGM/dgm_2020-2025/dgm2_628_5651_1_th_2020-2025.zip"
          type="application/zip" title="628_5651_1x1km"
          bbox="50.970 11.020 50.980 11.040"/>
    <link rel="section"
          href="{b}/hoehendaten/DGM/dgm_2020-2025/dgm2_630_5651_1_th_2020-2025.zip"
          type="application/zip" title="630_5651_1x1km"
          bbox="50.970 11.040 50.980 11.060"/>
    <link rel="alternate" href="{b}/legend.png" type="image/png"/>
  </entry>
</feed>
""".format(b=_BASE)

SAMPLE_DOM_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <link rel="section"
          href="{b}/hoehendaten/DOM/dom_2020-2025/dom2_628_5651_1_th_2020-2025.zip"
          type="application/zip" title="628_5651_1x1km"
          bbox="50.970 11.020 50.980 11.040"/>
  </entry>
</feed>
""".format(b=_BASE)

# Feed interleaves LoD1 and LoD2 links for the same tile — adapter must skip LoD1.
SAMPLE_LOD2_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <link rel="section"
          href="{b}/3dgebaeude/LoD1/LoD1_32_628_5650_2_TH.zip"
          type="application/zip" title="628_5650_2x2km"
          bbox="50.960 11.010 50.980 11.050"/>
    <link rel="section"
          href="{b}/3dgebaeude/LoD2/LoD2_32_628_5650_2_TH.zip"
          type="application/zip" title="628_5650_2x2km"
          bbox="50.960 11.010 50.980 11.050"/>
    <link rel="alternate" href="{b}/legend.png" type="image/png"/>
  </entry>
</feed>
""".format(b=_BASE)

ERFURT_POINT = "11.03,50.975"   # inside tile 628_5651 bbox and 628_5650 lod2 bbox
OUTSIDE_POINT = "13.40,52.52"   # Berlin — not in the sample index

DGM_CONFIG = SERVICE_PROVIDERS["tlbg-th"]["datasets"]["dgm"]
DOM_CONFIG = SERVICE_PROVIDERS["tlbg-th"]["datasets"]["dom"]
LOD2_CONFIG = SERVICE_PROVIDERS["tlbg-th"]["datasets"]["lod2"]


def _mock_response(xml_text: str):
    return SimpleNamespace(raise_for_status=lambda: None, text=xml_text)


# --- provider registry ---

def test_tlbg_th_provider_lists_dgm_dom_lod2() -> None:
    assert set(provider_dataset_names("tlbg-th")) == {"dgm", "dom", "lod2"}


# --- _parse_bbox ---

def test_parse_bbox_valid() -> None:
    result = _parse_bbox("50.970 11.020 50.980 11.040")
    assert result == pytest.approx((50.970, 11.020, 50.980, 11.040))


def test_parse_bbox_rejects_wrong_count() -> None:
    assert _parse_bbox("50.970 11.020 50.980") is None
    assert _parse_bbox("") is None


# --- _parse_coords ---

def test_parse_coords_dgm() -> None:
    href = f"{_BASE}/hoehendaten/DGM/dgm_2020-2025/dgm2_628_5651_1_th_2020-2025.zip"
    assert _parse_coords(href, "dgm2_") == (628, 5651)


def test_parse_coords_dom() -> None:
    href = f"{_BASE}/hoehendaten/DOM/dom_2020-2025/dom2_561_5609_1_th_2010-2013.zip"
    assert _parse_coords(href, "dom2_") == (561, 5609)


def test_parse_coords_lod2_skips_lod1() -> None:
    lod1 = f"{_BASE}/3dgebaeude/LoD1/LoD1_32_628_5650_2_TH.zip"
    lod2 = f"{_BASE}/3dgebaeude/LoD2/LoD2_32_628_5650_2_TH.zip"
    assert _parse_coords(lod1, "LoD2_32_") is None
    assert _parse_coords(lod2, "LoD2_32_") == (628, 5650)


def test_parse_coords_rejects_non_zip() -> None:
    assert _parse_coords(f"{_BASE}/legend.png", "dgm2_") is None


# --- _parse_atom ---

def test_parse_atom_dgm_deduplicates_vintages() -> None:
    """Tile 628_5651 appears twice (2010-2013 then 2020-2025); last URL wins."""
    entries = _parse_atom(SAMPLE_DGM_XML, "dgm2_")
    tile_628 = [e for e in entries if e["x_km"] == 628 and e["y_km"] == 5651]
    assert len(tile_628) == 1
    assert "2020-2025" in tile_628[0]["url"]


def test_parse_atom_dgm_returns_correct_tile_count() -> None:
    entries = _parse_atom(SAMPLE_DGM_XML, "dgm2_")
    assert len(entries) == 2
    assert {(e["x_km"], e["y_km"]) for e in entries} == {(628, 5651), (630, 5651)}


def test_parse_atom_dom_returns_one_tile() -> None:
    entries = _parse_atom(SAMPLE_DOM_XML, "dom2_")
    assert len(entries) == 1
    assert entries[0]["x_km"] == 628 and entries[0]["y_km"] == 5651


def test_parse_atom_lod2_skips_lod1_links() -> None:
    entries = _parse_atom(SAMPLE_LOD2_XML, "LoD2_32_")
    assert len(entries) == 1
    assert entries[0]["x_km"] == 628 and entries[0]["y_km"] == 5650
    assert "LoD2" in entries[0]["url"]
    assert "LoD1" not in entries[0]["url"]


# --- _intersecting_tiles ---

def test_intersecting_tiles_finds_erfurt_tile() -> None:
    index = [
        {"x_km": 628, "y_km": 5651, "south": 50.970, "west": 11.020,
         "north": 50.980, "east": 11.040,
         "url": f"{_BASE}/hoehendaten/DGM/dgm_2020-2025/dgm2_628_5651_1_th_2020-2025.zip"},
    ]
    tiles = _intersecting_tiles("dgm", Point(11.03, 50.975), index)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"] == "th_dgm_628_5651"
    assert "dgm2_628_5651" in tiles[0]["primary_url"]


def test_intersecting_tiles_outside_returns_empty() -> None:
    index = [
        {"x_km": 628, "y_km": 5651, "south": 50.970, "west": 11.020,
         "north": 50.980, "east": 11.040,
         "url": f"{_BASE}/hoehendaten/DGM/dgm_2020-2025/dgm2_628_5651_1_th_2020-2025.zip"},
    ]
    assert _intersecting_tiles("dgm", Point(13.40, 52.52), index) == []


# --- _load_index ---

def test_load_index_fetches_and_caches(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("multiplanner_api.th._cache_path",
                        lambda ds_cfg: tmp_path / ds_cfg["cache_file"])
    ds_cfg = _DATASET_CONFIG["dgm"]
    with patch("multiplanner_api.th.requests.get",
               return_value=_mock_response(SAMPLE_DGM_XML)):
        index = _load_index(ds_cfg, timeout=5)
    assert any(e["x_km"] == 628 and e["y_km"] == 5651 for e in index)
    assert (tmp_path / "tlbg_th_dgm.json").exists()


def test_load_index_uses_cache_when_fresh(tmp_path, monkeypatch) -> None:
    cache = tmp_path / "tlbg_th_dgm.json"
    entries = [{"x_km": 628, "y_km": 5651, "south": 50.970, "west": 11.020,
                "north": 50.980, "east": 11.040,
                "url": f"{_BASE}/hoehendaten/DGM/dgm_2020-2025/dgm2_628_5651_1_th_2020-2025.zip"}]
    cache.write_text(json.dumps(entries), encoding="utf-8")
    monkeypatch.setattr("multiplanner_api.th._cache_path", lambda _: cache)
    with patch("multiplanner_api.th.requests.get",
               side_effect=AssertionError("should not fetch")):
        index = _load_index(_DATASET_CONFIG["dgm"], timeout=5)
    assert any(e["x_km"] == 628 for e in index)


# --- locate_tiles / summarize_tiles ---

def test_locate_dgm_point_in_erfurt(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("multiplanner_api.th._cache_path",
                        lambda ds_cfg: tmp_path / ds_cfg["cache_file"])
    with patch("multiplanner_api.th.requests.get",
               return_value=_mock_response(SAMPLE_DGM_XML)):
        tiles = locate_tiles("dgm", config=DGM_CONFIG, geometry=ERFURT_POINT,
                             geometry_type="esriGeometryPoint", timeout=5)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"] == "th_dgm_628_5651"
    assert "dgm2_628_5651" in tiles[0]["primary_url"]
    assert "2020-2025" in tiles[0]["primary_url"]


def test_locate_lod2_point_in_erfurt(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("multiplanner_api.th._cache_path",
                        lambda ds_cfg: tmp_path / ds_cfg["cache_file"])
    with patch("multiplanner_api.th.requests.get",
               return_value=_mock_response(SAMPLE_LOD2_XML)):
        tiles = locate_tiles("lod2", config=LOD2_CONFIG, geometry=ERFURT_POINT,
                             geometry_type="esriGeometryPoint", timeout=5)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"] == "th_lod2_628_5650"
    assert "LoD2" in tiles[0]["primary_url"]


def test_locate_tiles_outside_returns_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("multiplanner_api.th._cache_path",
                        lambda ds_cfg: tmp_path / ds_cfg["cache_file"])
    with patch("multiplanner_api.th.requests.get",
               return_value=_mock_response(SAMPLE_DGM_XML)):
        tiles = locate_tiles("dgm", config=DGM_CONFIG, geometry=OUTSIDE_POINT,
                             geometry_type="esriGeometryPoint", timeout=5)
    assert tiles == []


def test_locate_tiles_raises_for_oversized_area(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("multiplanner_api.th._cache_path",
                        lambda ds_cfg: tmp_path / ds_cfg["cache_file"])
    # 201 tiles all covering the query bbox
    big_index = [
        {"x_km": i, "y_km": 5651, "south": 50.0, "west": 9.0, "north": 51.0, "east": 12.0,
         "url": f"{_BASE}/hoehendaten/DGM/dgm_2020-2025/dgm2_{i}_5651_1_th_2020-2025.zip"}
        for i in range(201)
    ]
    with patch("multiplanner_api.th._load_index", return_value=big_index):
        with pytest.raises(ValueError, match="200 tiles"):
            locate_tiles(
                "dgm", config=DGM_CONFIG,
                geometry='{"xmin":9.0,"ymin":50.0,"xmax":12.0,"ymax":51.0}',
                geometry_type="esriGeometryEnvelope",
                timeout=1,
            )


def test_summarize_tiles_has_correct_fields(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("multiplanner_api.th._cache_path",
                        lambda ds_cfg: tmp_path / ds_cfg["cache_file"])
    with patch("multiplanner_api.th.requests.get",
               return_value=_mock_response(SAMPLE_DGM_XML)):
        summaries = summarize_tiles("dgm", config=DGM_CONFIG, geometry=ERFURT_POINT,
                                    geometry_type="esriGeometryPoint", timeout=5)
    assert len(summaries) == 1
    s = summaries[0]
    assert s["provider"] == "tlbg-th"
    assert s["dataset"] == "dgm"
    assert s["tile_id"] == "th_dgm_628_5651"
    assert "geoportal-th.de" in s["source"]


def test_unknown_dataset_raises() -> None:
    with pytest.raises(ValueError, match="Unknown Thüringen dataset"):
        locate_tiles("xyz", config={}, geometry=ERFURT_POINT,
                     geometry_type="esriGeometryPoint", timeout=1)
