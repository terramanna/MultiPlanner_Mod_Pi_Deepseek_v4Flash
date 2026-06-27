"""Bavaria raster adapter via the official poly2metalink polygon service."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import requests
from pyproj import Transformer
from shapely.geometry import Point, Polygon, box
from shapely.ops import transform

WGS84 = "EPSG:4326"
ETRS89_UTM32 = "EPSG:25832"
PROVIDER_ID = "ldbv-by"
METALINK_NS = {"m": "urn:ietf:params:xml:ns:metalink"}


def locate_tiles(
    dataset: str,
    *,
    config: dict[str, Any],
    geometry: str,
    geometry_type: str,
    timeout: int,
) -> list[dict[str, str]]:
    geom_32 = _to_utm32(request_geometry(geometry, geometry_type))
    response = requests.post(
        config["metalink_url"],
        data=_request_body(geom_32),
        headers={"Content-Type": "text/plain"},
        timeout=timeout,
    )
    try:
        response.raise_for_status()
    except Exception as exc:
        message = getattr(getattr(exc, "response", None), "text", "") or str(exc)
        raise ValueError(f"Bayern selection rejected: {message}") from exc
    return _metalink_urls(response.text, dataset)


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
            "source": config["source_url"],
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
    raise ValueError(f"Unsupported Bayern geometry type: {geometry_type}")


def _to_utm32(geometry):
    transformer = Transformer.from_crs(WGS84, ETRS89_UTM32, always_xy=True)
    return transform(transformer.transform, geometry)


def _request_body(geometry) -> str:
    return f"SRID=25832;{geometry.wkt}"


def _metalink_urls(payload: str, dataset: str) -> list[dict[str, str]]:
    root = ElementTree.fromstring(payload)
    records: list[dict[str, str]] = []
    for file_element in root.findall("m:file", METALINK_NS):
        name = file_element.attrib.get("name", "")
        url_element = file_element.find("m:url", METALINK_NS)
        if not name or url_element is None or not url_element.text:
            continue
        stem = Path(name).stem
        records.append(
            {
                "tile_id": f"by_{dataset}_{stem}",
                "primary_url": url_element.text.strip(),
            }
        )
    return records
