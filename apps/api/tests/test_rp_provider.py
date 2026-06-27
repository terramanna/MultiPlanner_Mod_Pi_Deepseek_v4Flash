from types import SimpleNamespace

import requests
from shapely.geometry import Point

from multiplanner_api.rp import _load_index, _parse_meta4, _tile_coordinates
from multiplanner_api.providers import SERVICE_PROVIDERS, provider_dataset_names

META4 = """\
<?xml version="1.0" encoding="UTF-8"?>
<metalink xmlns="urn:ietf:params:xml:ns:metalink">
  <file name="dgm1_32_390_5510_1_rp_2022.tif">
    <url>https://geobasis-rlp.de/data/dgm1/current/tif/dgm1_32_390_5510_1_rp_2022.tif</url>
    <size>1234567</size>
  </file>
  <file name="dgm1_32_390_5510_1_rp_2024.tif">
    <url>https://geobasis-rlp.de/data/dgm1/current/tif/dgm1_32_390_5510_1_rp_2024.tif</url>
    <size>1234567</size>
  </file>
  <file name="dgm1_32_391_5510_1_rp_2023.tif">
    <url>https://geobasis-rlp.de/data/dgm1/current/tif/dgm1_32_391_5510_1_rp_2023.tif</url>
    <size>1234567</size>
  </file>
  <file name="junk_file_should_be_ignored.txt">
    <url>https://example.com/junk.txt</url>
  </file>
</metalink>"""

# Mainz city centre ~ EPSG:25832: x ≈ 447 000, y ≈ 5 533 000
MAINZ_POINT = "8.2711,49.9929"


def test_lvermgeo_rp_provider_lists_dgm1_dataset() -> None:
    assert provider_dataset_names("lvermgeo-rp") == ("dgm1",)


def test_tile_coordinates_single_point_returns_one_km_cell() -> None:
    assert _tile_coordinates(Point(447_500, 5_533_500)) == [(447, 5533)]


def test_parse_meta4_prefers_most_recent_year_for_duplicate_tile() -> None:
    index = _parse_meta4(META4)
    assert (390, 5510) in index
    entry = index[(390, 5510)]
    assert entry["year"] == "2024"
    assert entry["tile_id"] == "dgm1_32_390_5510_1_rp_2024"
    assert entry["primary_url"] == "https://geobasis-rlp.de/data/dgm1/current/tif/dgm1_32_390_5510_1_rp_2024.tif"


def test_parse_meta4_includes_all_valid_tiles() -> None:
    index = _parse_meta4(META4)
    assert len(index) == 2
    assert (391, 5510) in index


def test_parse_meta4_ignores_non_matching_filenames() -> None:
    index = _parse_meta4(META4)
    for entry in index.values():
        assert entry["primary_url"].endswith(".tif")


def test_load_index_is_cached_on_second_call(monkeypatch, tmp_path) -> None:
    calls: list[bool] = []
    monkeypatch.setenv("MULTIPLANNER_CACHE_ROOT", str(tmp_path))
    monkeypatch.setattr("multiplanner_api.rp.requests.Session", _fake_session(calls))

    first = _load_index(timeout=1)
    second = _load_index(timeout=1)

    assert first == second
    assert len(calls) == 1


def test_load_index_retries_without_ssl_verification(monkeypatch, tmp_path) -> None:
    verify_values: list[bool] = []
    monkeypatch.setenv("MULTIPLANNER_CACHE_ROOT", str(tmp_path))
    monkeypatch.setattr("multiplanner_api.rp.requests.Session", _fake_session(verify_values, fail_first=True))

    index = _load_index(timeout=1)

    assert verify_values == [True, False]
    assert (390, 5510) in index


def test_load_index_ignores_environment_proxies(monkeypatch, tmp_path) -> None:
    trust_env_values: list[bool] = []
    monkeypatch.setenv("MULTIPLANNER_CACHE_ROOT", str(tmp_path))
    monkeypatch.setattr("multiplanner_api.rp.requests.Session", _fake_session([], trust_env_values=trust_env_values))

    _load_index(timeout=1)

    assert trust_env_values == [False]


def _fake_session(calls: list[bool], trust_env_values: list[bool] | None = None, *, fail_first: bool = False):
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
            return SimpleNamespace(text=META4, raise_for_status=lambda: None)

    return FakeSession
