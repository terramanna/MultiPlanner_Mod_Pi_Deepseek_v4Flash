"""Hamburg FHH DGM1 adapter via OGC API Features + DAV download.

Tile catalog:  https://api.hamburg.de/datasets/v1/uebersicht_kachelbezeichnungen/
               collections/lgv_kachel_dgm_2km_utm/items?bbox=...
Tile download: https://daten-hamburg.de/DAV/DGM1/{dateiname_dgm_1}
File format:   ASCII XYZ (.xyz), EPSG:25832
Tile size:     2 km × 2 km; 244 tiles cover the Hamburg city-state
Dataset:       dgm1 only (no WCS or DOM1 available)
"""

from __future__ import annotations

import json
from typing import Any

import requests
from shapely.geometry import Point, Polygon, box

MAX_TILES_PER_DATASET = 100
PROVIDER_ID = "lgv-hh"

_OGC_API_URL = (
    "https://api.hamburg.de/datasets/v1/uebersicht_kachelbezeichnungen"
    "/collections/lgv_kachel_dgm_2km_utm/items"
)
_DAV_BASE = "https://daten-hamburg.de/DAV/DGM1"


def locate_tiles(
    dataset: str,
    *,
    config: dict[str, Any],
    geometry: str,
    geometry_type: str,
    timeout: int,
) -> list[dict[str, str]]:
    geom = request_geometry(geometry, geometry_type)
    west, south, east, north = _ensure_bbox_extent(*geom.bounds)
    features = _query_ogc_api(west, south, east, north, timeout)
    if len(features) > MAX_TILES_PER_DATASET:
        raise ValueError(
            f"Hamburg selection resolves to {len(features)} 2 km tiles. "
            f"Limit the area to {MAX_TILES_PER_DATASET} tiles per dataset."
        )
    return [_tile_record(feat["properties"]) for feat in features]


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
            "source": "https://daten-hamburg.de/",
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
    raise ValueError(f"Unsupported Hamburg geometry type: {geometry_type}")


def _ensure_bbox_extent(
    west: float, south: float, east: float, north: float, eps: float = 0.001
) -> tuple[float, float, float, float]:
    """Expand a degenerate bbox (e.g. a point) to a minimum extent so the OGC
    API spatial filter intersects correctly."""
    if east - west < eps:
        cx = (west + east) / 2
        west, east = cx - eps / 2, cx + eps / 2
    if north - south < eps:
        cy = (south + north) / 2
        south, north = cy - eps / 2, cy + eps / 2
    return west, south, east, north


def _query_ogc_api(
    west: float, south: float, east: float, north: float, timeout: int
) -> list[dict]:
    """Return all features from the Hamburg tile catalog that intersect the bbox.

    Hamburg has 244 2km tiles; limit=300 fetches them all in one request.
    """
    response = requests.get(
        _OGC_API_URL,
        params={"bbox": f"{west},{south},{east},{north}", "f": "json", "limit": 300},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json().get("features", [])


def _tile_record(properties: dict) -> dict[str, str]:
    filename = properties["dateiname_dgm_1"]
    tile_id = "hh_dgm1_" + filename.removesuffix(".xyz")
    return {"tile_id": tile_id, "primary_url": f"{_DAV_BASE}/{filename}"}
