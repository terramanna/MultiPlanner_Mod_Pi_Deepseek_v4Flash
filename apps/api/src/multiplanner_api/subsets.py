from __future__ import annotations

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


def locate_subsets(request: LocateSubsetRequest) -> LocateSubsetResponse:
    provider = request.provider
    if provider not in SERVICE_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")

    supported = set(provider_dataset_names(provider))
    invalid = [name for name in request.datasets if name not in supported]
    if invalid:
        raise ValueError(f"Unsupported dataset(s) for {provider}: {', '.join(invalid)}")

    geometry, geometry_type = _build_geometry(request.geometry)
    results: list[DatasetSubsetResult] = []
    for dataset in request.datasets:
        matches = summarize_remote_tiles(
            provider,
            dataset,
            geometry=geometry,
            geometry_type=geometry_type,
        )
        tiles = []
        for match in matches:
            metadata = {
                key: value
                for key, value in match.items()
                if key not in {"provider", "dataset", "tile_id", "updated", "primary_url"}
            }
            tiles.append(
                TileSummary(
                    provider=match["provider"],
                    dataset=match["dataset"],
                    tile_id=match.get("tile_id"),
                    updated=match.get("updated"),
                    primary_url=match.get("primary_url"),
                    metadata=metadata,
                )
            )
        results.append(
            DatasetSubsetResult(
                dataset=dataset,
                match_count=len(tiles),
                tiles=tiles,
            )
        )

    return LocateSubsetResponse(
        provider=provider,
        geometry_kind=request.geometry.kind,
        results=results,
    )


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
