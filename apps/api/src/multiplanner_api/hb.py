"""Bulk-ZIP adapter for Landesamt Geoinformation Bremen (FHB) DGM1.

Bremen offers no WCS or per-tile API; the entire DGM1 for each city is
distributed as a single ASCII XYZ ZIP file via INSPIRE ATOM.

City ZIPs (CC BY 4.0):
  Bremen (2017):      https://gdi2.geo.bremen.de/inspire/download/DGM/data/Gitternetz_DGM1_2017_HB_ASCII_XYZ.zip
  Bremerhaven (2015): https://gdi2.geo.bremen.de/inspire/download/DGM/data/Gitternetz_DGM1_2015_BHV_ASCII_XYZ.zip

CRS:    EPSG:25832 (ETRS89 / UTM Zone 32N)
Format: ASCII XYZ

locate_tiles returns the ZIP(s) whose city bbox intersects the request geometry
(0-2 results). Geometry input is WGS84 — no reprojection needed for the coarse
city-level intersection check.
"""

from __future__ import annotations

import json
from typing import Any

from shapely.geometry import Point, Polygon, box

PROVIDER_ID = "lginf-hb"

# WGS84 bounding boxes (conservative) for each city ZIP.
_CITY_TILES = [
    {
        "tile_id": "hb_dgm1_HB",
        "bbox": box(8.4766, 52.9960, 8.9910, 53.2280),
        "primary_url": (
            "https://gdi2.geo.bremen.de/inspire/download/DGM/data"
            "/Gitternetz_DGM1_2017_HB_ASCII_XYZ.zip"
        ),
    },
    {
        "tile_id": "hb_dgm1_BHV",
        "bbox": box(8.4930, 53.4700, 8.6290, 53.6140),
        "primary_url": (
            "https://gdi2.geo.bremen.de/inspire/download/DGM/data"
            "/Gitternetz_DGM1_2015_BHV_ASCII_XYZ.zip"
        ),
    },
]


def locate_tiles(
    dataset: str,
    *,
    config: dict[str, Any],
    geometry: str,
    geometry_type: str,
    timeout: int,
) -> list[dict[str, str]]:
    geom = request_geometry(geometry, geometry_type)
    return [
        {"tile_id": city["tile_id"], "primary_url": city["primary_url"]}
        for city in _CITY_TILES
        if geom.intersects(city["bbox"])
    ]


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
            "source": "https://gdi2.geo.bremen.de/",
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
    raise ValueError(f"Unsupported Bremen geometry type: {geometry_type}")
