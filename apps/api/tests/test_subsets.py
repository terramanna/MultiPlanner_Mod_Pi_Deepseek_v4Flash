from pathlib import Path
from types import SimpleNamespace
from threading import Lock, Thread
from time import sleep
import zipfile

import requests
from fastapi.testclient import TestClient

from multiplanner_api import downloads, ellipse_exports
from multiplanner_api.downloads import _download_file, _target_filename, download_subset
from multiplanner_api.main import app
from multiplanner_api.models import BboxGeometryInput, CorridorGeometryInput, DownloadSubsetRequest, LocateSubsetRequest
from multiplanner_api.subsets import _estimated_ellipse_bytes, _estimated_source_bytes, locate_subsets


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


def two_tile_response() -> SimpleNamespace:
    tiles = [
        SimpleNamespace(tile_id="tile-a", primary_url="https://example.invalid/tile-a.tif"),
        SimpleNamespace(tile_id="tile-b", primary_url="https://example.invalid/tile-b.tif"),
    ]
    return SimpleNamespace(results=[SimpleNamespace(dataset="dgm1", tiles=tiles)])


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
    monkeypatch.setattr("multiplanner_api.downloads.load_settings", lambda: SimpleNamespace(cache_root=str(tmp_path / "cache"), output_dir="", ellipse_gdal_dir="unused"))
    monkeypatch.setattr("multiplanner_api.downloads.locate_subsets", lambda request: single_tile_response())


def test_target_filename_uses_file_query_suffix_for_sh_download() -> None:
    url = (
        "https://geodaten.schleswig-holstein.de/gaialight-sh/_apps/dladownload/massen.php"
        "?file=dgm1_32_593_5953_1_sh_2022.xyz&id=2&live=2022&km=32590_5950"
    )

    assert _target_filename(url, "sh_dgm1_325935953") == "sh_dgm1_325935953.xyz"


def test_cached_sh_text_download_strips_appended_portal_html(tmp_path) -> None:
    target = tmp_path / "sh_lod2_325935953.xml"
    target.write_bytes(b"<CityModel/>\n<!DOCTYPE html>\n<html>portal</html>\n")
    url = (
        "https://geodaten.schleswig-holstein.de/gaialight-sh/_apps/dladownload/massen.php"
        "?file=LoD2_32_593_5953_1_SH.xml&id=4"
    )

    _download_file(url, target)

    assert target.read_bytes() == b"<CityModel/>\n"


