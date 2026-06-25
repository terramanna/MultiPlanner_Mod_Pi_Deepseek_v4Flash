from pathlib import Path
from types import SimpleNamespace

import requests
from fastapi.testclient import TestClient

from multiplanner_api.downloads import download_subset
from multiplanner_api.main import app
from multiplanner_api.models import CorridorGeometryInput, DownloadSubsetRequest, LocateSubsetRequest
from multiplanner_api.subsets import locate_subsets


client = TestClient(app)


def point_payload() -> dict[str, object]:
    return {"provider": "lgln-ni", "datasets": ["dgm1"], "geometry": {"kind": "point", "lon": 7.467435, "lat": 52.324784}}


def corridor_geometry() -> CorridorGeometryInput:
    return CorridorGeometryInput(kind="corridor", from_lon=7.419522, from_lat=52.330475, to_lon=7.695833, to_lat=52.296389)


def corridor_download_request(selection_name: str) -> DownloadSubsetRequest:
    return DownloadSubsetRequest(provider="geobasis-nrw", datasets=["dgm1"], selection_name=selection_name, geometry=corridor_geometry())


def tile_dict(provider: str, dataset: str) -> dict[str, object]:
    return {"provider": provider, "dataset": dataset, "tile_id": f"{provider}-{dataset}", "updated": None, "primary_url": f"https://example.invalid/{provider}/{dataset}.tif"}


def single_tile_response() -> SimpleNamespace:
    tile = SimpleNamespace(tile_id="tile-a", primary_url="https://example.invalid/tile-a.tif")
    return SimpleNamespace(results=[SimpleNamespace(dataset="dgm1", tiles=[tile])])


def fake_locate_response(request) -> dict[str, object]:
    return {"provider": request.provider, "geometry_kind": request.geometry.kind, "results": [fake_dataset_result(request.provider)]}


def fake_dataset_result(provider: str) -> dict[str, object]:
    return {"dataset": "dgm1", "match_count": 1, "tiles": [{"provider": provider, "dataset": "dgm1", "tile_id": "fake-tile", "updated": None, "primary_url": "https://example.invalid/fake.tif", "metadata": {}}]}


def fake_download_response(request) -> dict[str, object]:
    return {
        "provider": request.provider,
        "selection_name": request.selection_name or "demo",
        "export_profile": request.export_profile,
        "output_dir": "data/cache/saved_subsets/demo",
        "file_count": 1,
        "files": [{"provider": "lgln-ni", "dataset": "dgm1", "tile_id": "fake-tile", "source_url": "https://example.invalid/fake.tif", "saved_path": "data/cache/saved_subsets/demo/dgm1/fake-tile.tif"}],
        "exports": ["data/cache/saved_subsets/demo/ellipse_export/dgm1.tif", "data/cache/saved_subsets/demo/ellipse_export/dgm1.TAB"],
    }


