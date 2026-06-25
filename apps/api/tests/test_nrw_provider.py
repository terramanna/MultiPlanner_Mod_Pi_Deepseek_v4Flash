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
    assert provider_dataset_names("geobasis-nrw") == ("dgm1", "dom1")


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

    def get_catalog(*_args, **_kwargs):
        requests.append(True)
        return SimpleNamespace(text=CATALOG, raise_for_status=lambda: None)

    monkeypatch.setenv("MULTIPLANNER_CACHE_ROOT", str(tmp_path))
    monkeypatch.setattr("multiplanner_api.nrw.requests.get", get_catalog)
    config = SERVICE_PROVIDERS["geobasis-nrw"]["datasets"]["dgm1"]

    first = load_index("dgm1", config, timeout=1)
    second = load_index("dgm1", config, timeout=1)

    assert first == second
    assert len(requests) == 1


def test_catalogue_index_retries_without_ssl_verification(monkeypatch, tmp_path) -> None:
    verify_values = []

    def get_catalog(*_args, **kwargs):
        verify_values.append(kwargs["verify"])
        if kwargs["verify"]:
            raise requests.exceptions.SSLError("certificate verify failed")
        return SimpleNamespace(text=CATALOG, raise_for_status=lambda: None)

    monkeypatch.setenv("MULTIPLANNER_CACHE_ROOT", str(tmp_path))
    monkeypatch.setattr("multiplanner_api.nrw.requests.get", get_catalog)
    config = SERVICE_PROVIDERS["geobasis-nrw"]["datasets"]["dgm1"]

    index = load_index("dgm1", config, timeout=1)

    assert verify_values == [True, False]
    assert index[(395, 5798)]["version"] == "2024"
