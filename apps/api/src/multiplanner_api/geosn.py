"""Tile-locator for GeoSN (Freistaat Sachsen) 2 km GeoTIFF products.

Tiles are fully deterministic from coordinates — no catalog fetch needed.
Download base: https://www.geodaten.sachsen.de/download/
Naming:  {dataset}_33{east_km}_{north_km}_2_sn_tiff.zip
CRS:     EPSG:25833  (ETRS89 / UTM zone 33N)
"""

from __future__ import annotations
from multiplanner_shared.geometry_io import request_geometry

import json
import math
from typing import Any

from pyproj import Transformer
from shapely.geometry import Point, Polygon, box
from shapely.ops import transform

WGS84 = "EPSG:4326"
ETRS89_UTM33 = "EPSG:25833"
TILE_KM = 2
MAX_TILES_PER_DATASET = 100
PROVIDER_ID = "geosn-sn"
# Loose WGS84 bounding box for Saxony.  locate_tiles returns [] for points
# outside this box so auto-provider probes do not attempt spurious downloads.
_SAXONY_BBOX = (11.8, 50.1, 15.1, 51.7)  # W, S, E, N


def locate_tiles(
    dataset: str,
    *,
    config: dict[str, Any],
    geometry: str,
    geometry_type: str,
    timeout: int,
) -> list[dict[str, str]]:
    base_url = config["base_url"]
    file_prefix = config.get("file_prefix", dataset)
    geom_wgs84 = request_geometry(geometry, geometry_type)
    if not geom_wgs84.intersects(box(*_SAXONY_BBOX)):
        return []
    geom_33 = _to_utm33(geom_wgs84)
    candidates = tile_coordinates(geom_33)
    if len(candidates) > MAX_TILES_PER_DATASET:
        raise ValueError(
            f"GeoSN selection resolves to {len(candidates)} 2 km tiles. "
            f"Limit the area to {MAX_TILES_PER_DATASET} tiles per dataset."
        )
    return [_tile_record(file_prefix, east_km, north_km, base_url) for east_km, north_km in candidates]


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
            "source": config["base_url"],
        }
        for tile in locate_tiles(
            dataset,
            config=config,
            geometry=geometry,
            geometry_type=geometry_type,
            timeout=timeout,
        )
    ]




def _to_utm33(geometry):
    transformer = Transformer.from_crs(WGS84, ETRS89_UTM33, always_xy=True)
    return transform(transformer.transform, geometry)


def tile_coordinates(geometry) -> list[tuple[int, int]]:
    """Return (east_km, north_km) SW-corner keys for 2 km tiles intersecting *geometry*.

    Coordinates must already be in EPSG:25833 (metres).
    Keys are multiples of TILE_KM.
    """
    west_m, south_m, east_m, north_m = geometry.bounds
    step_m = TILE_KM * 1000
    e_start = math.floor(west_m / step_m) * TILE_KM
    e_end = math.floor(east_m / step_m) * TILE_KM
    n_start = math.floor(south_m / step_m) * TILE_KM
    n_end = math.floor(north_m / step_m) * TILE_KM
    return [
        (e, n)
        for e in range(e_start, e_end + TILE_KM, TILE_KM)
        for n in range(n_start, n_end + TILE_KM, TILE_KM)
        if geometry.intersects(
            box(e * 1000, n * 1000, (e + TILE_KM) * 1000, (n + TILE_KM) * 1000)
        )
    ]


def _tile_record(dataset: str, east_km: int, north_km: int, base_url: str) -> dict[str, str]:
    tile_id = f"{dataset}_33{east_km}_{north_km}_2_sn"
    return {
        "tile_id": tile_id,
        "primary_url": f"{base_url}{tile_id}_tiff.zip",
    }
