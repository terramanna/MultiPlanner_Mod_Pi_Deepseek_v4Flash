from fastapi.testclient import TestClient
from types import SimpleNamespace

from multiplanner_api import path_profile
from multiplanner_api.main import app
from multiplanner_api.models import PathProfileRequest, ProfileEndpointInput


client = TestClient(app)


def request_payload() -> dict[str, object]:
    return {
        "provider": "lgl-bw",
        "source": "dgm1_dom1",
        "site_a": {"lon": 7.0, "lat": 52.0, "height_m": 100.0},
        "site_b": {"lon": 7.0146, "lat": 52.0, "height_m": 110.0},
        "antenna_height_m": 30.0,
        "frequency_mhz": 6000.0,
        "fresnel_zone": 1,
        "sample_count": 5,
    }


def test_path_profile_samples_dgm_and_dom(monkeypatch) -> None:
    calls = []

    def fake_probe(provider, dataset, lon, lat):
        calls.append((provider, dataset, lon, lat))
        return 100.0 if dataset == "dgm1" else 118.0

    monkeypatch.setattr(path_profile, "_probe_height", fake_probe)
    result = path_profile.build_path_profile(PathProfileRequest(**request_payload()))

    assert len(result.samples) == 5
    assert result.source == "dgm1_dom1"
    assert result.samples[2].selected_height_m == 118.0
    assert result.samples[2].clearance_m is not None
    assert {call[1] for call in calls} == {"dgm1", "dom1"}


def test_path_profile_clamps_sample_count(monkeypatch) -> None:
    monkeypatch.setattr(path_profile, "_probe_height", lambda *_args: 10.0)
    request = PathProfileRequest(
        provider="lgl-bw",
        source="dgm1",
        site_a=ProfileEndpointInput(lon=7.0, lat=52.0),
        site_b=ProfileEndpointInput(lon=7.1, lat=52.0),
        sample_count=1,
    )

    result = path_profile.build_path_profile(request)

    assert len(result.samples) == 3


def test_path_profile_route_uses_service(monkeypatch) -> None:
    monkeypatch.setattr(path_profile, "_probe_height", lambda *_args: 88.0)

    response = client.post("/api/v1/profile/path", json=request_payload())

    body = response.json()
    assert response.status_code == 200
    assert body["source"] == "dgm1_dom1"
    assert len(body["samples"]) == 5
    assert body["samples"][0]["distance_m"] == 0


def test_zero_endpoint_heights_use_sampled_ground(monkeypatch) -> None:
    def fake_probe(_provider, _dataset, lon, _lat):
        return 100.0 + round((lon - 7.0) * 1000)

    monkeypatch.setattr(path_profile, "_probe_height", fake_probe)
    request = PathProfileRequest(
        provider="lgl-bw",
        source="dgm1",
        site_a=ProfileEndpointInput(lon=7.0, lat=52.0),
        site_b=ProfileEndpointInput(lon=7.02, lat=52.0),
        antenna_height_m=30.0,
        sample_count=3,
    )

    result = path_profile.build_path_profile(request)

    assert result.samples[0].los_height_m == 130.0
    assert result.samples[1].los_height_m == 140.0
    assert result.samples[2].los_height_m == 150.0
    assert result.samples[0].clearance_m == 30.0


def test_endpoint_nodata_uses_nearest_sampled_ground(monkeypatch) -> None:
    def fake_probe(_provider, _dataset, lon, _lat):
        if round(lon, 2) != 7.01:
            raise ValueError("No data value")
        return 100.0

    monkeypatch.setattr(path_profile, "_probe_height", fake_probe)
    request = PathProfileRequest(
        provider="lgl-bw",
        source="dgm1",
        site_a=ProfileEndpointInput(lon=7.0, lat=52.0),
        site_b=ProfileEndpointInput(lon=7.02, lat=52.0),
        antenna_height_m=30.0,
        sample_count=3,
    )

    result = path_profile.build_path_profile(request)

    assert result.samples[1].los_height_m == 130.0
    assert result.samples[1].clearance_m > 0
    assert result.warnings == ["No data value"]


def test_auto_profile_resolves_single_provider_from_subset_preview(monkeypatch) -> None:
    providers = []

    def fake_locate_subsets(_request):
        result = SimpleNamespace(provider="lgl-bw", match_count=2)
        return SimpleNamespace(results=[result])

    def fake_probe(provider, *_args):
        providers.append(provider)
        return 100.0

    monkeypatch.setattr(path_profile, "locate_subsets", fake_locate_subsets)
    monkeypatch.setattr(path_profile, "_probe_height", fake_probe)

    result = path_profile.build_path_profile(PathProfileRequest(**{**request_payload(), "provider": "auto"}))

    assert result.provider == "lgl-bw"
    assert providers == ["lgl-bw"] * 10
    assert "Profile provider resolved from subset preview: lgl-bw." in result.warnings