def test_parallel_downloads_for_same_target_are_serialized(monkeypatch, tmp_path) -> None:
    active = 0
    maximum_active = 0
    counter_lock = Lock()

    def fake_download(_url, _target):
        nonlocal active, maximum_active
        with counter_lock:
            active += 1
            maximum_active = max(maximum_active, active)
        sleep(0.03)
        with counter_lock:
            active -= 1

    monkeypatch.setattr("multiplanner_api.downloads._download_file_once", fake_download)
    target = tmp_path / "tile.tif"
    threads = [Thread(target=_download_file, args=("https://example.invalid/tile.tif", target)) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert maximum_active == 1


def test_sh_estimates_reflect_large_bdom_tiles() -> None:
    assert _estimated_source_bytes("lvermgeo-sh", "dgm1", 23) == 644_000_000
    assert _estimated_source_bytes("lvermgeo-sh", "dom1", 23) == 2_415_000_000
    assert _estimated_ellipse_bytes("lvermgeo-sh", "dom1", 23) == 2_415_000_000


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


def test_subset_route_returns_provider_lookup_detail(monkeypatch) -> None:
    def fail_lookup(*_args, **_kwargs):
        raise requests.exceptions.ConnectionError("catalog unavailable")

    monkeypatch.setattr("multiplanner_api.subsets.summarize_remote_tiles", fail_lookup)
    response = client.post("/api/v1/subsets/locate", json=point_payload())
    assert response.status_code == 400
    assert response.json()["detail"] == "Provider lookup failed for lgln-ni/dgm1: catalog unavailable"


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
    monkeypatch.setattr("multiplanner_api.downloads.requests.Session", fake_retrying_session(calls, fail_first=True))
    response = download_subset(corridor_download_request("ssl-fallback"))
    target = tmp_path / "cache" / "saved_subsets" / "ssl-fallback" / "dgm1" / "tile-a.tif"
    assert calls == [True, False]
    assert response.file_count == 1
    assert target.read_bytes() == b"tile-bytes"


def test_download_subset_retries_transient_tile_download_once(monkeypatch, tmp_path) -> None:
    calls = []
    patch_download_settings(monkeypatch, tmp_path)
    monkeypatch.setattr("multiplanner_api.downloads.requests.Session", fake_timeout_once_session(calls))

    response = download_subset(corridor_download_request("timeout-retry"))

    target = tmp_path / "cache" / "saved_subsets" / "timeout-retry" / "dgm1" / "tile-a.tif"
    assert calls == [True, True]
    assert response.file_count == 1
    assert target.read_bytes() == b"tile-bytes"


def test_download_resumes_an_interrupted_partial_file(monkeypatch, tmp_path) -> None:
    requests_sent = []
    target = tmp_path / "tile.tif"
    target.with_name("tile.tif.part").write_bytes(b"first-half-")

    class ResumingResponse(FakeResponse):
        status_code = 206

        def iter_content(self, chunk_size: int):
            yield b"second-half"

    class ResumingSession:
        trust_env = True

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def get(self, _url, *, headers, **_kwargs):
            requests_sent.append(headers)
            return ResumingResponse()

    monkeypatch.setattr("multiplanner_api.downloads.requests.Session", ResumingSession)

    _download_file("https://example.invalid/tile.tif", target)

    assert requests_sent == [{"Range": "bytes=11-"}]
    assert target.read_bytes() == b"first-half-second-half"
    assert not target.with_name("tile.tif.part").exists()


def test_download_subset_ignores_environment_proxies(monkeypatch, tmp_path) -> None:
    trust_env_values = []
    patch_download_settings(monkeypatch, tmp_path)
    monkeypatch.setattr("multiplanner_api.downloads.requests.Session", fake_retrying_session([], trust_env_values))
    response = download_subset(corridor_download_request("proxy-bypass"))
    assert response.file_count == 1
    assert trust_env_values == [False]


def test_download_subset_reports_missing_files_and_skips_export(monkeypatch, tmp_path) -> None:
    progress = []
    patch_download_settings(monkeypatch, tmp_path)
    monkeypatch.setattr("multiplanner_api.downloads.locate_subsets", lambda _request: two_tile_response())

    def fake_download(url, target_path):
        if url.endswith("tile-b.tif"):
            raise RuntimeError("network timeout")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b"tile-bytes")

    monkeypatch.setattr("multiplanner_api.downloads._download_file", fake_download)
    response = download_subset(
        corridor_download_request("partial-download"),
        on_progress=lambda *event: progress.append(event),
    )

    assert response.expected_file_count == 2
    assert response.file_count == 1
    assert response.failed_downloads[0].tile_id == "tile-b"
    assert response.exports == []
    assert [event[3:] for event in progress] == [(1, 2, True), (2, 2, False)]
    assert "Export skipped because 1 identified source file(s) failed to download." in response.warnings


def test_download_subset_returns_export_conversion_warnings(monkeypatch, tmp_path) -> None:
    patch_download_settings(monkeypatch, tmp_path)

    def fake_download(_url, target_path):
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b"tile-bytes")

    monkeypatch.setattr("multiplanner_api.downloads._download_file", fake_download)
    monkeypatch.setattr(
        "multiplanner_api.downloads._export_subset",
        lambda *_args: ([], ["UTM32N GeoTIFF + TAB export failed for dgm1: conversion stopped."]),
    )

    response = download_subset(corridor_download_request("export-warning"))

    assert response.file_count == 1
    assert response.exports == []
    assert response.warnings == ["UTM32N GeoTIFF + TAB export failed for dgm1: conversion stopped."]


