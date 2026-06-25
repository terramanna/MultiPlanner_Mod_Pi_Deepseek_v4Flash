from __future__ import annotations

import requests

from multiplanner_api.models import (
    BboxGeometryInput,
    CorridorGeometryInput,
    DatasetSubsetResult,
    LocateSubsetRequest,
    LocateSubsetResponse,
    PolygonGeometryInput,
    PointGeometryInput,
    TileSummary,
)
from multiplanner_api.providers import (
    SERVICE_PROVIDERS,
    bbox_geometry,
    corridor_geometry,
    provider_dataset_names,
    point_geometry,
    polygon_geometry,
    summarize_remote_tiles,
)

SOURCE_BYTES_PER_TILE = {
    "dgm1": 3_000_000,
    "dom1": 3_000_000,
    "dop20": 80_000_000,
}
ELLIPSE_BYTES_PER_TILE = {
    "dgm1": 4_000_000,
    "dom1": 4_000_000,
}
SUMMARY_FIELDS = {"provider", "dataset", "tile_id", "updated", "primary_url"}


def locate_subsets(request: LocateSubsetRequest) -> LocateSubsetResponse:
    geometry, geometry_type = _build_geometry(request.geometry)
    if request.provider == "auto":
        return _locate_auto_subsets(request, geometry, geometry_type)
    return _locate_single_provider_subsets(request.provider, request.datasets, request.geometry.kind, geometry, geometry_type)


def _locate_single_provider_subsets(
    provider: str,
    datasets: list[str],
    geometry_kind: str,
    geometry: str,
    geometry_type: str,
) -> LocateSubsetResponse:
    if provider not in SERVICE_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")

    supported = set(provider_dataset_names(provider))
    invalid = [name for name in datasets if name not in supported]
    if invalid:
        raise ValueError(f"Unsupported dataset(s) for {provider}: {', '.join(invalid)}")

    results = [
        _build_dataset_subset_result(provider, dataset, geometry, geometry_type)
        for dataset in datasets
    ]
    return _build_locate_response(provider, geometry_kind, results)


def _locate_auto_subsets(
    request: LocateSubsetRequest,
    geometry: str,
    geometry_type: str,
) -> LocateSubsetResponse:
    results: list[DatasetSubsetResult] = []
    warnings: list[str] = []

    for provider in SERVICE_PROVIDERS:
        supported = set(provider_dataset_names(provider))
        provider_datasets = [name for name in request.datasets if name in supported]
        skipped = [name for name in request.datasets if name not in supported]
        if skipped:
            warnings.append(f"{provider} does not support: {', '.join(skipped)}")
        for dataset in provider_datasets:
            try:
                results.append(_build_dataset_subset_result(provider, dataset, geometry, geometry_type))
            except Exception as exc:
                warnings.append(f"{provider}/{dataset} failed: {exc}")

    if not results:
        raise ValueError("No configured provider supports the requested datasets.")

    response = _build_locate_response("auto", request.geometry.kind, results)
    response.warnings = warnings
    return response


def _build_dataset_subset_result(
    provider: str,
    dataset: str,
    geometry: str,
    geometry_type: str,
) -> DatasetSubsetResult:
    try:
        matches = summarize_remote_tiles(
            provider,
            dataset,
            geometry=geometry,
            geometry_type=geometry_type,
        )
    except requests.exceptions.RequestException as exc:
        raise ValueError(f"Provider lookup failed for {provider}/{dataset}: {exc}") from exc
    tiles = [_build_tile_summary(match) for match in matches]
    return DatasetSubsetResult(
        provider=provider,
        dataset=dataset,
        match_count=len(tiles),
        tiles=tiles,
        estimated_source_bytes=_estimated_source_bytes(dataset, len(tiles)),
        estimated_ellipse_bytes=_estimated_ellipse_bytes(dataset, len(tiles)),
    )


def _build_tile_summary(match: dict[str, object]) -> TileSummary:
    metadata = {
        key: _optional_string(value)
        for key, value in match.items()
        if key not in SUMMARY_FIELDS
    }
    return TileSummary(
        provider=str(match["provider"]),
        dataset=str(match["dataset"]),
        tile_id=_optional_string(match.get("tile_id")),
        updated=_optional_string(match.get("updated")),
        primary_url=_optional_string(match.get("primary_url")),
        metadata=metadata,
    )


def _build_locate_response(
    provider: str,
    geometry_kind: str,
    results: list[DatasetSubsetResult],
) -> LocateSubsetResponse:
    return LocateSubsetResponse(
        provider=provider,
        geometry_kind=geometry_kind,
        results=results,
        total_estimated_source_bytes=sum(result.estimated_source_bytes for result in results),
        total_estimated_ellipse_bytes=sum(result.estimated_ellipse_bytes for result in results),
    )


def _estimated_source_bytes(dataset: str, tile_count: int) -> int:
    return tile_count * SOURCE_BYTES_PER_TILE.get(dataset, 5_000_000)


def _estimated_ellipse_bytes(dataset: str, tile_count: int) -> int:
    return tile_count * ELLIPSE_BYTES_PER_TILE.get(dataset, 0)


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _build_geometry(
    geometry_input: PointGeometryInput | BboxGeometryInput | PolygonGeometryInput | CorridorGeometryInput,
) -> tuple[str, str]:
    if isinstance(geometry_input, PointGeometryInput):
        return point_geometry(geometry_input.lon, geometry_input.lat)
    if isinstance(geometry_input, BboxGeometryInput):
        return bbox_geometry(
            geometry_input.west,
            geometry_input.south,
            geometry_input.east,
            geometry_input.north,
        )
    if isinstance(geometry_input, PolygonGeometryInput):
        return polygon_geometry(geometry_input.coordinates)
    if isinstance(geometry_input, CorridorGeometryInput):
        return corridor_geometry(
            geometry_input.from_lon,
            geometry_input.from_lat,
            geometry_input.to_lon,
            geometry_input.to_lat,
            geometry_input.buffer_m,
        )
    raise ValueError(f"Unsupported geometry kind: {geometry_input.kind}")
