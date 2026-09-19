"""Hamburg FHH adapter via OGC API Features (DGM1) and bulk download (bDOM/LOD2).

dgm1     OGC API + DAV:  https://api.hamburg.de/datasets/v1/…/lgv_kachel_dgm_2km_utm
         Download:       https://daten-hamburg.de/DAV/DGM1/{dateiname_dgm_1}
         Format:         ASCII XYZ (.xyz), EPSG:25832, 2 km × 2 km tiles
bdom     Single ZIP:     https://daten-hamburg.de/opendata/Digitales_Hoehenmodell_bDOM/
dom1_hh_2022-11-21.zip
lod2     Single GML:     https://archiv.transparenz.hamburg.de/hmbtgarchive/HMDK/
lod2-de_hh_2016-11-22_21283_snap_1.GML
"""

from __future__ import annotations
from multiplanner_shared.geometry_io import request_geometry

import json
from typing import Any

from shapely.geometry import Point, Polygon, box

from multiplanner_api.http_client import get_with_ssl_fallback

MAX_TILES_PER_DATASET = 100
PROVIDER_ID = "lgv-hh"

_OGC_API_URL = (
    "https://api.hamburg.de/datasets/v1/uebersicht_kachelbezeichnungen"
    "/collections/lgv_kachel_dgm_2km_utm/items"
)
_DAV_BASE = "https://daten-hamburg.de/DAV/DGM1"

_HH_BBOX = box(9.70, 53.35, 10.35, 53.80)

_BDOM_BASE = "https://daten-hamburg.de/opendata/Digitales_Hoehenmodell_bDOM"
_LOD2_BASE = "https://archiv.transparenz.hamburg.de/hmbtgarchive/HMDK"

_BULK_TILES: dict[str, dict] = {
    "bdom": {
        "tile_id": "hh_bdom_HH",
        "primary_url": f"{_BDOM_BASE}/dom1_hh_2022-11-21.zip",
    },
    "dom1": {
        "tile_id": "hh_bdom_HH",
        "primary_url": f"{_BDOM_BASE}/dom1_hh_2022-11-21.zip",
    },
    "lod2": {
        "tile_id": "hh_lod2_HH",
        "primary_url": f"{_LOD2_BASE}/lod2-de_hh_2016-11-22_21283_snap_1.GML",
    },
}


def locate_tiles(
    dataset: str,
    *,
    config: dict[str, Any],
    geometry: str,
    geometry_type: str,
    timeout: int,
) -> list[dict[str, str]]:
    if dataset in _BULK_TILES:
        return _locate_bulk(dataset, geometry, geometry_type)
    geom = request_geometry(geometry, geometry_type)
    west, south, east, north = _ensure_bbox_extent(*geom.bounds)
    features = _query_ogc_api(west, south, east, north, timeout)
    if len(features) > MAX_TILES_PER_DATASET:
        raise ValueError(
            f"Hamburg selection resolves to {len(features)} 2 km tiles. "
            f"Limit the area to {MAX_TILES_PER_DATASET} tiles per dataset."
        )
    return [_tile_record(feat["properties"]) for feat in features]


def _locate_bulk(dataset: str, geometry: str, geometry_type: str) -> list[dict[str, str]]:
    geom = request_geometry(geometry, geometry_type)
    entry = _BULK_TILES[dataset]
    if not geom.intersects(_HH_BBOX):
        return []
    return [{"tile_id": entry["tile_id"], "primary_url": entry["primary_url"]}]


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
    response = get_with_ssl_fallback(
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
