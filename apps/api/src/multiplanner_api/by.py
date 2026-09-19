"""Bavaria raster adapter via the official poly2metalink polygon service."""

from __future__ import annotations
from multiplanner_shared.geometry_io import request_geometry, to_utm32

import json
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from shapely.geometry import Point, Polygon, box

from multiplanner_api.http_client import post_with_ssl_fallback

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
    geom_32 = to_utm32(request_geometry(geometry, geometry_type))
    response = post_with_ssl_fallback(
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
