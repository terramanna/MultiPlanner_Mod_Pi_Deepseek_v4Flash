"""WCS 2.0.1 adapter for LVermGeo Sachsen-Anhalt DGM1/DOM1.

Endpoints:  dgm1 → …/ST_LVermGeo_DGM1_WCS_OpenData/guest  (Coverage1)
            dom1 → …/ST_LVermGeo_DOM1_WCS_OpenData/guest  (Coverage1)
Axis labels: x (easting), y (northing) — from DescribeCoverage gml:axisLabels
CRS:        EPSG:25832 (ETRS89 / UTM Zone 32N)
Format:     image/tiff
Extent:     x 606000–790000, y 5646000–5882000

Tile size: 1 km × 1 km (consistent with NRW/HE tile granularity).
"""

from __future__ import annotations
from multiplanner_shared.geometry_io import request_geometry, to_utm32

import json
import math
from typing import Any

from shapely.geometry import Point, Polygon, box

WCS_TILE_SIZE_M = 1000
DOP20_TILE_SIZE_M = 2000
MAX_TILES_PER_DATASET = 200
PROVIDER_ID = "lvermgeo-st"
_SAXONY_ANHALT_BBOX = (10.56, 51.15, 13.18, 53.05)  # W, S, E, N (WGS84)

_ST_WCS_BASE = "https://www.geodatenportal.sachsen-anhalt.de/wss/service"
_WCS_CONFIGS: dict[str, tuple[str, str]] = {
    "dgm1": (f"{_ST_WCS_BASE}/ST_LVermGeo_DGM1_WCS_OpenData/guest", "Coverage1"),
    "dom1": ("https://geodatenportal.sachsen-anhalt.de/ows_WCS_ST_DOM1", "Coverage1"),
}
_DOP20_BASE = "https://www.geodatenportal.sachsen-anhalt.de/gfds_webshare/sec-download/LVermGeo/DOP20"


def locate_tiles(
    dataset: str,
    *,
    config: dict[str, Any],
    geometry: str,
    geometry_type: str,
    timeout: int,
) -> list[dict[str, str]]:
    geom_wgs84 = request_geometry(geometry, geometry_type)
    if not geom_wgs84.intersects(box(*_SAXONY_ANHALT_BBOX)):
        return []
    geom_32 = to_utm32(geom_wgs84)
    if dataset == "lod2":
        return [
            {"tile_id": f"st_lod2_{i + 1}", "primary_url": url}
            for i, url in enumerate(_ST_LOD2_URLS)
        ]
    if dataset == "dop20":
        cells = _tile_cells(geom_32, DOP20_TILE_SIZE_M)
        if len(cells) > MAX_TILES_PER_DATASET:
            raise ValueError(
                f"Saxony-Anhalt selection resolves to {len(cells)} 2 km tiles. "
                f"Limit the area to {MAX_TILES_PER_DATASET} tiles per dataset."
            )
        return [_dop20_tile_record(x_m, y_m) for x_m, y_m in cells]
    cells = _tile_cells(geom_32, WCS_TILE_SIZE_M)
    if len(cells) > MAX_TILES_PER_DATASET:
        raise ValueError(
            f"Saxony-Anhalt selection resolves to {len(cells)} 1 km tiles. "
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
    return [
        {
            "provider": PROVIDER_ID,
            "dataset": dataset,
            "tile_id": tile["tile_id"],
            "updated": None,
            "primary_url": tile["primary_url"],
            "source": "https://www.geodatenportal.sachsen-anhalt.de/",
        }
        for tile in locate_tiles(
            dataset,
            config=config,
            geometry=geometry,
            geometry_type=geometry_type,
            timeout=timeout,
        )
    ]


_ST_LOD2_URLS = [
    "https://www.geodatenportal.sachsen-anhalt.de/gfds_webshare/download/LVermGeo/Geodatenportal/Online-Bereitstellung-LVermGeo/3D/LoD2-1.zip",
    "https://www.geodatenportal.sachsen-anhalt.de/gfds_webshare/download/LVermGeo/Geodatenportal/Online-Bereitstellung-LVermGeo/3D/LoD2-2.zip",
    "https://www.geodatenportal.sachsen-anhalt.de/gfds_webshare/download/LVermGeo/Geodatenportal/Online-Bereitstellung-LVermGeo/3D/LoD2-3.zip",
    "https://www.geodatenportal.sachsen-anhalt.de/gfds_webshare/download/LVermGeo/Geodatenportal/Online-Bereitstellung-LVermGeo/3D/LoD2-4.zip",
]


def _tile_cells(geometry, tile_size: int) -> list[tuple[int, int]]:
    """Return (x_m, y_m) SW-corner metre origins for *tile_size* cells intersecting *geometry*.

    geometry must already be in EPSG:25832.
    """
    west, south, east, north = geometry.bounds
    x_start = math.floor(west / tile_size) * tile_size
    x_end = math.floor(east / tile_size) * tile_size
    y_start = math.floor(south / tile_size) * tile_size
    y_end = math.floor(north / tile_size) * tile_size
    return [
        (x, y)
        for x in range(x_start, x_end + tile_size, tile_size)
        for y in range(y_start, y_end + tile_size, tile_size)
        if geometry.intersects(box(x, y, x + tile_size, y + tile_size))
    ]


def _tile_record(dataset: str, x_m: int, y_m: int) -> dict[str, str]:
    endpoint, coverage_id = _WCS_CONFIGS[dataset]
    tile_id = f"st_{dataset}_{x_m}_{y_m}"
    url = (
        f"{endpoint}?request=GetCoverage&service=WCS&version=2.0.1"
        f"&coverageid={coverage_id}&FORMAT=image/tiff"
        f"&SUBSET=x({x_m},{x_m + WCS_TILE_SIZE_M})"
        f"&SUBSET=y({y_m},{y_m + WCS_TILE_SIZE_M})"
    )
    return {"tile_id": tile_id, "primary_url": url}


def _dop20_tile_record(x_m: int, y_m: int) -> dict[str, str]:
    east_km = x_m // 1000
    north_km = y_m // 1000
    tile_name = f"32{east_km}{north_km}"
    return {
        "tile_id": f"st_dop20_{tile_name}",
        "primary_url": f"{_DOP20_BASE}/{tile_name}.tif",
    }
