import json
from types import SimpleNamespace

import pytest

from multiplanner_api.by import (
    _metalink_urls,
    _request_body,
    locate_tiles,
    request_geometry,
    summarize_tiles,
)
from multiplanner_api.providers import SERVICE_PROVIDERS, provider_dataset_names

BAYERN_POINT = "11.5761,48.1371"

METALINK_DGM = """<?xml version="1.0" encoding="UTF-8"?>
<metalink xmlns="urn:ietf:params:xml:ns:metalink">
  <file name="691_5334.tif">
    <url>https://download1.bayernwolke.de/a/dgm/dgm1/691_5334.tif</url>
    <url>https://download2.bayernwolke.de/a/dgm/dgm1/691_5334.tif</url>
  </file>
  <file name="692_5334.tif">
    <url>https://download1.bayernwolke.de/a/dgm/dgm1/692_5334.tif</url>
  </file>
</metalink>
"""

METALINK_DOM = """<?xml version="1.0" encoding="UTF-8"?>
<metalink xmlns="urn:ietf:params:xml:ns:metalink">
  <file name="32691_5334_20_DOM.tif">
    <url>https://download1.bayernwolke.de/a/dom20/DOM/32691_5334_20_DOM.tif</url>
  </file>
</metalink>
"""

METALINK_DOP = """<?xml version="1.0" encoding="UTF-8"?>
<metalink xmlns="urn:ietf:params:xml:ns:metalink">
  <file name="32691_5334.tif">
    <url>https://download1.bayernwolke.de/a/dop20/data/32691_5334.tif</url>
  </file>
</metalink>
"""

METALINK_BDOM = """<?xml version="1.0" encoding="UTF-8"?>
<metalink xmlns="urn:ietf:params:xml:ns:metalink">
  <file name="690_5334.gml">
    <url>https://download1.bayernwolke.de/a/lod2/citygml/690_5334.gml</url>
  </file>
</metalink>
"""


def fake_response(text: str, status_code: int = 200):
    def raise_for_status():
        if status_code >= 400:
            error = RuntimeError(f"HTTP {status_code}")
            error.response = SimpleNamespace(status_code=status_code, text=text)
            raise error

    return SimpleNamespace(text=text, status_code=status_code, raise_for_status=raise_for_status)


def test_ldbv_by_provider_lists_terrain_surface_and_ortho_datasets() -> None:
    assert provider_dataset_names("ldbv-by") == ("dgm1", "dom1", "dop20", "bdom")


def test_request_geometry_point() -> None:
    geom = request_geometry(BAYERN_POINT, "esriGeometryPoint")
    assert geom.geom_type == "Point"
    assert abs(geom.x - 11.5761) < 1e-9
    assert abs(geom.y - 48.1371) < 1e-9


def test_request_geometry_envelope() -> None:
    payload = json.dumps({"xmin": 11.5, "ymin": 48.1, "xmax": 11.6, "ymax": 48.2})
    geom = request_geometry(payload, "esriGeometryEnvelope")
    assert geom.geom_type == "Polygon"
    assert abs(geom.bounds[0] - 11.5) < 1e-9


def test_request_geometry_polygon() -> None:
    payload = json.dumps({"rings": [[[11.5, 48.1], [11.6, 48.1], [11.6, 48.2], [11.5, 48.2], [11.5, 48.1]]]})
    geom = request_geometry(payload, "esriGeometryPolygon")
    assert geom.geom_type == "Polygon"


def test_request_geometry_unsupported_type() -> None:
    with pytest.raises(ValueError, match="Unsupported Bayern geometry type"):
        request_geometry("{}", "esriGeometryPolyline")


def test_request_body_is_srid_prefixed_wkt() -> None:
    geom = request_geometry(BAYERN_POINT, "esriGeometryPoint")
    body = _request_body(geom)
    assert body.startswith("SRID=25832;POINT")


def test_metalink_urls_extract_tile_ids_and_primary_urls() -> None:
    records = _metalink_urls(METALINK_DGM, "dgm1")
    assert records == [
        {"tile_id": "by_dgm1_691_5334", "primary_url": "https://download1.bayernwolke.de/a/dgm/dgm1/691_5334.tif"},
        {"tile_id": "by_dgm1_692_5334", "primary_url": "https://download1.bayernwolke.de/a/dgm/dgm1/692_5334.tif"},
    ]


def test_locate_tiles_point_geometry_returns_matching_tiles(monkeypatch) -> None:
    captured = {}

    def fake_post(url, *, data, headers, timeout):
        captured["url"] = url
        captured["data"] = data
        captured["headers"] = headers
        return fake_response(METALINK_DGM)

    monkeypatch.setattr("multiplanner_api.by.post_with_ssl_fallback", fake_post)
    config = SERVICE_PROVIDERS["ldbv-by"]["datasets"]["dgm1"]
    tiles = locate_tiles("dgm1", config=config, geometry=BAYERN_POINT, geometry_type="esriGeometryPoint", timeout=5)
    assert captured["url"].endswith("/services/poly2metalink/metalink/dgm1?data=dgm1&service=polygon")
    assert captured["headers"]["Content-Type"] == "text/plain"
    assert captured["data"].startswith("SRID=25832;POINT")
    assert [tile["tile_id"] for tile in tiles] == ["by_dgm1_691_5334", "by_dgm1_692_5334"]


