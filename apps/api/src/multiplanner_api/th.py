"""Thüringen DGM/DOM/LOD2 adapter via INSPIRE ATOM feeds (TLBG GDI-Th).

Dataset  Feed URL (dataset sub-feed)                               Tile   CRS
dgm      /dienste/atom_th_hoehendaten_dgm?type=dataset&id=14418…   1km    EPSG:25832
dom      /dienste/atom_th_hoehendaten_dom?type=dataset&id=3b5d8…   1km    EPSG:25832
lod2     /dienste/atom_th_gebaeude?type=dataset&id=97d152b8…       2km    EPSG:25832

DOP (orthophoto) is not implemented — no ATOM feed exists; the TLBG only
provides DOP via an interactive web download client limited to 12 tiles per
session.

Each ATOM <link rel="section"> carries a WGS84 bbox attribute
(south west north east) used directly for intersection; no UTM reprojection
is needed for tile selection.

License: Datenlizenz Deutschland – Namensnennung – Version 2.0 (dl-de/by-2-0)
"""

from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import requests
from shapely.geometry import Point, Polygon, box

from multiplanner_api.config import load_settings

PROVIDER_ID = "tlbg-th"
MAX_TILES_PER_DATASET = 200
CACHE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
_ATOM_NS = "http://www.w3.org/2005/Atom"
_BASE = "https://geoportal.geoportal-th.de"

_DATASET_CONFIG: dict[str, dict[str, str]] = {
    "dgm": {
        "atom_url": (
            f"{_BASE}/dienste/atom_th_hoehendaten_dgm"
            "?type=dataset&id=14418d25-fcd7-4a3f-99a9-e3059a2772af"
        ),
        "href_prefix": "dgm2_",
        "cache_file": "tlbg_th_dgm.json",
    },
    "dom": {
        "atom_url": (
            f"{_BASE}/dienste/atom_th_hoehendaten_dom"
            "?type=dataset&id=3b5d8d9c-775d-4617-8dfe-71480d6472a6"
        ),
        "href_prefix": "dom2_",
        "cache_file": "tlbg_th_dom.json",
    },
    "lod2": {
        "atom_url": (
            f"{_BASE}/dienste/atom_th_gebaeude"
            "?type=dataset&id=97d152b8-9e00-49f3-9ae4-8bbb30873562"
        ),
        "href_prefix": "LoD2_32_",
        "cache_file": "tlbg_th_lod2.json",
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
    ds_cfg = _dataset_config(dataset)
    geom = request_geometry(geometry, geometry_type)
    index = _load_index(ds_cfg, timeout=timeout)
    matching = _intersecting_tiles(dataset, geom, index)
    if len(matching) > MAX_TILES_PER_DATASET:
        raise ValueError(
            f"Thüringen {dataset} selection resolves to {len(matching)} tiles. "
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
    raise ValueError(f"Unsupported Thüringen geometry type: {geometry_type}")


def _dataset_config(dataset: str) -> dict[str, str]:
    if dataset not in _DATASET_CONFIG:
        raise ValueError(
            f"Unknown Thüringen dataset: {dataset!r}. Valid: {list(_DATASET_CONFIG)}"
        )
    return _DATASET_CONFIG[dataset]


def _intersecting_tiles(
    dataset: str,
    geom,
    index: list[dict],
) -> list[dict[str, str]]:
    results = []
    for entry in index:
        tile_box = box(entry["west"], entry["south"], entry["east"], entry["north"])
        if geom.intersects(tile_box):
            tile_id = f"th_{dataset}_{entry['x_km']}_{entry['y_km']}"
            results.append({"tile_id": tile_id, "primary_url": entry["url"]})
    return results


def _load_index(ds_cfg: dict[str, str], *, timeout: int) -> list[dict]:
    path = _cache_path(ds_cfg)
    if path.exists() and time.time() - path.stat().st_mtime < CACHE_MAX_AGE_SECONDS:
        return json.loads(path.read_text(encoding="utf-8"))
    response = requests.get(ds_cfg["atom_url"], timeout=timeout)
    response.raise_for_status()
    entries = _parse_atom(response.text, ds_cfg["href_prefix"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, separators=(",", ":")), encoding="utf-8")
    return entries


def _cache_path(ds_cfg: dict[str, str]) -> Path:
    return Path(load_settings().cache_root) / "provider_indexes" / ds_cfg["cache_file"]


def _parse_atom(xml_text: str, href_prefix: str) -> list[dict]:
    """Parse an INSPIRE ATOM dataset feed, returning one entry per tile.

    For feeds that contain multiple vintages of the same tile (e.g., DGM
    2010-2013 and 2020-2025) the last occurrence wins — feeds are ordered
    old-to-new so the most recent URL is kept.
    """
    root = ET.fromstring(xml_text)
    seen: dict[tuple[int, int], dict] = {}
    for link in root.iter(f"{{{_ATOM_NS}}}link"):
        if link.get("rel") != "section":
            continue
        href = link.get("href", "")
        coords = _parse_coords(href, href_prefix)
        if coords is None:
            continue
        bbox = _parse_bbox(link.get("bbox", ""))
        if bbox is None:
            continue
        x_km, y_km = coords
        south, west, north, east = bbox
        seen[(x_km, y_km)] = {
            "x_km": x_km,
            "y_km": y_km,
            "south": south,
            "west": west,
            "north": north,
            "east": east,
            "url": href,
        }
    return list(seen.values())


def _parse_coords(href: str, href_prefix: str) -> tuple[int, int] | None:
    """Extract (x_km, y_km) from a tile URL given the dataset filename prefix."""
    filename = href.rsplit("/", 1)[-1]
    if not filename.endswith(".zip"):
        return None
    if not filename.startswith(href_prefix):
        return None
    stem = filename[len(href_prefix) : -4]  # strip prefix and ".zip"
    parts = stem.split("_")
    if len(parts) < 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def _parse_bbox(bbox_str: str) -> tuple[float, float, float, float] | None:
    """Parse OGC 'south west north east' bbox string from an ATOM link attribute."""
    try:
        parts = bbox_str.split()
        if len(parts) != 4:
            return None
        south, west, north, east = (float(p) for p in parts)
        return south, west, north, east
    except (ValueError, AttributeError):
        return None
