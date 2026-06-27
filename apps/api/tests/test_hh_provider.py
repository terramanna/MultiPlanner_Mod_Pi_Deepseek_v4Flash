import json
from types import SimpleNamespace

import pytest

from multiplanner_api.hh import (
    _ensure_bbox_extent,
    _query_ogc_api,
    _tile_record,
    locate_tiles,
    request_geometry,
    summarize_tiles,
)
from multiplanner_api.providers import SERVICE_PROVIDERS, provider_dataset_names

DAV_BASE = "https://daten-hamburg.de/DAV/DGM1"

SAMPLE_FEATURE = {
    "type": "Feature",
    "id": 79,
    "geometry": None,
    "properties": {
        "kachel": "5828",
        "dateiname_dgm_1": "DGM1_32558_5928_2_FHH.xyz",
        "dateiname_dgm_10": "DGM10_32558_5928_2_FHH.xyz",
    },
}

HAMBURG_POINT = "10.0,53.55"


def _mock_response(features):
    return SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"type": "FeatureCollection", "features": features},
    )


def test_lgv_hh_provider_lists_datasets() -> None:
    assert provider_dataset_names("lgv-hh") == ("dgm1", "bdom", "lod2")


def test_tile_record_url_and_id() -> None:
    record = _tile_record(SAMPLE_FEATURE["properties"])
    assert record["tile_id"] == "hh_dgm1_DGM1_32558_5928_2_FHH"
    assert record["primary_url"] == f"{DAV_BASE}/DGM1_32558_5928_2_FHH.xyz"


def test_request_geometry_point() -> None:
    geom = request_geometry("10.0,53.55", "esriGeometryPoint")
    assert geom.geom_type == "Point"
    assert abs(geom.x - 10.0) < 1e-9
    assert abs(geom.y - 53.55) < 1e-9


def test_request_geometry_envelope() -> None:
    payload = json.dumps({"xmin": 9.9, "ymin": 53.4, "xmax": 10.1, "ymax": 53.6})
    geom = request_geometry(payload, "esriGeometryEnvelope")
    assert geom.geom_type == "Polygon"
    assert abs(geom.bounds[0] - 9.9) < 1e-9


def test_request_geometry_polygon() -> None:
    payload = json.dumps({"rings": [[[9.9, 53.4], [10.1, 53.4], [10.1, 53.6], [9.9, 53.6], [9.9, 53.4]]]})
    geom = request_geometry(payload, "esriGeometryPolygon")
    assert geom.geom_type == "Polygon"


def test_ensure_bbox_extent_expands_point() -> None:
    w, s, e, n = _ensure_bbox_extent(10.0, 53.5, 10.0, 53.5)
    assert e > w
    assert n > s


def test_ensure_bbox_extent_leaves_real_bbox_unchanged() -> None:
    result = _ensure_bbox_extent(9.9, 53.4, 10.1, 53.6)
    assert result == (9.9, 53.4, 10.1, 53.6)


def test_query_ogc_api_passes_bbox_param(monkeypatch) -> None:
    captured = {}

    def fake_get(url, *, params, timeout):
        captured["url"] = url
        captured["params"] = params
        return _mock_response([SAMPLE_FEATURE])

    monkeypatch.setattr("multiplanner_api.hh.requests.get", fake_get)
    features = _query_ogc_api(9.9, 53.4, 10.1, 53.6, timeout=5)
    assert features == [SAMPLE_FEATURE]
    assert "9.9" in captured["params"]["bbox"]
    assert captured["params"]["f"] == "json"


def test_locate_tiles_point_geometry_returns_one_tile(monkeypatch) -> None:
    monkeypatch.setattr(
        "multiplanner_api.hh.requests.get",
        lambda *a, **kw: _mock_response([SAMPLE_FEATURE]),
    )
    config = SERVICE_PROVIDERS["lgv-hh"]["datasets"]["dgm1"]
    tiles = locate_tiles("dgm1", config=config, geometry=HAMBURG_POINT,
                         geometry_type="esriGeometryPoint", timeout=5)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"] == "hh_dgm1_DGM1_32558_5928_2_FHH"
    assert tiles[0]["primary_url"].endswith(".xyz")


def test_locate_tiles_envelope_geometry(monkeypatch) -> None:
    two_features = [SAMPLE_FEATURE, {**SAMPLE_FEATURE, "id": 80,
                    "properties": {**SAMPLE_FEATURE["properties"],
                                   "dateiname_dgm_1": "DGM1_32560_5928_2_FHH.xyz"}}]
    monkeypatch.setattr(
        "multiplanner_api.hh.requests.get",
        lambda *a, **kw: _mock_response(two_features),
    )
    geom = json.dumps({"xmin": 9.9, "ymin": 53.4, "xmax": 10.2, "ymax": 53.6})
    config = SERVICE_PROVIDERS["lgv-hh"]["datasets"]["dgm1"]
    tiles = locate_tiles("dgm1", config=config, geometry=geom,
                         geometry_type="esriGeometryEnvelope", timeout=5)
    assert len(tiles) == 2


