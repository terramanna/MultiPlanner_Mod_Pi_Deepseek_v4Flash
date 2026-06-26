"""Berlin DGM1 adapter via INSPIRE ATOM feed (gdi.berlin.de).

Tile index: https://gdi.berlin.de/data/dgm1/atom/0.atom
Download:   https://gdi.berlin.de/data/dgm1/atom/DGM1_{X_km}_{Y_km}.zip
Format:     ASCII XYZ (CSV), EPSG:25833 (ETRS89 / UTM Zone 33N)
Tile size:  2 km × 2 km; 618 tiles cover Berlin
License:    Datenlizenz Deutschland Zero v2.0

The ATOM feed has one entry containing all 618 <link rel="section"> elements.
Coordinates in the filename are in km (integer), so DGM1_368_5808.zip covers
x=[368000, 370000], y=[5808000, 5810000] in EPSG:25833.
"""

from __future__ import annotations

import json
import math
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import requests
from pyproj import Transformer
from shapely.geometry import Point, Polygon, box
from shapely.ops import transform

from multiplanner_api.config import load_settings

WGS84 = "EPSG:4326"
ETRS89_UTM33 = "EPSG:25833"
TILE_SIZE_M = 2000
MAX_TILES_PER_DATASET = 200
PROVIDER_ID = "gdi-be"
CACHE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60

_ATOM_URL = "https://gdi.berlin.de/data/dgm1/atom/0.atom"
_ATOM_NS = "http://www.w3.org/2005/Atom"


def locate_tiles(
    dataset: str,
    *,
    config: dict[str, Any],
    geometry: str,
    geometry_type: str,
    timeout: int,
) -> list[dict[str, str]]:
    geom_33 = _to_utm33(request_geometry(geometry, geometry_type))
    index = _load_index(timeout=timeout)
    matching = _intersecting_tiles(geom_33, index)
    if len(matching) > MAX_TILES_PER_DATASET:
        raise ValueError(
            f"Berlin selection resolves to {len(matching)} 2 km tiles. "
            f"Limit the area to {MAX_TILES_PER_DATASET} tiles per dataset."
        )
    return matching


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
            "source": "https://gdi.berlin.de/",
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
    raise ValueError(f"Unsupported Berlin geometry type: {geometry_type}")


def _to_utm33(geometry):
    transformer = Transformer.from_crs(WGS84, ETRS89_UTM33, always_xy=True)
    return transform(transformer.transform, geometry)


def _intersecting_tiles(geom_33, index: dict[tuple[int, int], str]) -> list[dict[str, str]]:
    west, south, east, north = geom_33.bounds
    x_start = math.floor(west / TILE_SIZE_M) * TILE_SIZE_M
    x_end = math.floor(east / TILE_SIZE_M) * TILE_SIZE_M
    y_start = math.floor(south / TILE_SIZE_M) * TILE_SIZE_M
    y_end = math.floor(north / TILE_SIZE_M) * TILE_SIZE_M
    results = []
    for x_m in range(x_start, x_end + TILE_SIZE_M, TILE_SIZE_M):
        for y_m in range(y_start, y_end + TILE_SIZE_M, TILE_SIZE_M):
            key = (x_m // 1000, y_m // 1000)
            url = index.get(key)
            if url and geom_33.intersects(box(x_m, y_m, x_m + TILE_SIZE_M, y_m + TILE_SIZE_M)):
                tile_id = f"be_dgm1_{key[0]}_{key[1]}"
                results.append({"tile_id": tile_id, "primary_url": url})
    return results


def _load_index(*, timeout: int) -> dict[tuple[int, int], str]:
    path = _cache_path()
    if path.exists() and time.time() - path.stat().st_mtime < CACHE_MAX_AGE_SECONDS:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {(e["x_km"], e["y_km"]): e["url"] for e in raw}
    response = requests.get(_ATOM_URL, timeout=timeout)
    response.raise_for_status()
    entries = _parse_atom(response.text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, separators=(",", ":")), encoding="utf-8")
    return {(e["x_km"], e["y_km"]): e["url"] for e in entries}


def _cache_path() -> Path:
    return Path(load_settings().cache_root) / "provider_indexes" / "gdi_be_dgm1.json"


def _parse_atom(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    ns = {"atom": _ATOM_NS}
    entries = []
    for link in root.iter(f"{{{_ATOM_NS}}}link"):
        if link.get("rel") != "section":
            continue
        href = link.get("href", "")
        coords = _parse_coords(href)
        if coords:
            x_km, y_km = coords
            entries.append({"x_km": x_km, "y_km": y_km, "url": href})
    return entries


def _parse_coords(href: str) -> tuple[int, int] | None:
    """Extract (x_km, y_km) from a URL like .../DGM1_368_5808.zip."""
    filename = href.rsplit("/", 1)[-1]
    if not filename.startswith("DGM1_") or not filename.endswith(".zip"):
        return None
    parts = filename[len("DGM1_"):-len(".zip")].split("_")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None
