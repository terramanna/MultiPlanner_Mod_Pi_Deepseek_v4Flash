"""Metalink4 tile-index adapter for LVermGeo Rheinland-Pfalz DGM1.

Meta4 index:  https://geobasis-rlp.de/data/dgm1/current/meta4/dgm1_tif_07.meta4
Tile pattern: dgm1_32_{X}_{Y}_1_rp_{YYYY}.tif
              X = easting km, Y = northing km (EPSG:25832)
Tile size:    1 km × 1 km
~900+ tiles covering RP; fetched once and cached for 24 h.
"""

from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from typing import Any
import warnings
from xml.etree import ElementTree

import requests
from pyproj import Transformer
from shapely.geometry import Point, Polygon, box
from shapely.ops import transform
from urllib3.exceptions import InsecureRequestWarning

from multiplanner_api.config import load_settings

WGS84 = "EPSG:4326"
ETRS89_UTM32 = "EPSG:25832"
TILE_SIZE_M = 1000
MAX_TILES_PER_DATASET = 200
CACHE_MAX_AGE_SECONDS = 24 * 60 * 60
PROVIDER_ID = "lvermgeo-rp"

META4_URL = "https://geobasis-rlp.de/data/dgm1/current/meta4/dgm1_tif_07.meta4"
_FILENAME_RE = re.compile(
    r"^dgm1_32_(?P<x>\d+)_(?P<y>\d+)_1_rp_(?P<year>\d{4})\.tif$",
    re.IGNORECASE,
)
_META4_NS = "urn:ietf:params:xml:ns:metalink"


def locate_tiles(
    dataset: str,
    *,
    config: dict[str, Any],
    geometry: str,
    geometry_type: str,
    timeout: int,
) -> list[dict[str, str]]:
    candidates = _tile_coordinates(_to_utm32(request_geometry(geometry, geometry_type)))
    if len(candidates) > MAX_TILES_PER_DATASET:
        raise ValueError(
            f"Rheinland-Pfalz selection resolves to {len(candidates)} 1 km tiles. "
            f"Limit the area to {MAX_TILES_PER_DATASET} tiles per dataset."
        )
    index = _load_index(timeout=timeout)
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


def _load_index(*, timeout: int) -> dict[tuple[int, int], dict[str, str]]:
    path = Path(load_settings().cache_root) / "provider_indexes" / "lvermgeo_rp_dgm1.json"
    if path.exists() and time.time() - path.stat().st_mtime < CACHE_MAX_AGE_SECONDS:
        return _decode_index(json.loads(path.read_text(encoding="utf-8")))
    xml_text = _fetch_meta4(META4_URL, timeout)
    index = _parse_meta4(xml_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_encode_index(index), separators=(",", ":")), encoding="utf-8")
    return index


def _fetch_meta4(url: str, timeout: int) -> str:
    try:
        return _http_get(url, timeout, verify=True)
    except requests.exceptions.SSLError:
        warnings.warn(
            f"SSL verification failed for {url}; retrying without certificate verification.",
            stacklevel=2,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", InsecureRequestWarning)
            return _http_get(url, timeout, verify=False)


def _http_get(url: str, timeout: int, *, verify: bool) -> str:
    with requests.Session() as session:
        session.trust_env = False
        r = session.get(url, timeout=timeout, verify=verify)
        r.raise_for_status()
        return r.text


def _parse_meta4(xml_text: str) -> dict[tuple[int, int], dict[str, str]]:
    index: dict[tuple[int, int], dict[str, str]] = {}
    root = ElementTree.fromstring(xml_text)
    for file_el in root.iter(f"{{{_META4_NS}}}file"):
        name = file_el.attrib.get("name", "")
        m = _FILENAME_RE.match(name)
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


def request_geometry(geometry: str, geometry_type: str):
    if geometry_type == "esriGeometryPoint":
        lon, lat = (float(v) for v in geometry.split(",", maxsplit=1))
        return Point(lon, lat)
    payload = json.loads(geometry)
    if geometry_type == "esriGeometryEnvelope":
        return box(payload["xmin"], payload["ymin"], payload["xmax"], payload["ymax"])
    if geometry_type == "esriGeometryPolygon":
        return Polygon(payload["rings"][0])
    raise ValueError(f"Unsupported Rheinland-Pfalz geometry type: {geometry_type}")


def _to_utm32(geometry):
    transformer = Transformer.from_crs(WGS84, ETRS89_UTM32, always_xy=True)
    return transform(transformer.transform, geometry)


def _tile_coordinates(geometry) -> list[tuple[int, int]]:
    """Return (x_km, y_km) km-origin pairs for 1 km cells intersecting *geometry*.

    geometry must already be in EPSG:25832.
    """
    west, south, east, north = geometry.bounds
    return [
        (x_km, y_km)
        for x_km in range(math.floor(west / TILE_SIZE_M), math.floor(east / TILE_SIZE_M) + 1)
        for y_km in range(math.floor(south / TILE_SIZE_M), math.floor(north / TILE_SIZE_M) + 1)
        if geometry.intersects(box(x_km * TILE_SIZE_M, y_km * TILE_SIZE_M,
                                   (x_km + 1) * TILE_SIZE_M, (y_km + 1) * TILE_SIZE_M))
    ]
