"""Schleswig-Holstein adapter via GeoJSON tile indexes (GeoData portal Massendownload).

Index URLs follow the pattern:
  https://geodaten.schleswig-holstein.de/gaialight-sh/_apps/dladownload/
  single.php?file={GEOJSON_FILE}&id=4

Dataset       GeoJSON file                         ID field   URL field
dgm1          DGM1_SH__Massendownload.geojson      kachel     link_data
dop20         DOP20_SH__Massendownload.geojson     kachel     link_data
lod2          LOD2_SH_Massendownload.geojson       id         data_link

Tile size: 1 km x 1 km; CRS: EPSG:25832.
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

_BASE_URL = "https://geodaten.schleswig-holstein.de/gaialight-sh/_apps/dladownload/"

_DATASET_CONFIG: dict[str, dict[str, str]] = {
    "dgm1": {
        "geojson_file": "DGM1_SH__Massendownload.geojson",
        "id_field": "kachel",
        "url_field": "link_data",
    },
    "dop20": {
        "geojson_file": "DOP20_SH__Massendownload.geojson",
        "id_field": "kachel",
        "url_field": "link_data",
    },
    "lod2": {
        "geojson_file": "LOD2_SH_Massendownload.geojson",
        "id_field": "id",
        "url_field": "data_link",
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
    cfg = _DATASET_CONFIG[dataset]
    geom_utm32 = _to_utm32(request_geometry(geometry, geometry_type))
    tiles = _load_index(dataset, timeout=timeout)
    matching = [t for t in tiles if _tile_shape(t).intersects(geom_utm32)]
    if len(matching) > MAX_TILES_PER_DATASET:
        raise ValueError(
            f"Schleswig-Holstein selection resolves to {len(matching)} 1 km tiles. "
            f"Limit the area to {MAX_TILES_PER_DATASET} tiles per dataset."
        )
    id_field = cfg["id_field"]
    url_field = cfg["url_field"]
    return [
        {"tile_id": f"sh_{dataset}_{t[id_field]}", "primary_url": t[url_field], "datum": t["datum"]}
        for t in matching
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


def _load_index(dataset: str, *, timeout: int) -> list[dict]:
    path = _cache_path(dataset)
    if path.exists() and time.time() - path.stat().st_mtime < CACHE_MAX_AGE_SECONDS:
        return json.loads(path.read_text(encoding="utf-8"))
    cfg = _DATASET_CONFIG[dataset]
    response = requests.get(_geojson_url(dataset), timeout=timeout)
    response.raise_for_status()
    entries = _parse_geojson(
        response.json(),
        id_field=cfg["id_field"],
        url_field=cfg["url_field"],
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, separators=(",", ":")), encoding="utf-8")
    return entries


def _cache_path(dataset: str) -> Path:
    return Path(load_settings().cache_root) / "provider_indexes" / f"geodaten_sh_{dataset}.json"


def _geojson_url(dataset: str) -> str:
    return f"{_BASE_URL}single.php?file={_DATASET_CONFIG[dataset]['geojson_file']}&id=4"


def _parse_geojson(
    geojson: dict,
    *,
    id_field: str = "kachel",
    url_field: str = "link_data",
) -> list[dict]:
    entries = []
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        geom = feature.get("geometry")
        tile_id = props.get(id_field)
        url = props.get(url_field)
        if not geom or not tile_id or not url:
            continue
        bbox = list(shape(geom).bounds)
        entries.append({
            id_field: str(tile_id),
            url_field: str(url),
            "datum": str(props.get("datum", "")),
            "bbox": bbox,
        })
    return entries


def _tile_shape(tile: dict):
    xmin, ymin, xmax, ymax = tile["bbox"]
    return box(xmin, ymin, xmax, ymax)
