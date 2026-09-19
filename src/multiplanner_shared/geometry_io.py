"""Shared geometry helpers for provider adapters.

Providers parse incoming geometry and project it into their local UTM zone.
The geometry-request parsing and UTM transforms are identical across providers;
only the tile-index matching differs.
"""

from __future__ import annotations

import json
import math

from pyproj import Transformer
from shapely.geometry import Point, Polygon, box
from shapely.ops import transform

# Common CRS identifiers
WGS84 = "EPSG:4326"
ETRS89_UTM32 = "EPSG:25832"
ETRS89_UTM33 = "EPSG:25833"

_T_UTM32 = Transformer.from_crs(WGS84, ETRS89_UTM32, always_xy=True)
_T_UTM33 = Transformer.from_crs(WGS84, ETRS89_UTM33, always_xy=True)


def request_geometry(geometry: str, geometry_type: str):
    """Parse incoming geometry into a shapely geometry object.

    Accepts the same esriGeometry* strings that provider endpoints return.
    """
    if geometry_type == "esriGeometryPoint":
        lon, lat = (float(v) for v in geometry.split(",", maxsplit=1))
        return Point(lon, lat)
    payload = json.loads(geometry)
    if geometry_type == "esriGeometryEnvelope":
        return box(payload["xmin"], payload["ymin"], payload["xmax"], payload["ymax"])
    if geometry_type == "esriGeometryPolygon":
        return Polygon(payload["rings"][0])
    raise ValueError(f"Unsupported geometry type: {geometry_type}")


def to_utm32(geometry):
    return transform(_T_UTM32.transform, geometry)


def to_utm33(geometry):
    return transform(_T_UTM33.transform, geometry)


def tile_cells_for_geometry(geometry, tile_size_m: int = 1000) -> list[tuple[int, int]]:
    """Return (x_m, y_m) SW-corner metre origins for cells intersecting *geometry*.

    geometry must already be in the target UTM CRS.
    """
    west, south, east, north = geometry.bounds
    x_start = math.floor(west / tile_size_m) * tile_size_m
    x_end = math.floor(east / tile_size_m) * tile_size_m
    y_start = math.floor(south / tile_size_m) * tile_size_m
    y_end = math.floor(north / tile_size_m) * tile_size_m
    return [
        (x, y)
        for x in range(x_start, x_end + tile_size_m, tile_size_m)
        for y in range(y_start, y_end + tile_size_m, tile_size_m)
        if geometry.intersects(box(x, y, x + tile_size_m, y + tile_size_m))
    ]