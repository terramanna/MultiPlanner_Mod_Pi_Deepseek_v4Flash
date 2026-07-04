from __future__ import annotations

import math

from multiplanner_api.models import (
    CorridorGeometryInput,
    LocateSubsetRequest,
    PathProfileRequest,
    PathProfileResponse,
    PathProfileSample,
    PointProbeRequest,
)
from multiplanner_api.point_probe import probe_point
from multiplanner_api.subsets import locate_subsets

LIGHT_SPEED_MPS = 299_792_458
EARTH_RADIUS_M = 6_371_000


def build_path_profile(request: PathProfileRequest) -> PathProfileResponse:
    sample_count = _sample_count(request.sample_count)
    distance_m = max(1.0, _distance_m(request.site_a.lat, request.site_a.lon, request.site_b.lat, request.site_b.lon))
    warnings: list[str] = []
    provider = _resolve_profile_provider(request, warnings)
    request = request.model_copy(update={"provider": provider})
    samples = [
        _profile_sample(request, index, sample_count, distance_m, warnings)
        for index in range(sample_count)
    ]
    _apply_los(samples, request)
    return PathProfileResponse(
        provider=provider,
        source=request.source,
        distance_m=distance_m,
        antenna_height_m=max(0.0, request.antenna_height_m),
        frequency_mhz=_positive(request.frequency_mhz, 6000.0),
        fresnel_zone=max(1, request.fresnel_zone),
        samples=samples,
        warnings=_unique_warnings(warnings),
    )


def fresnel_radius_m(distance_m: float, frequency_mhz: float, zone: int, ratio: float) -> float:
    wavelength_m = LIGHT_SPEED_MPS / (_positive(frequency_mhz, 6000.0) * 1_000_000)
    first_leg_m = distance_m * ratio
    second_leg_m = distance_m - first_leg_m
    return math.sqrt((max(1, zone) * wavelength_m * first_leg_m * second_leg_m) / max(1.0, distance_m))


def _profile_sample(
    request: PathProfileRequest,
    index: int,
    sample_count: int,
    distance_m: float,
    warnings: list[str],
) -> PathProfileSample:
    ratio = index / (sample_count - 1)
    lon, lat = _interpolate_wgs84(request, ratio)
    fresnel_m = fresnel_radius_m(distance_m, request.frequency_mhz, request.fresnel_zone, ratio)
    sample = PathProfileSample(
        index=index,
        ratio=ratio,
        lon=lon,
        lat=lat,
        distance_m=distance_m * ratio,
        los_height_m=0.0,
        fresnel_radius_m=fresnel_m,
        fresnel_lower_m=-fresnel_m,
    )
    _apply_heights(sample, request, warnings)
    return sample


def _apply_heights(sample: PathProfileSample, request: PathProfileRequest, warnings: list[str]) -> None:
    try:
        if request.source in {"dgm1", "dgm1_dom1"}:
            sample.dgm_m = _probe_height(request.provider, "dgm1", sample.lon, sample.lat)
        if request.source in {"dom1", "dgm1_dom1"}:
            sample.dom_m = _probe_height(request.provider, "dom1", sample.lon, sample.lat)
    except Exception as exc:
        sample.error = str(exc)
        warnings.append(sample.error)
    sample.selected_height_m = _selected_height(sample, request.source)


def _apply_los(samples: list[PathProfileSample], request: PathProfileRequest) -> None:
    start_ground_m, end_ground_m = _endpoint_ground_heights(samples, request)
    for sample in samples:
        sample.los_height_m = _los_height(request, sample.ratio, start_ground_m, end_ground_m)
        sample.fresnel_lower_m = sample.los_height_m - sample.fresnel_radius_m
        if sample.selected_height_m is not None:
            sample.clearance_m = sample.fresnel_lower_m - sample.selected_height_m


