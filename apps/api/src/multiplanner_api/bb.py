"""WCS 2.0.1 / direct-download adapter for Geobasis Brandenburg.

Dataset     Endpoint / base URL                                      CRS
dgm1        https://isk.geobasis-bb.de/ows/dgm_wcs  (bb_dgm)        EPSG:25833
bdom        https://isk.geobasis-bb.de/ows/bdom_wcs (bb_bdom)       EPSG:25833
lod2        https://data.geobasis-bb.de/geobasis/daten/3d_gebaeude/lod2_gml/

Axis labels: x (easting), y (northing)
Tile size: 1 km × 1 km; LOD2 uses the same grid.
LOD2 filename: lod2_33{easting_km:03d}-{northing_km:04d}.zip
"""

from __future__ import annotations
from multiplanner_shared.geometry_io import request_geometry, to_utm33

import json
import math
from typing import Any

from shapely.geometry import Point, Polygon, box

TILE_SIZE_M = 1000
MAX_TILES_PER_DATASET = 200
PROVIDER_ID = "geobasis-bb"
_BRANDENBURG_BBOX = (11.26, 51.36, 14.76, 53.56)  # W, S, E, N (WGS84)

_WCS_CONFIGS: dict[str, dict[str, str]] = {
    "dgm1": {
        "endpoint": "https://isk.geobasis-bb.de/ows/dgm_wcs",
        "coverage_id": "bb_dgm",
    },
    "bdom": {
        "endpoint": "https://isk.geobasis-bb.de/ows/bdom_wcs",
        "coverage_id": "bb_bdom",
    },
    "dom1": {
        "endpoint": "https://isk.geobasis-bb.de/ows/bdom_wcs",
        "coverage_id": "bb_bdom",
    },
}
_LOD2_BASE = "https://data.geobasis-bb.de/geobasis/daten/3d_gebaeude/lod2_gml/"


def locate_tiles(
    dataset: str,
    *,
    config: dict[str, Any],
    geometry: str,
    geometry_type: str,
    timeout: int,
) -> list[dict[str, str]]:
    geom_wgs84 = request_geometry(geometry, geometry_type)
    if not geom_wgs84.intersects(box(*_BRANDENBURG_BBOX)):
        return []
    geom_33 = to_utm33(geom_wgs84)
    cells = _tile_cells(geom_33)
    if len(cells) > MAX_TILES_PER_DATASET:
        raise ValueError(
            f"Brandenburg selection resolves to {len(cells)} 1 km tiles. "
            f"Limit the area to {MAX_TILES_PER_DATASET} tiles per dataset."
        )
    return [_tile_record(dataset, x_m, y_m) for x_m, y_m in cells]


def summarize_tiles(
    dataset: str,
    *,
    config: dict[str, Any],
    geometry: str,
    geometry_type: str,
    timeout: int,
) -> list[dict[str, str]]:
    source = (
        _LOD2_BASE
        if dataset == "lod2"
        else "https://isk.geobasis-bb.de/"
    )
    return [
        {
            "provider": PROVIDER_ID,
            "dataset": dataset,
            "tile_id": tile["tile_id"],
            "updated": None,
            "primary_url": tile["primary_url"],
            "source": source,
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
    """Return (x_m, y_m) SW-corner metre origins for 1 km cells intersecting *geometry*.

    geometry must already be in EPSG:25833.
    """
    west, south, east, north = geometry.bounds
    x_start = math.floor(west / TILE_SIZE_M) * TILE_SIZE_M
    x_end = math.floor(east / TILE_SIZE_M) * TILE_SIZE_M
    y_start = math.floor(south / TILE_SIZE_M) * TILE_SIZE_M
    y_end = math.floor(north / TILE_SIZE_M) * TILE_SIZE_M
    return [
        (x, y)
        for x in range(x_start, x_end + TILE_SIZE_M, TILE_SIZE_M)
        for y in range(y_start, y_end + TILE_SIZE_M, TILE_SIZE_M)
        if geometry.intersects(box(x, y, x + TILE_SIZE_M, y + TILE_SIZE_M))
    ]


def _tile_record(dataset: str, x_m: int, y_m: int) -> dict[str, str]:
    tile_id = f"bb_{dataset}_{x_m}_{y_m}"
    if dataset == "lod2":
        fname = f"lod2_33{x_m // 1000:03d}-{y_m // 1000:04d}.zip"
        url = f"{_LOD2_BASE}{fname}"
    else:
        cfg = _WCS_CONFIGS[dataset]
        url = (
            f"{cfg['endpoint']}?request=GetCoverage&service=WCS&version=2.0.1"
            f"&coverageid={cfg['coverage_id']}&FORMAT=image/tiff"
            f"&SUBSET=x({x_m},{x_m + TILE_SIZE_M})"
            f"&SUBSET=y({y_m},{y_m + TILE_SIZE_M})"
        )
    return {"tile_id": tile_id, "primary_url": url}
