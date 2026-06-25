"""Cached tile-index adapter for Geobasis NRW 1 km GeoTIFF products."""

from __future__ import annotations

import json
import math
from pathlib import Path
import re
import time
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
FILENAME_PATTERN = re.compile(r"^(?P<prefix>\w+)_32_(?P<x>\d+)_(?P<y>\d+)_1_nw_(?P<version>\d+)\.tif$")


def locate_tiles(
    dataset: str,
    *,
    config: dict[str, Any],
    geometry: str,
    geometry_type: str,
    timeout: int,
) -> list[dict[str, str]]:
    candidates = tile_coordinates(_to_utm32(request_geometry(geometry, geometry_type)))
    if len(candidates) > MAX_TILES_PER_DATASET:
        raise ValueError(f"NRW selection resolves to {len(candidates)} 1 km tiles. Limit the area to {MAX_TILES_PER_DATASET} tiles per dataset.")
    index = load_index(dataset, config, timeout=timeout)
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
            "provider": "geobasis-nrw",
            "dataset": dataset,
            "tile_id": tile["tile_id"],
            "updated": tile["version"],
            "primary_url": tile["primary_url"],
            "source": "https://www.opengeodata.nrw.de/",
        }
        for tile in locate_tiles(dataset, config=config, geometry=geometry, geometry_type=geometry_type, timeout=timeout)
    ]


def load_index(dataset: str, config: dict[str, Any], *, timeout: int) -> dict[tuple[int, int], dict[str, str]]:
    path = index_path(dataset)
    if path.exists() and time.time() - path.stat().st_mtime < CACHE_MAX_AGE_SECONDS:
        return decode_index(json.loads(path.read_text(encoding="utf-8")))
    response = _get_catalog(config["catalog_url"], timeout)
    response.raise_for_status()
    index = parse_catalog(response.text, config["base_url"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(encode_index(index), separators=(",", ":")), encoding="utf-8")
    return index


def _get_catalog(url: str, timeout: int):
    try:
        return requests.get(url, timeout=timeout, verify=True)
    except requests.exceptions.SSLError:
        warnings.warn(
            f"SSL verification failed for {url}; retrying without certificate verification.",
            stacklevel=2,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", InsecureRequestWarning)
            return requests.get(url, timeout=timeout, verify=False)


def index_path(dataset: str) -> Path:
    return Path(load_settings().cache_root) / "provider_indexes" / f"geobasis_nrw_{dataset}.json"


def parse_catalog(content: str, base_url: str) -> dict[tuple[int, int], dict[str, str]]:
    index: dict[tuple[int, int], dict[str, str]] = {}
    for file_element in ElementTree.fromstring(content).iter("file"):
        name = file_element.attrib["name"]
        match = FILENAME_PATTERN.match(name)
        if not match:
            continue
        key = (int(match["x"]), int(match["y"]))
        tile = {"tile_id": name.removesuffix(".tif"), "primary_url": f"{base_url}{name}", "version": match["version"]}
        if key not in index or tile["version"] > index[key]["version"]:
            index[key] = tile
    return index


def encode_index(index: dict[tuple[int, int], dict[str, str]]) -> dict[str, dict[str, str]]:
    return {f"{east}:{north}": tile for (east, north), tile in index.items()}


def decode_index(index: dict[str, dict[str, str]]) -> dict[tuple[int, int], dict[str, str]]:
    return {tuple(int(value) for value in key.split(":", maxsplit=1)): tile for key, tile in index.items()}


def request_geometry(geometry: str, geometry_type: str):
    if geometry_type == "esriGeometryPoint":
        lon, lat = (float(value) for value in geometry.split(",", maxsplit=1))
        return Point(lon, lat)
    payload = json.loads(geometry)
    if geometry_type == "esriGeometryEnvelope":
        return box(payload["xmin"], payload["ymin"], payload["xmax"], payload["ymax"])
    if geometry_type == "esriGeometryPolygon":
        return Polygon(payload["rings"][0])
    raise ValueError(f"Unsupported NRW geometry type: {geometry_type}")


def _to_utm32(geometry):
    transformer = Transformer.from_crs(WGS84, ETRS89_UTM32, always_xy=True)
    return transform(transformer.transform, geometry)


def tile_coordinates(geometry) -> list[tuple[int, int]]:
    west, south, east, north = geometry.bounds
    return [
        (east_km, north_km)
        for east_km in range(math.floor(west / TILE_SIZE_M), math.floor(east / TILE_SIZE_M) + 1)
        for north_km in range(math.floor(south / TILE_SIZE_M), math.floor(north / TILE_SIZE_M) + 1)
        if geometry.intersects(box(east_km * TILE_SIZE_M, north_km * TILE_SIZE_M, (east_km + 1) * TILE_SIZE_M, (north_km + 1) * TILE_SIZE_M))
    ]
