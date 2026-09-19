"""Berlin DGM1/DOM1/bDOM adapter via INSPIRE ATOM feeds (gdi.berlin.de).

Dataset     ATOM sub-feed                            Filename pattern      Tiles
dgm1        /data/dgm1/atom/0.atom                   DGM1_{X}_{Y}.zip      618
dom1        /data/dom/atom/0.atom                    DOM1_{X}_{Y}.zip      227
bdom        /data/bdom/atom/0.atom                   {X}_{Y}.zip           276

All datasets: 2 km × 2 km tiles, EPSG:25833 (ETRS89 / UTM Zone 33N),
ASCII XYZ (CSV) format, Datenlizenz Deutschland Zero v2.0.

Coordinates in filenames are in km (integer):
  DGM1_368_5808.zip → x=[368000, 370000], y=[5808000, 5810000].
"""

from __future__ import annotations
from multiplanner_api.geometry_io import request_geometry

import json
import math
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from pyproj import Transformer
from shapely.geometry import Point, Polygon, box
from shapely.ops import transform

from multiplanner_api.config import load_settings
from multiplanner_api.http_client import get_with_ssl_fallback

WGS84 = "EPSG:4326"
ETRS89_UTM33 = "EPSG:25833"
TILE_SIZE_M = 2000
MAX_TILES_PER_DATASET = 200
PROVIDER_ID = "gdi-be"
CACHE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60

_ATOM_NS = "http://www.w3.org/2005/Atom"
_ATOM_BASE = "https://gdi.berlin.de/data"

_DATASET_CONFIG: dict[str, dict[str, str]] = {
    "dgm1": {
        "atom_url": f"{_ATOM_BASE}/dgm1/atom/0.atom",
        "filename_prefix": "DGM1_",
        "cache_file": "gdi_be_dgm1.json",
    },
    "dom1": {
        "atom_url": f"{_ATOM_BASE}/dom/atom/0.atom",
        "filename_prefix": "DOM1_",
        "cache_file": "gdi_be_dom1.json",
    },
    "bdom": {
        "atom_url": f"{_ATOM_BASE}/bdom/atom/0.atom",
        "filename_prefix": "",
        "cache_file": "gdi_be_bdom.json",
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
    geom_33 = _to_utm33(request_geometry(geometry, geometry_type))
    index = _load_index(dataset, ds_cfg, timeout=timeout)
    matching = _intersecting_tiles(dataset, geom_33, index)
    if len(matching) > MAX_TILES_PER_DATASET:
        raise ValueError(
            f"Berlin {dataset} selection resolves to {len(matching)} 2 km tiles. "
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




def _dataset_config(dataset: str) -> dict[str, str]:
    if dataset not in _DATASET_CONFIG:
        raise ValueError(f"Unknown Berlin dataset: {dataset!r}. Valid: {list(_DATASET_CONFIG)}")
    return _DATASET_CONFIG[dataset]


def _to_utm33(geometry):
    transformer = Transformer.from_crs(WGS84, ETRS89_UTM33, always_xy=True)
    return transform(transformer.transform, geometry)


def _intersecting_tiles(
    dataset: str, geom_33, index: dict[tuple[int, int], str]
) -> list[dict[str, str]]:
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
                tile_id = f"be_{dataset}_{key[0]}_{key[1]}"
                results.append({"tile_id": tile_id, "primary_url": url})
    return results


def _load_index(
    dataset: str, ds_cfg: dict[str, str], *, timeout: int
) -> dict[tuple[int, int], str]:
    path = _cache_path(ds_cfg)
    if path.exists() and time.time() - path.stat().st_mtime < CACHE_MAX_AGE_SECONDS:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {(e["x_km"], e["y_km"]): e["url"] for e in raw}
    response = get_with_ssl_fallback(ds_cfg["atom_url"], timeout=timeout)
    response.raise_for_status()
    entries = _parse_atom(response.text, ds_cfg["filename_prefix"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, separators=(",", ":")), encoding="utf-8")
    return {(e["x_km"], e["y_km"]): e["url"] for e in entries}


def _cache_path(ds_cfg: dict[str, str]) -> Path:
    return Path(load_settings().cache_root) / "provider_indexes" / ds_cfg["cache_file"]


def _parse_atom(xml_text: str, filename_prefix: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    entries = []
    for link in root.iter(f"{{{_ATOM_NS}}}link"):
        if link.get("rel") != "section":
            continue
        href = link.get("href", "")
        coords = _parse_coords(href, filename_prefix)
        if coords:
            x_km, y_km = coords
            entries.append({"x_km": x_km, "y_km": y_km, "url": href})
    return entries


def _parse_coords(href: str, filename_prefix: str) -> tuple[int, int] | None:
    """Extract (x_km, y_km) from a tile URL given the dataset filename prefix."""
    filename = href.rsplit("/", 1)[-1]
    if not filename.endswith(".zip"):
        return None
    if filename_prefix and not filename.startswith(filename_prefix):
        return None
    stem = filename[len(filename_prefix):-len(".zip")]
    parts = stem.split("_")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None
