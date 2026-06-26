"""Schleswig-Holstein DGM1 adapter via GeoJSON tile index + mass download.

Tile index:  https://geodaten.schleswig-holstein.de/gaialight-sh/_apps/dladownload/
             single.php?file=DGM1_SH__Massendownload.geojson&id=4
Download:    link_data field in each GeoJSON feature (.xyz files)
File format: ASCII XYZ (.xyz), EPSG:25832
Tile size:   1 km x 1 km; ~278 tiles cover Schleswig-Holstein
Dataset:     dgm1 only
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests
from pyproj import Transformer
from shapely.geometry import Point, Polygon, box, shape
from shapely.ops import transform

from multiplanner_api.config import load_settings

WGS84 = "EPSG:4326"
ETRS89_UTM32 = "EPSG:25832"
PROVIDER_ID = "lvermgeo-sh"
MAX_TILES_PER_DATASET = 200
CACHE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60

_GEOJSON_URL = (
    "https://geodaten.schleswig-holstein.de/gaialight-sh/_apps/dladownload/"
    "single.php?file=DGM1_SH__Massendownload.geojson&id=4"
)


def locate_tiles(
    dataset: str,
    *,
    config: dict[str, Any],
    geometry: str,
    geometry_type: str,
    timeout: int,
) -> list[dict[str, str]]:
    geom_utm32 = _to_utm32(request_geometry(geometry, geometry_type))
    tiles = _load_index(timeout=timeout)
    matching = [t for t in tiles if _tile_shape(t).intersects(geom_utm32)]
    if len(matching) > MAX_TILES_PER_DATASET:
        raise ValueError(
            f"Schleswig-Holstein selection resolves to {len(matching)} 1 km tiles. "
            f"Limit the area to {MAX_TILES_PER_DATASET} tiles per dataset."
        )
    return [{"tile_id": f"sh_dgm1_{t['kachel']}", "primary_url": t["link_data"], "datum": t["datum"]} for t in matching]


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
            "updated": tile["datum"],
            "primary_url": tile["primary_url"],
            "source": "https://geodaten.schleswig-holstein.de/",
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
    raise ValueError(f"Unsupported Schleswig-Holstein geometry type: {geometry_type}")


def _to_utm32(geometry):
    transformer = Transformer.from_crs(WGS84, ETRS89_UTM32, always_xy=True)
    return transform(transformer.transform, geometry)


def _load_index(*, timeout: int) -> list[dict]:
    path = _cache_path()
    if path.exists() and time.time() - path.stat().st_mtime < CACHE_MAX_AGE_SECONDS:
        return json.loads(path.read_text(encoding="utf-8"))
    response = requests.get(_GEOJSON_URL, timeout=timeout)
    response.raise_for_status()
    entries = _parse_geojson(response.json())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, separators=(",", ":")), encoding="utf-8")
    return entries


def _cache_path() -> Path:
    return Path(load_settings().cache_root) / "provider_indexes" / "geodaten_sh_dgm1.json"


def _parse_geojson(geojson: dict) -> list[dict]:
    entries = []
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        geom = feature.get("geometry")
        if not geom or not props.get("kachel") or not props.get("link_data"):
            continue
        bbox = list(shape(geom).bounds)
        entries.append({
            "kachel": str(props["kachel"]),
            "link_data": str(props["link_data"]),
            "datum": str(props.get("datum", "")),
            "bbox": bbox,
        })
    return entries


def _tile_shape(tile: dict):
    xmin, ymin, xmax, ymax = tile["bbox"]
    return box(xmin, ymin, xmax, ymax)
