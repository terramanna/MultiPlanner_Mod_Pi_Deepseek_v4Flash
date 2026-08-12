from fastapi.testclient import TestClient
from types import SimpleNamespace

from multiplanner_api.main import app


client = TestClient(app)


def network_link_feature_collection() -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            site_feature("SITE_A", "Actual Site A", "LTE", "S900001", "Mast;West", [7.0, 52.0]),
            site_feature("SITE_B", "Actual Site B", "LTE_POP", "S900002", "Dach;East", [7.2, 52.2]),
            link_feature("HND_SITE_A_SITE_B", "SITE_A", "SITE_B", "BNA-12345", [[7.0, 52.0], [7.2, 52.2]]),
            link_feature("HND_SITE_A_SITE_B", "SITE_A", "SITE_B", "BNA-12345", [[7.0, 52.0], [7.2, 52.2]]),
        ],
    }


def bounded_link_feature_collection() -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            link_feature("IN_BOUNDS_LINK", "A", "B", "", [[7.0, 52.0], [7.2, 52.2]]),
            link_feature("OUT_OF_BOUNDS_LINK", "C", "D", "", [[11.0, 48.0], [11.2, 48.2]]),
        ],
    }


def site_feature(name: str, label: str, site_type: str, s_number: str, flags: str, coordinates: list[float]) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": coordinates},
        "properties": {
            "layer": "site",
            "name": name,
            "name2": label,
            "site_type": site_type,
            "s_number": s_number,
            "flags": flags,
        },
    }


def link_feature(name: str, site_a: str, site_b: str, link_id: str, coordinates: list[list[float]]) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coordinates},
        "properties": {
            "layer": "link",
            "name": name,
            "site_a": site_a,
            "site_b": site_b,
            "s_number_a": "S900001",
            "s_number_b": "S900002",
            "bnetza_link_id": link_id,
        },
    }


def patch_offline_network_search(monkeypatch, feature_collection: dict) -> None:
    monkeypatch.setattr(
        "multiplanner_api.search.load_settings",
        lambda: SimpleNamespace(
            network_db_path="demo.sqlite",
            geocoder_url="https://example.invalid",
            geocoder_countrycodes="de",
            geocoder_email="",
        ),
    )
    monkeypatch.setattr("multiplanner_api.search.load_network_geojson", lambda _path: feature_collection)


def test_coordinate_search() -> None:
    response = client.get("/api/v1/search/places", params={"q": "52.324784, 7.467435"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["candidates"][0]["source"] == "coordinates"
    assert payload["candidates"][0]["lon"] == 7.467435
    assert payload["candidates"][0]["lat"] == 52.324784


def test_geocoder_search_route(monkeypatch) -> None:
    def fake_search_places(query: str, **kwargs):
        return {
            "query": query,
            "candidates": [
                {
                    "label": "Demo Place, Germany",
                    "lon": 7.4,
                    "lat": 52.3,
                    "source": "nominatim",
                }
            ],
        }

    monkeypatch.setattr("multiplanner_api.main.search_places", fake_search_places)
    response = client.get("/api/v1/search/places", params={"q": "Demo Place"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "Demo Place"
    assert payload["candidates"][0]["source"] == "nominatim"


def test_geocoder_search_route_passes_bounds(monkeypatch) -> None:
    captured = {}

    def fake_search_places(query: str, **kwargs):
        captured["query"] = query
        captured.update(kwargs)
        return {"query": query, "candidates": []}

    monkeypatch.setattr("multiplanner_api.main.search_places", fake_search_places)
    response = client.get(
        "/api/v1/search/places",
        params={"q": "Demo Place", "west": 7.0, "south": 50.0, "east": 8.0, "north": 51.0},
    )
    assert response.status_code == 200
    assert captured == {
        "query": "Demo Place",
        "west": 7.0,
        "south": 50.0,
        "east": 8.0,
        "north": 51.0,
    }


def test_network_link_id_search_works_without_geocoder(monkeypatch) -> None:
    geocoder_calls = []

    def broken_geocoder(*_args, **_kwargs):
        geocoder_calls.append(True)
        raise RuntimeError("offline")

    patch_offline_network_search(monkeypatch, network_link_feature_collection())
    monkeypatch.setattr("multiplanner_api.search.requests.get", broken_geocoder)

    response = client.get("/api/v1/search/places", params={"q": "BNA-12345"})

    payload = response.json()
    assert response.status_code == 200
    assert payload["candidates"][0]["source"] == "network-link"
    assert payload["candidates"][0]["site_a_lon"] == 7.0
    assert payload["candidates"][0]["site_b_lat"] == 52.2
    assert payload["candidates"][0]["link_name"] == "HND_SITE_A_SITE_B"
    assert payload["candidates"][0]["site_a_label"] == "Actual Site A"
    assert payload["candidates"][0]["site_a_structure"] == "Mast"
    assert payload["candidates"][0]["site_b_structure"] == "Dach"
    assert payload["candidates"][0]["distance_m"] > 0
    assert len(payload["candidates"]) == 1
    assert geocoder_calls == []


def test_network_search_falls_back_when_configured_database_is_empty(monkeypatch) -> None:
    fallback = {
        "type": "FeatureCollection",
        "features": [site_feature("01NEUENBUR01", "Neuenbürg", "LTE", "S900001", "Mast", [8.5, 48.8])],
    }
    monkeypatch.setattr(
        "multiplanner_api.search.load_settings",
        lambda: SimpleNamespace(
            network_db_path="empty.sqlite",
            geocoder_url="https://example.invalid",
            geocoder_countrycodes="de",
            geocoder_email="",
        ),
    )
    monkeypatch.setattr(
        "multiplanner_api.search.load_network_geojson",
        lambda _path: {"type": "FeatureCollection", "features": []},
    )
    monkeypatch.setattr("multiplanner_api.search._static_network_geojson", lambda: fallback)
    monkeypatch.setattr(
        "multiplanner_api.search.requests.get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
    )

    response = client.get("/api/v1/search/places", params={"q": "01NEUENBUR01"})

    assert response.status_code == 200
    assert response.json()["candidates"][0]["source"] == "network-site"


def test_network_search_respects_bounds(monkeypatch) -> None:
    patch_offline_network_search(monkeypatch, bounded_link_feature_collection())
    monkeypatch.setattr("multiplanner_api.search.requests.get", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("offline")))

    response = client.get(
        "/api/v1/search/places",
        params={"q": "LINK", "west": 6.5, "south": 51.5, "east": 7.5, "north": 52.5},
    )

    payload = response.json()
    assert response.status_code == 200
    assert [candidate["link_name"] for candidate in payload["candidates"]] == ["IN_BOUNDS_LINK"]
