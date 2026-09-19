import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from multiplanner_api.sh import (
    _cache_path,
    _geojson_url,
    _load_index,
    _parse_geojson,
    _tile_shape,
    locate_tiles,
    request_geometry,
    summarize_tiles,
)
from multiplanner_api.providers import SERVICE_PROVIDERS, provider_dataset_names

# Kachel 324246002: UTM32 easting 424-425 km, northing 6002-6003 km (western SH)
SAMPLE_TILE = {
    "kachel": "324246002",
    "link_data": "https://geodaten.schleswig-holstein.de/gaialight-sh/_apps/dladownload/massen.php?file=dgm1_32_424_6002_1_sh_2005.xyz&id=2&live=2005&km=32420_6000",
    "datum": "2005",
    "bbox": [424000.0, 6002000.0, 425000.0, 6003000.0],
}

SAMPLE_LOD2_TILE = {
    "id": "324266004",
    "data_link": "https://geodaten.schleswig-holstein.de/gaialight-sh/_apps/dladownload/massen.php?file=LoD2_32_426_6004_1_SH.xml&id=4&live=2024&km=4260_600400",
    "datum": "2024-06-30",
    "bbox": [426000.0, 6004000.0, 427000.0, 6005000.0],
}

SAMPLE_GEOJSON_FEATURE = {
    "type": "Feature",
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [
                [424000.0, 6002000.0],
                [425000.0, 6002000.0],
                [425000.0, 6003000.0],
                [424000.0, 6003000.0],
                [424000.0, 6002000.0],
            ]
        ],
    },
    "properties": {
        "kachel": "324246002",
        "datum": "2005",
        "link_data": "https://geodaten.schleswig-holstein.de/gaialight-sh/_apps/dladownload/massen.php?file=dgm1_32_424_6002_1_sh_2005.xyz&id=2&live=2005&km=32420_6000",
    },
}

SAMPLE_LOD2_GEOJSON_FEATURE = {
    "type": "Feature",
    "geometry": {
        "type": "Polygon",
        "coordinates": [
            [
                [426000.0, 6004000.0],
                [427000.0, 6004000.0],
                [427000.0, 6005000.0],
                [426000.0, 6005000.0],
                [426000.0, 6004000.0],
            ]
        ],
    },
    "properties": {
        "id": "324266004",
        "datum": "2024-06-30",
        "data_link": "https://geodaten.schleswig-holstein.de/gaialight-sh/_apps/dladownload/massen.php?file=LoD2_32_426_6004_1_SH.xml&id=4&live=2024&km=4260_600400",
    },
}

# WGS84 envelope covering all of Schleswig-Holstein — transforms to UTM32 range
# that includes the sample tile (easting ~424 km, northing ~6002 km)
SH_ENVELOPE = json.dumps({"xmin": 7.5, "ymin": 53.5, "xmax": 12.0, "ymax": 55.5})

# WGS84 envelope for Bavaria — far from SH, must NOT intersect the sample tile
BAVARIA_ENVELOPE = json.dumps({"xmin": 10.0, "ymin": 47.0, "xmax": 14.0, "ymax": 50.0})


def _mock_geojson_response(features):
    return SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"type": "FeatureCollection", "features": features},
    )


# --- provider registry ---

def test_lvermgeo_sh_provider_lists_dgm1_dom1_dop20_lod2() -> None:
    assert provider_dataset_names("lvermgeo-sh") == ("dgm1", "dom1", "dop20", "lod2")


def test_sh_dom1_surface_slot_uses_official_bdom_index() -> None:
    assert "file=bDOM_SH_Massendownload.geojson" in _geojson_url("dom1")


# --- _parse_geojson ---

def test_parse_geojson_extracts_fields() -> None:
    entries = _parse_geojson({"features": [SAMPLE_GEOJSON_FEATURE]})
    assert len(entries) == 1
    e = entries[0]
    assert e["kachel"] == "324246002"
    assert e["datum"] == "2005"
    assert "massen.php" in e["link_data"]
    assert len(e["bbox"]) == 4
    assert e["bbox"][0] == pytest.approx(424000.0)
    assert e["bbox"][2] == pytest.approx(425000.0)


def test_parse_geojson_lod2_uses_id_and_data_link_fields() -> None:
    entries = _parse_geojson({"features": [SAMPLE_LOD2_GEOJSON_FEATURE]},
                             id_field="id", url_field="data_link")
    assert len(entries) == 1
    e = entries[0]
    assert e["id"] == "324266004"
    assert "LoD2_32_426_6004" in e["data_link"]


def test_parse_geojson_skips_feature_without_link_data() -> None:
    bad_feature = {**SAMPLE_GEOJSON_FEATURE,
                   "properties": {"kachel": "324246002", "datum": "2005"}}
    assert _parse_geojson({"features": [bad_feature]}) == []