def test_download_subset_warns_when_bw_package_has_missing_child_rasters(monkeypatch, tmp_path) -> None:
    patch_download_settings(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "multiplanner_api.downloads.locate_subsets",
        lambda _request: SimpleNamespace(
            results=[
                SimpleNamespace(
                    dataset="dom1",
                    tiles=[
                        SimpleNamespace(
                            tile_id="bw_dom1_475_5288",
                            primary_url="https://opengeodata.lgl-bw.de/data/dom1/dom1_32_475_5288_2_bw.zip",
                        )
                    ],
                )
            ]
        ),
    )

    def fake_download(_url, target_path):
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target_path, "w") as zf:
            zf.writestr("dom1_32_475_5288_1_bw_2020.tif", b"tif")
            zf.writestr("dom1_32_476_5288_1_bw_2020.tif", b"tif")

    monkeypatch.setattr("multiplanner_api.downloads._download_file", fake_download)
    monkeypatch.setattr("multiplanner_api.downloads._export_subset", lambda *_args: (["export.tif"], []))

    response = download_subset(DownloadSubsetRequest(provider="lgl-bw", datasets=["dom1"], selection_name="partial-bw", geometry=corridor_geometry()))

    assert response.exports == ["export.tif"]
    assert response.warnings == [
        "lgl-bw/dom1/bw_dom1_475_5288 package contains 2 of 4 expected raster file(s); exported mosaic may have gaps."
    ]


def test_ascii_zip_sources_are_converted_before_export(monkeypatch, tmp_path) -> None:
    source = tmp_path / "dgm1_32_513_5402_1_bw_2023.xyz"
    source.write_text("513000 5402000 250\n", encoding="ascii")
    commands = []

    def fake_run_gdal(command, _environment):
        commands.append(command)
        Path(command[-1]).write_bytes(b"tif")

    monkeypatch.setattr(ellipse_exports, "_run_gdal", fake_run_gdal)
    result = ellipse_exports._prepare_export_source(source, tmp_path / "gdal_translate.exe", {})

    assert result.name == "dgm1_32_513_5402_1_bw_2023.xyz.tif"
    assert commands[0][commands[0].index("-a_srs") + 1] == "EPSG:25832"


def test_ellipse_export_with_pyramids_runs_gdaladdo(monkeypatch, tmp_path) -> None:
    source = tmp_path / "tile.tif"
    source.write_bytes(b"tif")
    commands = []

    def fake_run_gdal(command, _environment):
        commands.append(command)
        if command[0].endswith("gdalbuildvrt.exe"):
            Path(command[1]).write_text("vrt", encoding="ascii")
        elif command[0].endswith("gdalwarp.exe"):
            Path(command[-1]).write_bytes(b"tif")
        elif command[0].endswith("gdalinfo.exe"):
            return SimpleNamespace(stdout='{"coordinateSystem":{"wkt":"ID[\\"EPSG\\",32632]"},"size":[10,10],"cornerCoordinates":{"upperLeft":[0,10],"upperRight":[10,10],"lowerRight":[10,0],"lowerLeft":[0,0]}}')
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(ellipse_exports, "_run_gdal", fake_run_gdal)

    export_dir = tmp_path / "export"
    export_dir.mkdir()
    environment = {}
    exports = ellipse_exports._export_ellipse_dataset(
        "dgm1",
        [source],
        export_dir,
        tmp_path / "gdalbuildvrt.exe",
        tmp_path / "gdalwarp.exe",
        tmp_path / "gdalinfo.exe",
        tmp_path / "gdaladdo.exe",
        environment,
        "demo",
        True,
    )

    assert any(command[0].endswith("gdaladdo.exe") for command in commands)
    assert exports[0].endswith(".tif")
    assert exports[1].endswith(".TAB")


def test_semantic_grc_profile_uses_bayern_geometry_and_lod2(monkeypatch, tmp_path) -> None:
    request = DownloadSubsetRequest(
        provider="ldbv-by", datasets=["bdom"], selection_name="munich-selection",
        export_profile="ellipse_semantic_grc",
        geometry=BboxGeometryInput(kind="bbox", west=11.55, south=48.12, east=11.60, north=48.16),
    )
    source = tmp_path / "lod2.gml"
    source.write_text("<CityModel/>", encoding="utf-8")
    captured = {}

    def fake_export(**kwargs):
        captured.update(kwargs)
        return [
            str(tmp_path / "buildings.grc"), str(tmp_path / "trees.grc"),
            str(tmp_path / "buildings.vse"), str(tmp_path / "trees.vse"),
            str(tmp_path / "building_heights.mrr"), str(tmp_path / "tree_heights.mrr"),
        ], []

    monkeypatch.setattr(
        "multiplanner_api.downloads._export_for_ellipse",
        lambda *_args, **_kwargs: ([
            str(tmp_path / "dgm.tif"), str(tmp_path / "dgm.TAB"),
            str(tmp_path / "dom.tif"), str(tmp_path / "dom.TAB"),
        ], []),
    )
    monkeypatch.setattr("multiplanner_api.downloads.export_semantic_grc", fake_export)
    sources = {"dgm1": [tmp_path / "dgm.tif"], "dom1": [tmp_path / "dom.tif"], "bdom": [source]}
    exports, warnings = downloads._export_or_skip(request, sources, [], tmp_path, "gdal-dir")

    assert warnings == []
    assert [Path(path).suffix for path in exports] == [
        ".tif", ".TAB", ".tif", ".TAB", ".grc", ".grc", ".vse", ".vse", ".mrr", ".mrr",
    ]
    assert captured["geometry"] == request.geometry
    assert captured["provider"] == "ldbv-by"
    assert captured["lod2_paths"] == [source]
    assert captured["dgm_paths"] == [tmp_path / "dgm.tif"]
    assert captured["dom_paths"] == [tmp_path / "dom.tif"]
    assert captured["resolution_m"] == 2