def test_summarize_tiles_has_correct_provider_and_dataset(monkeypatch) -> None:
    monkeypatch.setattr(
        "multiplanner_api.hh.requests.get",
        lambda *a, **kw: _mock_response([SAMPLE_FEATURE]),
    )
    config = SERVICE_PROVIDERS["lgv-hh"]["datasets"]["dgm1"]
    summaries = summarize_tiles("dgm1", config=config, geometry=HAMBURG_POINT,
                                geometry_type="esriGeometryPoint", timeout=5)
    assert len(summaries) == 1
    s = summaries[0]
    assert s["provider"] == "lgv-hh"
    assert s["dataset"] == "dgm1"
    assert s["tile_id"].startswith("hh_dgm1_")
    assert "daten-hamburg.de" in s["source"]


def test_locate_tiles_raises_for_oversized_area(monkeypatch) -> None:
    big_response = [
        {**SAMPLE_FEATURE, "id": i,
         "properties": {**SAMPLE_FEATURE["properties"],
                        "dateiname_dgm_1": f"DGM1_32{500+i}_{5900+i}_2_FHH.xyz"}}
        for i in range(101)
    ]
    monkeypatch.setattr(
        "multiplanner_api.hh.requests.get",
        lambda *a, **kw: _mock_response(big_response),
    )
    config = SERVICE_PROVIDERS["lgv-hh"]["datasets"]["dgm1"]
    with pytest.raises(ValueError, match="100 tiles"):
        locate_tiles("dgm1", config=config, geometry=HAMBURG_POINT,
                     geometry_type="esriGeometryPoint", timeout=5)


# --- bdom (bulk single-file) ---

BDOM_URL = "https://daten-hamburg.de/opendata/Digitales_Hoehenmodell_bDOM/dom1_hh_2022-11-21.zip"
LOD2_URL = "https://archiv.transparenz.hamburg.de/hmbtgarchive/HMDK/lod2-de_hh_2016-11-22_21283_snap_1.GML"


def test_bdom_hamburg_point_returns_one_tile() -> None:
    config = SERVICE_PROVIDERS["lgv-hh"]["datasets"]["bdom"]
    tiles = locate_tiles("bdom", config=config, geometry=HAMBURG_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"] == "hh_bdom_HH"
    assert tiles[0]["primary_url"] == BDOM_URL


def test_bdom_outside_hamburg_returns_empty() -> None:
    config = SERVICE_PROVIDERS["lgv-hh"]["datasets"]["bdom"]
    outside = "8.5,51.0"  # Frankfurt area
    tiles = locate_tiles("bdom", config=config, geometry=outside,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert tiles == []


def test_summarize_bdom_has_correct_fields() -> None:
    config = SERVICE_PROVIDERS["lgv-hh"]["datasets"]["bdom"]
    summaries = summarize_tiles("bdom", config=config, geometry=HAMBURG_POINT,
                                geometry_type="esriGeometryPoint", timeout=1)
    assert len(summaries) == 1
    s = summaries[0]
    assert s["provider"] == "lgv-hh"
    assert s["dataset"] == "bdom"
    assert s["tile_id"] == "hh_bdom_HH"
    assert s["primary_url"] == BDOM_URL


# --- lod2 (bulk single-file) ---

def test_lod2_hamburg_point_returns_one_tile() -> None:
    config = SERVICE_PROVIDERS["lgv-hh"]["datasets"]["lod2"]
    tiles = locate_tiles("lod2", config=config, geometry=HAMBURG_POINT,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert len(tiles) == 1
    assert tiles[0]["tile_id"] == "hh_lod2_HH"
    assert tiles[0]["primary_url"] == LOD2_URL


def test_lod2_outside_hamburg_returns_empty() -> None:
    config = SERVICE_PROVIDERS["lgv-hh"]["datasets"]["lod2"]
    outside = "8.5,51.0"
    tiles = locate_tiles("lod2", config=config, geometry=outside,
                         geometry_type="esriGeometryPoint", timeout=1)
    assert tiles == []


def test_summarize_lod2_has_correct_fields() -> None:
    config = SERVICE_PROVIDERS["lgv-hh"]["datasets"]["lod2"]
    summaries = summarize_tiles("lod2", config=config, geometry=HAMBURG_POINT,
                                geometry_type="esriGeometryPoint", timeout=1)
    assert len(summaries) == 1
    s = summaries[0]
    assert s["provider"] == "lgv-hh"
    assert s["dataset"] == "lod2"
    assert s["tile_id"] == "hh_lod2_HH"
    assert s["primary_url"] == LOD2_URL
