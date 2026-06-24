from fastapi.testclient import TestClient

from multiplanner_api.main import app


client = TestClient(app)


def test_coordinate_search() -> None:
    response = client.get("/api/v1/search/places", params={"q": "52.324784, 7.467435"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["candidates"][0]["source"] == "coordinates"
    assert payload["candidates"][0]["lon"] == 7.467435
    assert payload["candidates"][0]["lat"] == 52.324784


def test_geocoder_search_route(monkeypatch) -> None:
    def fake_search_places(query: str):
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
