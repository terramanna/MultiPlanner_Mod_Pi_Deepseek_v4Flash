"""Bulk-ZIP adapter for Landesamt Geoinformation Bremen (FHB).

Bremen distributes data as one ZIP per city (Bremen + Bremerhaven).

Dataset   ZIPs                                                                Format
dgm1      gdi2.geo.bremen.de/inspire/download/DGM/data/Gitternetz_DGM1_…    ASCII XYZ
dom1      gdi2.geo.bremen.de/inspire/download/DOM/data/Gitternetz_DOM1_…    ASCII XYZ
lod2      gdi2.geo.bremen.de/inspire/download/LoD/data/LOD2_CITYGML_…      CityGML

CRS:  EPSG:25832 (ETRS89 / UTM Zone 32N)
License: CC BY 4.0 — Landesamt GeoInformation Bremen

locate_tiles returns the ZIP(s) whose city bbox intersects the request geometry
(0–2 results per dataset). Geometry input is WGS84.
"""

from __future__ import annotations

import json
from typing import Any

from shapely.geometry import Point, Polygon, box

PROVIDER_ID = "lginf-hb"

_BASE = "https://gdi2.geo.bremen.de/inspire/download"

# WGS84 bounding boxes (conservative) for each city.
_HB_BBOX = box(8.4766, 52.9960, 8.9910, 53.2280)
_BHV_BBOX = box(8.4930, 53.4700, 8.6290, 53.6140)

_CITY_TILES: dict[str, list[dict]] = {
    "dgm1": [
        {
            "tile_id": "hb_dgm1_HB",
            "bbox": _HB_BBOX,
            "primary_url": f"{_BASE}/DGM/data/Gitternetz_DGM1_2017_HB_ASCII_XYZ.zip",
        },
        {
            "tile_id": "hb_dgm1_BHV",
            "bbox": _BHV_BBOX,
            "primary_url": f"{_BASE}/DGM/data/Gitternetz_DGM1_2015_BHV_ASCII_XYZ.zip",
        },
    ],
    "dom1": [
        {
            "tile_id": "hb_dom1_HB",
            "bbox": _HB_BBOX,
            "primary_url": f"{_BASE}/DOM/data/Gitternetz_DOM1_2017_HB_ASCII_XYZ.zip",
        },
        {
            "tile_id": "hb_dom1_BHV",
            "bbox": _BHV_BBOX,
            "primary_url": f"{_BASE}/DOM/data/Gitternetz_DOM1_2015_BHV_ASCII_XYZ.zip",
        },
    ],
    "lod2": [
        {
            "tile_id": "hb_lod2_HB",
            "bbox": _HB_BBOX,
            "primary_url": f"{_BASE}/LoD/data/LOD2_CITYGML_HB.zip",
        },
        {
            "tile_id": "hb_lod2_BHV",
            "bbox": _BHV_BBOX,
            "primary_url": f"{_BASE}/LoD/data/LOD2_CITYGML_BHV.zip",
        },
    ],
}


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
        for city in _CITY_TILES[dataset]
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
            "source": f"{_BASE}/",
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