def test_parse_geojson_skips_feature_without_kachel() -> None:
    bad_feature = {**SAMPLE_GEOJSON_FEATURE,
                   "properties": {"datum": "2005", "link_data": "https://example.com/tile.xyz"}}
    assert _parse_geojson({"features": [bad_feature]}) == []


def test_parse_geojson_empty_collection() -> None:
    assert _parse_geojson({"features": []}) == []


# --- _tile_shape ---

def test_tile_shape_covers_tile_interior() -> None:
    from shapely.geometry import Point
    s = _tile_shape(SAMPLE_TILE)
    assert s.contains(Point(424500.0, 6002500.0))


def test_tile_shape_does_not_cover_outside() -> None:
    from shapely.geometry import Point
    s = _tile_shape(SAMPLE_TILE)
    assert not s.contains(Point(300000.0, 5800000.0))


# --- request_geometry ---

def test_request_geometry_point() -> None:
    geom = request_geometry("9.5,54.3", "esriGeometryPoint")
    assert geom.geom_type == "Point"
    assert abs(geom.x - 9.5) < 1e-9


def test_request_geometry_envelope() -> None:
    geom = request_geometry(SH_ENVELOPE, "esriGeometryEnvelope")
    assert geom.geom_type == "Polygon"


def test_request_geometry_polygon() -> None:
    payload = json.dumps({"rings": [[[8.0, 54.0], [9.0, 54.0], [9.0, 55.0], [8.0, 55.0], [8.0, 54.0]]]})
    geom = request_geometry(payload, "esriGeometryPolygon")
    assert geom.geom_type == "Polygon"


def test_request_geometry_unsupported_type() -> None:
    with pytest.raises(ValueError, match="Unsupported geometry type"):
        request_geometry("{}", "esriGeometryMultipoint")


# --- locate_tiles ---

def test_locate_tiles_returns_matching_dgm1_tile(monkeypatch) -> None:
    monkeypatch.setattr("multiplanner_api.sh._load_index", lambda dataset, *, timeout: [SAMPLE_TILE])
    config = SERVICE_PROVIDERS["lvermgeo-sh"]["datasets"]["dgm1"]
    tiles = locate_tiles("dgm1", config=config, geometry=SH_ENVELOPE,
                         geometry_type="esriGeometryEnvelope", timeout=5)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"] == "sh_dgm1_324246002"
    assert ".xyz" in tiles[0]["primary_url"]
    assert tiles[0]["datum"] == "2005"


def test_locate_tiles_returns_matching_lod2_tile(monkeypatch) -> None:
    monkeypatch.setattr("multiplanner_api.sh._load_index", lambda dataset, *, timeout: [SAMPLE_LOD2_TILE])
    config = SERVICE_PROVIDERS["lvermgeo-sh"]["datasets"]["lod2"]
    tiles = locate_tiles("lod2", config=config, geometry=SH_ENVELOPE,
                         geometry_type="esriGeometryEnvelope", timeout=5)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"] == "sh_lod2_324266004"
    assert "LoD2_32_426_6004" in tiles[0]["primary_url"]


def test_locate_tiles_no_match_outside_state(monkeypatch) -> None:
    monkeypatch.setattr("multiplanner_api.sh._load_index", lambda dataset, *, timeout: [SAMPLE_TILE])
    config = SERVICE_PROVIDERS["lvermgeo-sh"]["datasets"]["dgm1"]
    tiles = locate_tiles("dgm1", config=config, geometry=BAVARIA_ENVELOPE,
                         geometry_type="esriGeometryEnvelope", timeout=5)
    assert tiles == []


def test_locate_tiles_raises_for_oversized_area(monkeypatch) -> None:
    big_index = [
        {**SAMPLE_TILE, "kachel": str(i), "bbox": [400000.0 + i * 1000, 6000000.0, 401000.0 + i * 1000, 6001000.0]}
        for i in range(201)
    ]
    monkeypatch.setattr("multiplanner_api.sh._load_index", lambda dataset, *, timeout: big_index)
    # Bypass CRS transform so UTM32 envelope coords can be used directly
    monkeypatch.setattr("multiplanner_api.sh._to_utm32", lambda g: g)
    big_utm_envelope = json.dumps({"xmin": 399000.0, "ymin": 5999000.0, "xmax": 602000.0, "ymax": 6002000.0})
    config = SERVICE_PROVIDERS["lvermgeo-sh"]["datasets"]["dgm1"]
    with pytest.raises(ValueError, match="201 1 km tiles"):
        locate_tiles("dgm1", config=config, geometry=big_utm_envelope,
                     geometry_type="esriGeometryEnvelope", timeout=5)


# --- summarize_tiles ---