def patch_download_settings(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("multiplanner_api.downloads.load_settings", lambda: SimpleNamespace(cache_root=str(tmp_path / "cache"), ellipse_gdal_dir="unused"))
    monkeypatch.setattr("multiplanner_api.downloads.locate_subsets", lambda request: single_tile_response())


def test_list_providers() -> None:
    response = client.get("/api/v1/providers")
    assert response.status_code == 200
    payload = response.json()
    assert payload["providers"][0]["name"] == "auto"
    assert "lgln-ni" in [provider["name"] for provider in payload["providers"]]


def test_subset_route_uses_service(monkeypatch) -> None:
    monkeypatch.setattr("multiplanner_api.main.locate_subsets", fake_locate_response)
    response = client.post("/api/v1/subsets/locate", json=point_payload())
    payload = response.json()
    assert response.status_code == 200
    assert payload["provider"] == "lgln-ni"
    assert payload["geometry_kind"] == "point"
    assert payload["results"][0]["match_count"] == 1


def test_download_route_uses_service(monkeypatch) -> None:
    payload = {**point_payload(), "selection_name": "demo-corridor", "export_profile": "ellipse_mapinfo_tab", "geometry": corridor_geometry().model_dump()}
    monkeypatch.setattr("multiplanner_api.main.download_subset", fake_download_response)
    response = client.post("/api/v1/subsets/download", json=payload)
    body = response.json()
    assert response.status_code == 200
    assert body["selection_name"] == "demo-corridor"
    assert body["file_count"] == 1
    assert body["export_profile"] == "ellipse_mapinfo_tab"
    assert body["exports"][1].endswith(".TAB")


def test_open_folder_route_opens_cache_folder(monkeypatch, tmp_path) -> None:
    opened = []
    monkeypatch.setattr("multiplanner_api.main.settings", SimpleNamespace(cache_root=str(tmp_path / "cache")))
    monkeypatch.setattr("multiplanner_api.main.os.startfile", lambda path: opened.append(Path(path)))  # type: ignore[attr-defined]
    folder = tmp_path / "cache" / "saved_subsets" / "demo"
    folder.mkdir(parents=True)
    response = client.post("/api/v1/subsets/open-folder", json={"path": str(folder)})
    assert response.status_code == 200
    assert opened == [folder.resolve()]


def test_auto_locate_queries_supported_datasets_per_provider(monkeypatch) -> None:
    calls = []

    def fake_summarize(provider, dataset, *, geometry, geometry_type):
        calls.append((provider, dataset, geometry_type))
        return [tile_dict(provider, dataset)]

    monkeypatch.setattr("multiplanner_api.subsets.summarize_remote_tiles", fake_summarize)
    response = locate_subsets(LocateSubsetRequest(provider="auto", datasets=["dgm1", "dom1", "dop20"], geometry=corridor_geometry()))
    assert response.provider == "auto"
    assert ("lgln-ni", "dop20", "esriGeometryPolygon") in calls
    assert ("geobasis-nrw", "dgm1", "esriGeometryPolygon") in calls
    assert "geobasis-nrw does not support: dop20" in response.warnings


def test_auto_locate_keeps_other_provider_when_one_dataset_fails(monkeypatch) -> None:
    def fake_summarize(provider, dataset, *, geometry, geometry_type):
        if provider == "lgln-ni":
            raise RuntimeError("provider unavailable")
        return [tile_dict(provider, dataset)]

    monkeypatch.setattr("multiplanner_api.subsets.summarize_remote_tiles", fake_summarize)
    response = locate_subsets(LocateSubsetRequest(provider="auto", datasets=["dgm1"], geometry=corridor_geometry()))
    assert response.results[0].provider == "geobasis-nrw"
    assert any("lgln-ni/dgm1 failed" in warning for warning in response.warnings)


def test_cached_file_endpoint_serves_files_within_cache_root(monkeypatch, tmp_path) -> None:
    cache_root = tmp_path / "cache"
    target = cache_root / "saved_subsets" / "demo" / "dgm1" / "tile-a.tif"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"tile-bytes")
    monkeypatch.setattr("multiplanner_api.main.settings", SimpleNamespace(cache_root=str(cache_root)))
    response = client.get("/api/v1/subsets/file", params={"path": str(target)})
    assert response.status_code == 200
    assert response.content == b"tile-bytes"


def test_download_subset_returns_absolute_saved_paths(monkeypatch, tmp_path) -> None:
    patch_download_settings(monkeypatch, tmp_path)
    monkeypatch.setattr("multiplanner_api.downloads._download_file", lambda *_args, **_kwargs: None)
    response = download_subset(corridor_download_request("abs-paths"))
    assert Path(response.files[0].saved_path).is_absolute()
    assert not response.exports or all(Path(path).is_absolute() for path in response.exports)


def test_download_subset_retries_tiff_downloads_without_ssl_verification(monkeypatch, tmp_path) -> None:
    calls = []
    patch_download_settings(monkeypatch, tmp_path)
    monkeypatch.setattr("multiplanner_api.downloads.requests.get", fake_retrying_get(calls))
    response = download_subset(corridor_download_request("ssl-fallback"))
    target = tmp_path / "cache" / "saved_subsets" / "ssl-fallback" / "dgm1" / "tile-a.tif"
    assert calls == [True, False]
    assert response.file_count == 1
    assert target.read_bytes() == b"tile-bytes"


def fake_retrying_get(calls: list[bool]):
    def fake_get(url, *, stream, timeout, verify):
        calls.append(verify)
        if verify:
            raise requests.exceptions.SSLError("certificate verify failed")
        return FakeResponse()

    return fake_get


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):
        yield b"tile-bytes"
