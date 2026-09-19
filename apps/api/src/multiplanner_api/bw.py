"""Grid-ZIP adapter for tiled LGL Baden-Wuerttemberg products.

Official product catalog:
  https://opengeodata.lgl-bw.de/assets/config/local/odp-products.json

Published contracts used here:
  - DGM1: /data/dgm/dgm1_32_{x_km}_{y_km}_2_bw.zip
  - DOM1: /data/dom1/dom1_32_{x_km}_{y_km}_2_bw.zip
  - DOP20 RGB: /data/dop20/dop20rgb_32_{x_km}_{y_km}_2_bw.zip
  - LoD2: /data/lod2/LoD2_32_{x_km}_{y_km}_2_bw.zip

CRS:       EPSG:25832 (ETRS89 / UTM Zone 32N)
Tile size: 2 km x 2 km
Format:    ZIP bundles; internal source type depends on dataset
"""

from __future__ import annotations
from multiplanner_shared.geometry_io import request_geometry

import json
import math
from typing import Any

from pyproj import Transformer
from shapely.geometry import Point, Polygon, box
from shapely.ops import transform

WGS84 = "EPSG:4326"
ETRS89_UTM32 = "EPSG:25832"
TILE_SIZE_M = 1000
MAX_TILES_PER_DATASET = 200
PROVIDER_ID = "lgl-bw"
_BW_BBOX = (7.51, 47.53, 10.49, 49.79)  # W, S, E, N (WGS84)
DEFAULT_SOURCE_URL = "https://opengeodata.lgl-bw.de/"


def locate_tiles(
    dataset: str,
    *,
    config: dict[str, Any],
    geometry: str,
    geometry_type: str,
    timeout: int,
) -> list[dict[str, str]]:
    geom_wgs84 = request_geometry(geometry, geometry_type)
    if not geom_wgs84.intersects(box(*_BW_BBOX)):
        return []
    geom_32 = _to_utm32(geom_wgs84)
    cells = _tile_cells(geom_32)
    if len(cells) > MAX_TILES_PER_DATASET:
        raise ValueError(
            f"Baden-Wuerttemberg selection resolves to {len(cells)} 2 km tiles. "
            f"Limit the area to {MAX_TILES_PER_DATASET} tiles per dataset."
        )
    return [_tile_record(dataset, x_km, y_km) for x_km, y_km in cells]


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
            "source": config.get("source_url", DEFAULT_SOURCE_URL),
        }
        for tile in locate_tiles(
            dataset,
            config=config,
            geometry=geometry,
            geometry_type=geometry_type,
            timeout=timeout,
        )
    ]




def _to_utm32(geometry):
    transformer = Transformer.from_crs(WGS84, ETRS89_UTM32, always_xy=True)
    return transform(transformer.transform, geometry)


def _tile_cells(geometry) -> list[tuple[int, int]]:
    west, south, east, north = geometry.bounds
    x_start = math.floor(west / TILE_SIZE_M)
    x_end = math.floor(east / TILE_SIZE_M)
    y_start = math.floor(south / TILE_SIZE_M)
    y_end = math.floor(north / TILE_SIZE_M)
    packages = {
        (_package_x(x_km), _package_y(y_km))
        for x_km in range(x_start, x_end + 1)
        for y_km in range(y_start, y_end + 1)
        if geometry.intersects(box(x_km * TILE_SIZE_M, y_km * TILE_SIZE_M, (x_km + 1) * TILE_SIZE_M, (y_km + 1) * TILE_SIZE_M))
    }
    return sorted(packages)


def _package_x(x_km: int) -> int:
    return x_km if x_km % 2 == 1 else x_km - 1


def _package_y(y_km: int) -> int:
    return y_km if y_km % 2 == 0 else y_km - 1


def _tile_record(dataset: str, x_km: int, y_km: int) -> dict[str, str]:
    tile_id = f"bw_{dataset}_{x_km}_{y_km}"
    filename, base_url = _dataset_location(dataset)
    return {"tile_id": tile_id, "primary_url": f"{base_url}{filename.format(x_km=x_km, y_km=y_km)}"}


def _dataset_location(dataset: str) -> tuple[str, str]:
    locations = {
        "dgm1": ("dgm1_32_{x_km}_{y_km}_2_bw.zip", "https://opengeodata.lgl-bw.de/data/dgm/"),
        "dom1": ("dom1_32_{x_km}_{y_km}_2_bw.zip", "https://opengeodata.lgl-bw.de/data/dom1/"),
        "dop20": ("dop20rgb_32_{x_km}_{y_km}_2_bw.zip", "https://opengeodata.lgl-bw.de/data/dop20/"),
        "bdom": ("LoD2_32_{x_km}_{y_km}_2_bw.zip", "https://opengeodata.lgl-bw.de/data/lod2/"),
    }
    try:
        return locations[dataset]
    except KeyError as exc:
        raise ValueError(f"Unsupported Baden-Wuerttemberg dataset: {dataset}") from exc