def test_summarize_tiles_has_correct_provider_and_dataset(monkeypatch) -> None:
    monkeypatch.setattr("multiplanner_api.sh._load_index", lambda dataset, *, timeout: [SAMPLE_TILE])
    config = SERVICE_PROVIDERS["lvermgeo-sh"]["datasets"]["dgm1"]
    summaries = summarize_tiles("dgm1", config=config, geometry=SH_ENVELOPE,
                                geometry_type="esriGeometryEnvelope", timeout=5)
    assert len(summaries) == 1
    s = summaries[0]
    assert s["provider"] == "lvermgeo-sh"
    assert s["dataset"] == "dgm1"
    assert s["tile_id"] == "sh_dgm1_324246002"
    assert "geodaten.schleswig-holstein.de" in s["source"]
    assert s["updated"] == "2005"


def test_locate_tiles_returns_matching_dom1_tile(monkeypatch) -> None:
    dom1_tile = {**SAMPLE_TILE,
                 "link_data": "https://geodaten.schleswig-holstein.de/gaialight-sh/_apps/dladownload/massen.php?file=bdom20nc_32_424_6002_1_sh_2024.tif&id=6"}
    monkeypatch.setattr("multiplanner_api.sh._load_index", lambda dataset, *, timeout: [dom1_tile])
    config = SERVICE_PROVIDERS["lvermgeo-sh"]["datasets"]["dom1"]
    tiles = locate_tiles("dom1", config=config, geometry=SH_ENVELOPE,
                         geometry_type="esriGeometryEnvelope", timeout=5)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"] == "sh_dom1_324246002"
    assert "bdom20nc_32_424_6002" in tiles[0]["primary_url"]


def test_summarize_tiles_dop20_has_correct_dataset(monkeypatch) -> None:
    dop_tile = {**SAMPLE_TILE,
                "link_data": "https://geodaten.schleswig-holstein.de/gaialight-sh/_apps/dladownload/massen.php?file=dop20rgbi_32_424_6002_1_sh_2024.tif&id=7"}
    monkeypatch.setattr("multiplanner_api.sh._load_index", lambda dataset, *, timeout: [dop_tile])
    config = SERVICE_PROVIDERS["lvermgeo-sh"]["datasets"]["dop20"]
    summaries = summarize_tiles("dop20", config=config, geometry=SH_ENVELOPE,
                                geometry_type="esriGeometryEnvelope", timeout=5)
    assert len(summaries) == 1
    assert summaries[0]["dataset"] == "dop20"
    assert summaries[0]["tile_id"] == "sh_dop20_324246002"
    assert "dop20rgbi" in summaries[0]["primary_url"]


# --- _load_index cache behaviour ---

def test_load_index_uses_cached_file(monkeypatch, tmp_path) -> None:
    cached = [SAMPLE_TILE]
    cache_file = tmp_path / "geodaten_sh_dgm1.json"
    cache_file.write_text(json.dumps(cached), encoding="utf-8")
    monkeypatch.setattr("multiplanner_api.sh._cache_path", lambda dataset: cache_file)
    fetch_called = []
    monkeypatch.setattr(
        "multiplanner_api.sh.get_with_ssl_fallback",
        lambda *a, **kw: fetch_called.append(1) or _mock_geojson_response([]),
    )
    result = _load_index("dgm1", timeout=5)
    assert fetch_called == []
    assert result == cached


def test_load_index_fetches_when_cache_missing(monkeypatch, tmp_path) -> None:
    cache_file = tmp_path / "geodaten_sh_dgm1.json"
    monkeypatch.setattr("multiplanner_api.sh._cache_path", lambda dataset: cache_file)
    monkeypatch.setattr(
        "multiplanner_api.sh.get_with_ssl_fallback",
        lambda *a, **kw: _mock_geojson_response([SAMPLE_GEOJSON_FEATURE]),
    )
    result = _load_index("dgm1", timeout=5)
    assert len(result) == 1
    assert result[0]["kachel"] == "324246002"
    assert cache_file.exists()


def test_load_index_refetches_stale_cache(monkeypatch, tmp_path) -> None:
    stale = [{"kachel": "old", "link_data": "https://example.com/old.xyz", "datum": "2000", "bbox": [0.0, 0.0, 1.0, 1.0]}]
    cache_file = tmp_path / "geodaten_sh_dgm1.json"
    cache_file.write_text(json.dumps(stale), encoding="utf-8")
    stale_mtime = time.time() - 8 * 24 * 60 * 60  # 8 days old
    import os
    os.utime(cache_file, (stale_mtime, stale_mtime))
    monkeypatch.setattr("multiplanner_api.sh._cache_path", lambda dataset: cache_file)
    monkeypatch.setattr(
        "multiplanner_api.sh.get_with_ssl_fallback",
        lambda *a, **kw: _mock_geojson_response([SAMPLE_GEOJSON_FEATURE]),
    )
    result = _load_index("dgm1", timeout=5)
    assert result[0]["kachel"] == "324246002"
