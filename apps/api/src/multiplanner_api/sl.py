"""INSPIRE WCS 2.0.1 adapter for LVGL Saarland DGM1.

Endpoint:   https://geoportal.saarland.de/gdi-sl/inspireraster/inspirewcsel
Coverage ID: EL.GridCoverage
CRS:        EPSG:25832 (ETRS89 / UTM Zone 32N)
Axis labels: E (easting), N (northing) — INSPIRE convention
Tile size:  1 km × 1 km
Extent:     roughly x 296000–370000, y 5434000–5490000 (Saarland)
"""

from __future__ import annotations
from multiplanner_shared.geometry_io import request_geometry, to_utm32

import json
import math
from typing import Any

from shapely.geometry import Point, Polygon, box

TILE_SIZE_M = 1000
MAX_TILES_PER_DATASET = 200
PROVIDER_ID = "lvgl-sl"
_SAARLAND_BBOX = (6.36, 49.11, 7.40, 49.64)  # W, S, E, N (WGS84)

_WCS_BASE = "https://geoportal.saarland.de/gdi-sl/inspireraster/inspirewcsel"
_COVERAGE_ID = "EL.GridCoverage"


def locate_tiles(
    dataset: str,
    *,
    config: dict[str, Any],
    geometry: str,
    geometry_type: str,
    timeout: int,
) -> list[dict[str, str]]:
    geom_wgs84 = request_geometry(geometry, geometry_type)
    if not geom_wgs84.intersects(box(*_SAARLAND_BBOX)):
        return []
    geom_32 = to_utm32(geom_wgs84)
    cells = _tile_cells(geom_32)
    if len(cells) > MAX_TILES_PER_DATASET:
        raise ValueError(
            f"Saarland selection resolves to {len(cells)} 1 km tiles. "
            f"Limit the area to {MAX_TILES_PER_DATASET} tiles per dataset."
        )
    return [_tile_record(e_m, n_m) for e_m, n_m in cells]


def summarize_tiles(
    dataset: str,
    *,
    config: dict[str, Any],
    geometry: str,
    geometry_type: str,
    timeout: int,
) -> list[dict[str, str]]:
    return [
        {
            "provider": PROVIDER_ID,
            "dataset": dataset,
            "tile_id": tile["tile_id"],
            "updated": None,
            "primary_url": tile["primary_url"],
            "source": "https://geoportal.saarland.de/",
        }
        for tile in locate_tiles(
            dataset,
            config=config,
            geometry=geometry,
            geometry_type=geometry_type,
            timeout=timeout,
        )
    ]


def _tile_cells(geometry) -> list[tuple[int, int]]:
    """Return (e_m, n_m) SW-corner metre origins for 1 km cells intersecting *geometry*.

    geometry must already be in EPSG:25832.
    """
    west, south, east, north = geometry.bounds
    e_start = math.floor(west / TILE_SIZE_M) * TILE_SIZE_M
    e_end = math.floor(east / TILE_SIZE_M) * TILE_SIZE_M
    n_start = math.floor(south / TILE_SIZE_M) * TILE_SIZE_M
    n_end = math.floor(north / TILE_SIZE_M) * TILE_SIZE_M
    return [
        (e, n)
        for e in range(e_start, e_end + TILE_SIZE_M, TILE_SIZE_M)
        for n in range(n_start, n_end + TILE_SIZE_M, TILE_SIZE_M)
        if geometry.intersects(box(e, n, e + TILE_SIZE_M, n + TILE_SIZE_M))
    ]


def _tile_record(e_m: int, n_m: int) -> dict[str, str]:
    tile_id = f"sl_dgm1_{e_m}_{n_m}"
    url = (
        f"{_WCS_BASE}?request=GetCoverage&service=WCS&version=2.0.1"
        f"&coverageid={_COVERAGE_ID}&FORMAT=image/tiff"
        f"&SUBSET=E({e_m},{e_m + TILE_SIZE_M})"
        f"&SUBSET=N({n_m},{n_m + TILE_SIZE_M})"
    )
    return {"tile_id": tile_id, "primary_url": url}
