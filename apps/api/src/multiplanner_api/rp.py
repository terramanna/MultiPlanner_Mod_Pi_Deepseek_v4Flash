"""Metalink4 tile-index adapter for LVermGeo Rheinland-Pfalz.

Supported datasets:
  dgm1   — bare-earth DTM, 1 km × 1 km GeoTIFF tiles
             index: https://geobasis-rlp.de/data/dgm1/current/meta4/dgm1_tif_07.meta4
  dop20  — RGB ortho, 2 km × 2 km JPEG2000 tiles
             index: https://geobasis-rlp.de/data/dop20rgb/current/meta4/dop20rgb_jp2_07.meta4

Both indexes are fetched once and cached for 24 h.
"""

from __future__ import annotations
from multiplanner_shared.geometry_io import request_geometry, to_utm32

import json
import math
import re
import time
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from shapely.geometry import Point, Polygon, box

from multiplanner_api.config import load_settings
from multiplanner_api.http_client import get_verified

MAX_TILES_PER_DATASET = 200
CACHE_MAX_AGE_SECONDS = 24 * 60 * 60
PROVIDER_ID = "lvermgeo-rp"
_META4_NS = "urn:ietf:params:xml:ns:metalink"

_DATASETS: dict[str, dict[str, Any]] = {
    "dgm1": {
        "meta4_url": "https://geobasis-rlp.de/data/dgm1/current/meta4/dgm1_tif_07.meta4",
        "cache_file": "lvermgeo_rp_dgm1.json",
        "filename_re": re.compile(
            r"^dgm1_32_(?P<x>\d+)_(?P<y>\d+)_1_rp_(?P<year>\d{4})\.tif$",
            re.IGNORECASE,
        ),
        "tile_size_m": 1000,
    },
    "dop20": {
        "meta4_url": "https://geobasis-rlp.de/data/dop20rgb/current/meta4/dop20rgb_jp2_07.meta4",
        "cache_file": "lvermgeo_rp_dop20.json",
        "filename_re": re.compile(
            r"^dop20rgb_32_(?P<x>\d+)_(?P<y>\d+)_2_rp_(?P<year>\d{4})\.jp2$",
            re.IGNORECASE,
        ),
        "tile_size_m": 2000,
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
    ds = _dataset_config(dataset)
    geom = to_utm32(request_geometry(geometry, geometry_type))
    candidates = _tile_coordinates(geom, ds["tile_size_m"])
    if len(candidates) > MAX_TILES_PER_DATASET:
        raise ValueError(
            f"Rheinland-Pfalz selection resolves to {len(candidates)} tiles. "
            f"Limit the area to {MAX_TILES_PER_DATASET} tiles per dataset."
        )
    index = _load_index(dataset, timeout=timeout)
    return [index[key] for key in candidates if key in index]


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
            "updated": tile["year"],
            "primary_url": tile["primary_url"],
            "source": "https://geobasis-rlp.de/",
        }
        for tile in locate_tiles(
            dataset,
            config=config,
            geometry=geometry,
            geometry_type=geometry_type,
            timeout=timeout,
        )
    ]


def _dataset_config(dataset: str) -> dict[str, Any]:
    if dataset not in _DATASETS:
        raise ValueError(f"Unknown Rheinland-Pfalz dataset: {dataset!r}")
    return _DATASETS[dataset]


def _load_index(dataset: str, *, timeout: int) -> dict[tuple[int, int], dict[str, str]]:
    ds = _dataset_config(dataset)
    path = Path(load_settings().cache_root) / "provider_indexes" / ds["cache_file"]
    if path.exists() and time.time() - path.stat().st_mtime < CACHE_MAX_AGE_SECONDS:
        return _decode_index(json.loads(path.read_text(encoding="utf-8")))
    xml_text = _fetch_meta4(ds["meta4_url"], timeout)
    index = _parse_meta4(xml_text, ds["filename_re"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_encode_index(index), separators=(",", ":")), encoding="utf-8")
    return index


def _fetch_meta4(url: str, timeout: int) -> str:
    response = get_verified(url, timeout=timeout)
    return response.text


def _parse_meta4(
    xml_text: str,
    filename_re: re.Pattern[str],
) -> dict[tuple[int, int], dict[str, str]]:
    index: dict[tuple[int, int], dict[str, str]] = {}
    root = ElementTree.fromstring(xml_text)
    for file_el in root.iter(f"{{{_META4_NS}}}file"):
        name = file_el.attrib.get("name", "")
        m = filename_re.match(name)
        if not m:
            continue
        key = (int(m["x"]), int(m["y"]))
        url_el = file_el.find(f"{{{_META4_NS}}}url")
        url = url_el.text.strip() if url_el is not None and url_el.text else ""
        if not url:
            continue
        year = m["year"]
        entry = {"tile_id": Path(name).stem, "primary_url": url, "year": year}
        if key not in index or year > index[key]["year"]:
            index[key] = entry
    return index


def _encode_index(index: dict[tuple[int, int], dict[str, str]]) -> dict[str, dict[str, str]]:
    return {f"{x}:{y}": tile for (x, y), tile in index.items()}


def _decode_index(raw: dict[str, dict[str, str]]) -> dict[tuple[int, int], dict[str, str]]:
    return {tuple(int(v) for v in k.split(":", 1)): tile for k, tile in raw.items()}


def _tile_coordinates(geometry, tile_size_m: int) -> list[tuple[int, int]]:
    """Return (x_km, y_km) km-origin pairs for tiles of *tile_size_m* intersecting *geometry*.

    geometry must already be in EPSG:25832. x_km and y_km are always in 1 km
    units (e.g. 344 means 344 000 m); the step between adjacent tiles is
    tile_size_m // 1000 km (1 for dgm1, 2 for dop20).
    """
    step = tile_size_m // 1000
    west, south, east, north = geometry.bounds
    x_lo = math.floor(west / tile_size_m) * step
    x_hi = math.floor(east / tile_size_m) * step
    y_lo = math.floor(south / tile_size_m) * step
    y_hi = math.floor(north / tile_size_m) * step
    return [
        (x_km, y_km)
        for x_km in range(x_lo, x_hi + step, step)
        for y_km in range(y_lo, y_hi + step, step)
        if geometry.intersects(
            box(x_km * 1000, y_km * 1000, x_km * 1000 + tile_size_m, y_km * 1000 + tile_size_m)
        )
    ]