@pytest.mark.parametrize(
    ("dataset", "metalink", "expected_url", "expected_tile_id"),
    [
        ("dom1", METALINK_DOM, "https://geoservices.bayern.de/services/poly2metalink/metalink/dom20dom?data=dom20dom&service=polygon", "by_dom1_32691_5334_20_DOM"),
        ("dop20", METALINK_DOP, "https://geoservices.bayern.de/services/poly2metalink/metalink/dop20rgb?data=dop20rgb&service=polygon", "by_dop20_32691_5334"),
        ("bdom", METALINK_BDOM, "https://geoservices.bayern.de/services/poly2metalink/metalink/lod2?data=lod2&service=polygon", "by_bdom_690_5334"),
    ],
)
def test_locate_tiles_supports_dom_and_ortho_datasets(monkeypatch, dataset, metalink, expected_url, expected_tile_id) -> None:
    captured = {}

    def fake_post(url, *, data, headers, timeout):
        captured["url"] = url
        captured["data"] = data
        captured["headers"] = headers
        return fake_response(metalink)

    monkeypatch.setattr("multiplanner_api.by.post_with_ssl_fallback", fake_post)
    config = SERVICE_PROVIDERS["ldbv-by"]["datasets"][dataset]
    tiles = locate_tiles(dataset, config=config, geometry=BAYERN_POINT, geometry_type="esriGeometryPoint", timeout=5)
    assert captured["url"] == expected_url
    assert captured["headers"]["Content-Type"] == "text/plain"
    assert captured["data"].startswith("SRID=25832;POINT")
    assert tiles == [{"tile_id": expected_tile_id, "primary_url": _metalink_urls(metalink, dataset)[0]["primary_url"]}]


def test_locate_tiles_envelope_geometry(monkeypatch) -> None:
    geom = json.dumps({"xmin": 11.5, "ymin": 48.1, "xmax": 11.6, "ymax": 48.2})
    config = SERVICE_PROVIDERS["ldbv-by"]["datasets"]["dgm1"]

    def fake_post(*_args, **_kwargs):
        return fake_response(METALINK_DGM)

    monkeypatch.setattr("multiplanner_api.by.post_with_ssl_fallback", fake_post)
    tiles = locate_tiles("dgm1", config=config, geometry=geom, geometry_type="esriGeometryEnvelope", timeout=5)
    assert len(tiles) == 2


def test_locate_tiles_returns_empty_list_when_metalink_has_no_files(monkeypatch) -> None:
    monkeypatch.setattr(
        "multiplanner_api.by.post_with_ssl_fallback",
        lambda *_args, **_kwargs: fake_response('<?xml version="1.0"?><metalink xmlns="urn:ietf:params:xml:ns:metalink"></metalink>'),
    )
    config = SERVICE_PROVIDERS["ldbv-by"]["datasets"]["dgm1"]
    tiles = locate_tiles("dgm1", config=config, geometry=BAYERN_POINT, geometry_type="esriGeometryPoint", timeout=5)
    assert tiles == []


def test_locate_tiles_raises_for_oversized_or_out_of_bounds_geometry(monkeypatch) -> None:
    def fake_post(*_args, **_kwargs):
        return fake_response("Geometrie zu groß oder außerhalb der Grenzen.", status_code=400)

    monkeypatch.setattr("multiplanner_api.by.post_with_ssl_fallback", fake_post)
    config = SERVICE_PROVIDERS["ldbv-by"]["datasets"]["dgm1"]
    with pytest.raises(ValueError, match="Bayern selection rejected"):
        locate_tiles("dgm1", config=config, geometry=BAYERN_POINT, geometry_type="esriGeometryPoint", timeout=5)


def test_summarize_tiles_has_correct_provider_and_dataset(monkeypatch) -> None:
    monkeypatch.setattr("multiplanner_api.by.post_with_ssl_fallback", lambda *_args, **_kwargs: fake_response(METALINK_DGM))
    config = SERVICE_PROVIDERS["ldbv-by"]["datasets"]["dgm1"]
    summaries = summarize_tiles("dgm1", config=config, geometry=BAYERN_POINT, geometry_type="esriGeometryPoint", timeout=5)
    assert len(summaries) == 2
    assert summaries[0]["provider"] == "ldbv-by"
    assert summaries[0]["dataset"] == "dgm1"
    assert summaries[0]["source"] == "https://geodaten.bayern.de/opengeodata/OpenDataDetail.html?pn=dgm1&active=DOWNLOAD"


@pytest.mark.parametrize(
    ("dataset", "metalink", "source_url"),
    [
        ("dom1", METALINK_DOM, "https://geodaten.bayern.de/opengeodata/OpenDataDetail.html?pn=dom20&active=DOWNLOAD"),
        ("dop20", METALINK_DOP, "https://geodaten.bayern.de/opengeodata/OpenDataDetail.html?pn=dop20rgb&active=DOWNLOAD"),
        ("bdom", METALINK_BDOM, "https://geodaten.bayern.de/opengeodata/OpenDataDetail.html?pn=lod2&active=MASSENDOWNLOAD"),
    ],
)
def test_summarize_tiles_uses_dataset_specific_sources(monkeypatch, dataset, metalink, source_url) -> None:
    monkeypatch.setattr("multiplanner_api.by.post_with_ssl_fallback", lambda *_args, **_kwargs: fake_response(metalink))
    config = SERVICE_PROVIDERS["ldbv-by"]["datasets"][dataset]
    summaries = summarize_tiles(dataset, config=config, geometry=BAYERN_POINT, geometry_type="esriGeometryPoint", timeout=5)
    assert summaries[0]["provider"] == "ldbv-by"
    assert summaries[0]["dataset"] == dataset
    assert summaries[0]["source"] == source_url