def test_one_metre_semantic_profile_selects_one_metre_export(monkeypatch, tmp_path) -> None:
    request = DownloadSubsetRequest(
        provider="ldbv-by", datasets=["dgm1", "dom1", "bdom"],
        export_profile="ellipse_semantic_grc_1m",
        geometry=BboxGeometryInput(kind="bbox", west=11.55, south=48.12, east=11.60, north=48.16),
    )
    captured = {}
    monkeypatch.setattr("multiplanner_api.downloads._export_for_ellipse", lambda *_a, **_k: ([], []))
    monkeypatch.setattr(
        "multiplanner_api.downloads.export_semantic_grc",
        lambda **kwargs: (captured.update(kwargs) or [], []),
    )

    downloads._export_or_skip(request, {"dgm1": [], "dom1": [], "bdom": []}, [], tmp_path, "gdal")

    assert captured["resolution_m"] == 1


def test_semantic_grc_profile_rejects_unsupported_provider(tmp_path) -> None:
    request = DownloadSubsetRequest(**point_payload(), export_profile="ellipse_semantic_grc")

    exports, warnings = downloads._export_or_skip(request, {}, [], tmp_path, "gdal-dir")

    assert exports == []
    assert warnings == ["Buildings + trees GRC export supports Bayern and Schleswig-Holstein selections only."]


def test_semantic_grc_profile_uses_sh_lod2_dataset(monkeypatch, tmp_path) -> None:
    request = DownloadSubsetRequest(
        provider="lvermgeo-sh", datasets=["dgm1", "dom1", "lod2"],
        export_profile="ellipse_semantic_grc",
        geometry=BboxGeometryInput(kind="bbox", west=10.28, south=53.51, east=10.40, north=53.62),
    )
    captured = {}
    monkeypatch.setattr("multiplanner_api.downloads._export_for_ellipse", lambda *_a, **_k: ([], []))
    monkeypatch.setattr(
        "multiplanner_api.downloads.export_semantic_grc",
        lambda **kwargs: (captured.update(kwargs) or [], []),
    )
    sources = {"dgm1": [tmp_path / "dgm.xyz"], "dom1": [tmp_path / "dom.tif"], "lod2": [tmp_path / "lod2.xml"]}

    exports, warnings = downloads._export_or_skip(request, sources, [], tmp_path, "gdal")

    assert exports == []
    assert warnings == []
    assert captured["provider"] == "lvermgeo-sh"
    assert captured["lod2_paths"] == [tmp_path / "lod2.xml"]

def fake_retrying_session(
    calls: list[bool],
    trust_env_values: list[bool] | None = None,
    *,
    fail_first: bool = False,
):
    class FakeSession:
        def __init__(self):
            self.trust_env = True

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def get(self, url, *, headers, stream, timeout, verify):
            if trust_env_values is not None:
                trust_env_values.append(self.trust_env)
            calls.append(verify)
            if fail_first and verify and len(calls) == 1:
                raise requests.exceptions.SSLError("certificate verify failed")
            return FakeResponse()

    return FakeSession


def fake_timeout_once_session(calls: list[bool]):
    class FakeSession:
        def __init__(self):
            self.trust_env = True

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def get(self, url, *, headers, stream, timeout, verify):
            calls.append(verify)
            if len(calls) == 1:
                raise requests.exceptions.ReadTimeout("read timed out")
            return FakeResponse()

    return FakeSession


class FakeResponse:
    status_code = 200
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):
        yield b"tile-bytes"
