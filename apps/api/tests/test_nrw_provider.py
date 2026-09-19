from types import SimpleNamespace

import requests
from shapely.geometry import Point

from multiplanner_api.nrw import load_index, parse_catalog, tile_coordinates
from multiplanner_api.providers import SERVICE_PROVIDERS, provider_dataset_names


CATALOG = """<?xml version=\"1.0\"?>
<listing>
  <file name=\"dgm1_32_395_5798_1_nw_2022.tif\" />
  <file name=\"dgm1_32_395_5798_1_nw_2024.tif\" />
</listing>"""


def test_nrw_provider_lists_1m_terrain_and_surface_datasets() -> None:
    assert provider_dataset_names("geobasis-nrw") == ("dgm1", "dom1", "lod2")


def test_nrw_grid_derives_the_intersecting_1km_tile() -> None:
    assert tile_coordinates(Point(395554.8, 5798268.3)) == [(395, 5798)]


def test_catalog_uses_the_current_tile_version() -> None:
    index = parse_catalog(CATALOG, "https://example.test/")

    assert index[(395, 5798)] == {
        "tile_id": "dgm1_32_395_5798_1_nw_2024",
        "primary_url": "https://example.test/dgm1_32_395_5798_1_nw_2024.tif",
        "version": "2024",
    }


def test_catalogue_index_is_cached_until_its_refresh_is_due(monkeypatch, tmp_path) -> None:
    requests = []

    monkeypatch.setenv("MULTIPLANNER_CACHE_ROOT", str(tmp_path))
    monkeypatch.setattr("multiplanner_api.nrw.get_verified", lambda *_args, **_kwargs: requests.append(1) or SimpleNamespace(text=CATALOG, raise_for_status=lambda: None))
    config = SERVICE_PROVIDERS["geobasis-nrw"]["datasets"]["dgm1"]

    first = load_index("dgm1", config, timeout=1)
    second = load_index("dgm1", config, timeout=1)

    assert first == second
    assert len(requests) == 1


def test_catalogue_index_uses_verified_tls(monkeypatch, tmp_path) -> None:
    calls = []

    monkeypatch.setenv("MULTIPLANNER_CACHE_ROOT", str(tmp_path))
    monkeypatch.setattr("multiplanner_api.nrw.get_verified", lambda *_args, **_kwargs: calls.append(1) or SimpleNamespace(text=CATALOG, raise_for_status=lambda: None))
    config = SERVICE_PROVIDERS["geobasis-nrw"]["datasets"]["dgm1"]

    index = load_index("dgm1", config, timeout=1)

    assert calls == [1]
    assert index[(395, 5798)]["version"] == "2024"


def test_catalogue_index_uses_verified_tls_helper(monkeypatch, tmp_path) -> None:
    calls = []
    monkeypatch.setenv("MULTIPLANNER_CACHE_ROOT", str(tmp_path))
    monkeypatch.setattr("multiplanner_api.nrw.get_verified", lambda *_args, **_kwargs: calls.append(1) or SimpleNamespace(text=CATALOG, raise_for_status=lambda: None))
    config = SERVICE_PROVIDERS["geobasis-nrw"]["datasets"]["dgm1"]

    index = load_index("dgm1", config, timeout=1)

    assert index[(395, 5798)]["version"] == "2024"
    assert calls == [1]


def fake_catalog_session(calls: list[bool], trust_env_values: list[bool] | None = None, *, fail_first: bool = False):
    class FakeSession:
        def __init__(self):
            self.trust_env = True

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def get(self, *_args, **kwargs):
            if trust_env_values is not None:
                trust_env_values.append(self.trust_env)
            calls.append(kwargs["verify"])
            if fail_first and kwargs["verify"] and len(calls) == 1:
                raise requests.exceptions.SSLError("certificate verify failed")
            return SimpleNamespace(text=CATALOG, raise_for_status=lambda: None)

    return FakeSession
