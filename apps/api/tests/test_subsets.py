from fastapi.testclient import TestClient

from multiplanner_api.main import app


client = TestClient(app)


def test_list_providers() -> None:
    response = client.get("/api/v1/providers")
    assert response.status_code == 200
    payload = response.json()
    assert payload["providers"][0]["name"] == "lgln-ni"


def test_subset_route_uses_service(monkeypatch) -> None:
    def fake_locate_subsets(request):
        return {
            "provider": request.provider,
            "geometry_kind": request.geometry.kind,
            "results": [
                {
                    "dataset": "dgm1",
                    "match_count": 1,
                    "tiles": [
                        {
                            "provider": request.provider,
                            "dataset": "dgm1",
                            "tile_id": "fake-tile",
                            "updated": None,
                            "primary_url": "https://example.invalid/fake.tif",
                            "metadata": {"metadata": "https://example.invalid/meta"},
                        }
                    ],
                }
            ],
        }

    monkeypatch.setattr("multiplanner_api.main.locate_subsets", fake_locate_subsets)
    response = client.post(
        "/api/v1/subsets/locate",
        json={
            "provider": "lgln-ni",
            "datasets": ["dgm1"],
            "geometry": {
                "kind": "point",
                "lon": 7.467435,
                "lat": 52.324784,
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "lgln-ni"
    assert payload["geometry_kind"] == "point"
    assert payload["results"][0]["match_count"] == 1


def test_download_route_uses_service(monkeypatch) -> None:
    def fake_download_subset(request):
        return {
            "provider": request.provider,
            "selection_name": request.selection_name or "demo",
            "export_profile": request.export_profile,
            "output_dir": "data/cache/saved_subsets/demo",
            "file_count": 1,
            "files": [
                {
                    "dataset": "dgm1",
                    "tile_id": "fake-tile",
                    "source_url": "https://example.invalid/fake.tif",
                    "saved_path": "data/cache/saved_subsets/demo/dgm1/fake-tile.tif",
                }
            ],
            "exports": [
                "data/cache/saved_subsets/demo/ellipse_export/dgm1.tif",
                "data/cache/saved_subsets/demo/ellipse_export/dgm1.TAB",
            ],
        }

    monkeypatch.setattr("multiplanner_api.main.download_subset", fake_download_subset)
    response = client.post(
        "/api/v1/subsets/download",
        json={
            "provider": "lgln-ni",
            "datasets": ["dgm1"],
            "selection_name": "demo-corridor",
            "export_profile": "ellipse_mapinfo_tab",
            "geometry": {
                "kind": "corridor",
                "from_lon": 7.46,
                "from_lat": 52.32,
                "to_lon": 7.47,
                "to_lat": 52.33,
                "buffer_m": 75,
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["selection_name"] == "demo-corridor"
    assert payload["file_count"] == 1
    assert payload["export_profile"] == "ellipse_mapinfo_tab"
    assert payload["exports"][1].endswith(".TAB")
