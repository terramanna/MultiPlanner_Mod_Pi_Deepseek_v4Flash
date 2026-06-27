"""Grid-ZIP adapter for LGL Baden-Wuerttemberg DGM1.

Official product catalog:
  https://opengeodata.lgl-bw.de/assets/config/local/odp-products.json

Published contract:
  - layerLID: zwei_km_gitter
  - productConnectorKey: DGM
  - selectionCapacity: 10 in the portal UI
  - tile download pattern: /data/dgm/dgm1_32_{x_km}_{y_km}_2_bw.zip

CRS:       EPSG:25832 (ETRS89 / UTM Zone 32N)
Tile size: 2 km x 2 km
Format:    ZIP containing four 1 km ASCII XYZ files
"""

from __future__ import annotations

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
SOURCE_URL = "https://opengeodata.lgl-bw.de/"
BASE_URL = "https://opengeodata.lgl-bw.de/data/dgm/"


def locate_tiles(
    dataset: str,
    *,
    config: dict[str, Any],
    geometry: str,
    geometry_type: str,
    timeout: int,
) -> list[dict[str, str]]:
    geom_32 = _to_utm32(request_geometry(geometry, geometry_type))
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
            "source": SOURCE_URL,
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
        lon, lat = (float(value) for value in geometry.split(",", maxsplit=1))
        return Point(lon, lat)
    payload = json.loads(geometry)
    if geometry_type == "esriGeometryEnvelope":
        return box(payload["xmin"], payload["ymin"], payload["xmax"], payload["ymax"])
    if geometry_type == "esriGeometryPolygon":
        return Polygon(payload["rings"][0])
    raise ValueError(f"Unsupported Baden-Wuerttemberg geometry type: {geometry_type}")


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
    filename = f"{dataset}_32_{x_km}_{y_km}_2_bw.zip"
    return {"tile_id": tile_id, "primary_url": f"{BASE_URL}{filename}"}
