"""INSPIRE WCS 2.0.1 adapter for HVBG Hessen DGM1/DOM1.

Endpoint:  https://inspirehessen.de/raster/{dataset}/ows
Coverage IDs: dgm1 → he_dgm1, dom1 → dom1
CRS:       EPSG:25832 (ETRS89 / UTM Zone 32N)
Tile size: 1 km × 1 km (matches NRW grid; avoids large single requests)

WCS GetCoverage example (from HVBG official guide, 2025-05):
  https://inspirehessen.de/raster/dgm1/ows?request=GetCoverage&service=WCS
    &version=2.0.1&coverageid=he_dgm1&FORMAT=GTIFF
    &SUBSET=e(514145,518345)&SUBSET=n(5593248,5597467)
"""

from __future__ import annotations

import json
import math
from typing import Any

from pyproj import Transformer
from shapely.geometry import Point, Polygon, box
from shapely.ops import transform

WGS84 = "EPSG:4326"
ETRS89_UTM32 = "EPSG:25832"
TILE_SIZE_M = 1000
MAX_TILES_PER_DATASET = 200
PROVIDER_ID = "hvbg-he"
_HESSEN_BBOX = (7.77, 49.39, 10.24, 51.66)  # W, S, E, N (WGS84)

_WCS_BASE = "https://inspirehessen.de/raster/{dataset}/ows"
_COVERAGE_IDS: dict[str, str] = {"dgm1": "he_dgm1", "dom1": "dom1", "dop20": "he_dop20"}


def locate_tiles(
    dataset: str,
    *,
    config: dict[str, Any],
    geometry: str,
    geometry_type: str,
    timeout: int,
) -> list[dict[str, str]]:
    geom_wgs84 = request_geometry(geometry, geometry_type)
    if not geom_wgs84.intersects(box(*_HESSEN_BBOX)):
        return []
    geom_32 = _to_utm32(geom_wgs84)
    cells = _tile_cells(geom_32)
    if len(cells) > MAX_TILES_PER_DATASET:
        raise ValueError(
            f"Hessen selection resolves to {len(cells)} 1 km tiles. "
            f"Limit the area to {MAX_TILES_PER_DATASET} tiles per dataset."
        )
    wcs_base = _WCS_BASE.format(dataset=dataset)
    coverage_id = _COVERAGE_IDS.get(dataset, f"he_{dataset}")
    return [_tile_record(dataset, e_m, n_m, wcs_base, coverage_id) for e_m, n_m in cells]


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
            "source": "https://inspirehessen.de/",
        }
        for tile in locate_tiles(
            dataset,
            config=config,
            geometry=geometry,
            geometry_type=geometry_type,
            timeout=timeout,
        )
    ]


def request_geometry(geometry: str, geometry_type: str):
    if geometry_type == "esriGeometryPoint":
        lon, lat = (float(v) for v in geometry.split(",", maxsplit=1))
        return Point(lon, lat)
    payload = json.loads(geometry)
    if geometry_type == "esriGeometryEnvelope":
        return box(payload["xmin"], payload["ymin"], payload["xmax"], payload["ymax"])
    if geometry_type == "esriGeometryPolygon":
        return Polygon(payload["rings"][0])
    raise ValueError(f"Unsupported Hessen geometry type: {geometry_type}")


def _to_utm32(geometry):
    transformer = Transformer.from_crs(WGS84, ETRS89_UTM32, always_xy=True)
    return transform(transformer.transform, geometry)


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


def _tile_record(
    dataset: str, e_m: int, n_m: int, wcs_base: str, coverage_id: str
) -> dict[str, str]:
    tile_id = f"he_{dataset}_{e_m}_{n_m}"
    url = (
        f"{wcs_base}?request=GetCoverage&service=WCS&version=2.0.1"
        f"&coverageid={coverage_id}&FORMAT=GTIFF"
        f"&SUBSET=e({e_m},{e_m + TILE_SIZE_M})"
        f"&SUBSET=n({n_m},{n_m + TILE_SIZE_M})"
    )
    return {"tile_id": tile_id, "primary_url": url}
