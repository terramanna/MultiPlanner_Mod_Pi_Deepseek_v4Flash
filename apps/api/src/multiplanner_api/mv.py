"""WCS 2.0.1 adapter for LAiV Mecklenburg-Vorpommern DGM1/DOM1.

Endpoints:   dgm1 → https://www.geodaten-mv.de/dienste/dgm_wcs  (coverage mv_dgm)
             dom1 → https://www.geodaten-mv.de/dienste/dom_wcs  (coverage mv_dom)
Axis labels: x (easting), y (northing) — from DescribeCoverage gml:axisLabels
CRS:         EPSG:25833 (ETRS89 / UTM Zone 33N)
Format:      image/tiff
Extent:      x 200000–465000, y 5886000–6075000
License:     CC BY 4.0

Tile size: 1 km × 1 km.
"""

from __future__ import annotations

import json
import math
from typing import Any

from pyproj import Transformer
from shapely.geometry import Point, Polygon, box
from shapely.ops import transform

WGS84 = "EPSG:4326"
ETRS89_UTM33 = "EPSG:25833"
TILE_SIZE_M = 1000
MAX_TILES_PER_DATASET = 200
PROVIDER_ID = "laiv-mv"

_WCS_CONFIGS: dict[str, tuple[str, str]] = {
    "dgm1": ("https://www.geodaten-mv.de/dienste/dgm_wcs", "mv_dgm"),
    "dom1": ("https://www.geodaten-mv.de/dienste/dom_wcs", "mv_dom"),
}


def locate_tiles(
    dataset: str,
    *,
    config: dict[str, Any],
    geometry: str,
    geometry_type: str,
    timeout: int,
) -> list[dict[str, str]]:
    geom_33 = _to_utm33(request_geometry(geometry, geometry_type))
    cells = _tile_cells(geom_33)
    if len(cells) > MAX_TILES_PER_DATASET:
        raise ValueError(
            f"Mecklenburg-Vorpommern selection resolves to {len(cells)} 1 km tiles. "
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
            "source": "https://www.geodaten-mv.de/",
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
    raise ValueError(f"Unsupported Mecklenburg-Vorpommern geometry type: {geometry_type}")


def _to_utm33(geometry):
    transformer = Transformer.from_crs(WGS84, ETRS89_UTM33, always_xy=True)
    return transform(transformer.transform, geometry)


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
    endpoint, coverage_id = _WCS_CONFIGS[dataset]
    tile_id = f"mv_{dataset}_{x_m}_{y_m}"
    url = (
        f"{endpoint}?request=GetCoverage&service=WCS&version=2.0.1"
        f"&coverageid={coverage_id}&FORMAT=image/tiff"
        f"&SUBSET=x({x_m},{x_m + TILE_SIZE_M})"
        f"&SUBSET=y({y_m},{y_m + TILE_SIZE_M})"
    )
    return {"tile_id": tile_id, "primary_url": url}