def _endpoint_ground_heights(
    samples: list[PathProfileSample],
    request: PathProfileRequest,
) -> tuple[float, float]:
    valid_samples = [sample for sample in samples if sample.selected_height_m is not None]
    start = _endpoint_ground_height(request.site_a.height_m, valid_samples, first=True)
    end = _endpoint_ground_height(request.site_b.height_m, valid_samples, first=False)
    return start, end


def _endpoint_ground_height(
    explicit_height_m: float,
    valid_samples: list[PathProfileSample],
    *,
    first: bool,
) -> float:
    if explicit_height_m > 0 or not valid_samples:
        return explicit_height_m
    sample = valid_samples[0] if first else valid_samples[-1]
    return sample.selected_height_m or explicit_height_m


def _probe_height(provider: str, dataset: str, lon: float, lat: float) -> float:
    response = probe_point(PointProbeRequest(provider=provider, dataset=dataset, lon=lon, lat=lat))
    return response.height_m


def _resolve_profile_provider(request: PathProfileRequest, warnings: list[str]) -> str:
    if request.provider != "auto":
        return request.provider
    providers = _providers_from_subset_preview(request)
    if len(providers) == 1:
        warnings.append(f"Profile provider resolved from subset preview: {providers[0]}.")
        return providers[0]
    if len(providers) > 1:
        warnings.append(f"Profile crosses multiple providers: {', '.join(providers)}. Using auto point probes.")
    return "auto"


def _providers_from_subset_preview(request: PathProfileRequest) -> list[str]:
    response = locate_subsets(
        LocateSubsetRequest(
            provider="auto",
            datasets=_profile_datasets(request.source),
            geometry=CorridorGeometryInput(
                kind="corridor",
                from_lon=request.site_a.lon,
                from_lat=request.site_a.lat,
                to_lon=request.site_b.lon,
                to_lat=request.site_b.lat,
                buffer_m=75,
            ),
        )
    )
    providers = {result.provider for result in response.results if result.provider and result.match_count}
    return sorted(providers)


def _profile_datasets(source: str) -> list[str]:
    if source == "dgm1":
        return ["dgm1"]
    if source == "dom1":
        return ["dom1"]
    return ["dgm1", "dom1"]


def _selected_height(sample: PathProfileSample, source: str) -> float | None:
    if source == "dgm1":
        return sample.dgm_m
    if source == "dom1":
        return sample.dom_m
    if sample.dgm_m is None and sample.dom_m is None:
        return None
    return max(value for value in [sample.dgm_m, sample.dom_m] if value is not None)


def _los_height(request: PathProfileRequest, ratio: float, start_ground_m: float, end_ground_m: float) -> float:
    antenna = max(0.0, request.antenna_height_m)
    start_m = start_ground_m + antenna
    end_m = end_ground_m + antenna
    return start_m + (end_m - start_m) * ratio


def _interpolate_wgs84(request: PathProfileRequest, ratio: float) -> tuple[float, float]:
    lon = request.site_a.lon + (request.site_b.lon - request.site_a.lon) * ratio
    lat = request.site_a.lat + (request.site_b.lat - request.site_a.lat) * ratio
    return lon, lat


def _sample_count(value: int) -> int:
    return min(101, max(3, value))


def _distance_m(first_lat: float, first_lon: float, second_lat: float, second_lon: float) -> float:
    delta_lat = math.radians(second_lat - first_lat)
    delta_lon = math.radians(second_lon - first_lon)
    first_lat_r = math.radians(first_lat)
    second_lat_r = math.radians(second_lat)
    haversine = math.sin(delta_lat / 2) ** 2 + math.cos(first_lat_r) * math.cos(second_lat_r) * math.sin(delta_lon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.atan2(math.sqrt(haversine), math.sqrt(1 - haversine))


def _positive(value: float, fallback: float) -> float:
    return value if math.isfinite(value) and value > 0 else fallback


def _unique_warnings(warnings: list[str]) -> list[str]:
    return list(dict.fromkeys(warnings))
