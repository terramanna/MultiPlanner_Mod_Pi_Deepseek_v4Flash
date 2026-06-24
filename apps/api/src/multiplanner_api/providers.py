from __future__ import annotations

import json
from typing import Any

import requests
from pyproj import Transformer
from shapely.geometry import LineString
from shapely.ops import transform

SERVICE_PROVIDERS = {
    "lgln-ni": {
        "label": "LGLN Lower Saxony",
        "datasets": {
            "dgm1": {
                "query_url": "https://services-eu1.arcgis.com/4v3xxN52w88W065F/arcgis/rest/services/lgln_opengeodata_dgm1/FeatureServer/0/query",
                "primary_url_field": "dgm1",
                "url_fields": ("dgm1", "metadata"),
            },
            "dom1": {
                "query_url": "https://services-eu1.arcgis.com/4v3xxN52w88W065F/arcgis/rest/services/lgln_opengeodata_dom1/FeatureServer/0/query",
                "primary_url_field": "dom1",
                "url_fields": ("dom1", "metadata"),
            },
            "dop20": {
                "query_url": "https://services-eu1.arcgis.com/4v3xxN52w88W065F/arcgis/rest/services/DOP20_Index/FeatureServer/0/query",
                "primary_url_field": "rgb",
                "url_fields": ("rgb", "rgb_metadata", "rgbi", "rgbi_metadata"),
            },
        },
    }
}

WGS84 = "EPSG:4326"
WEB_MERCATOR = "EPSG:3857"


def list_provider_names() -> list[str]:
    return sorted(SERVICE_PROVIDERS.keys())


def provider_dataset_names(provider: str) -> tuple[str, ...]:
    return tuple(SERVICE_PROVIDERS[provider]["datasets"].keys())


def _dataset_config(provider: str, dataset: str) -> dict[str, Any]:
    return SERVICE_PROVIDERS[provider]["datasets"][dataset]


def _query_params(*, geometry: str, geometry_type: str, out_sr: str = "4326") -> dict[str, Any]:
    return {
        "f": "json",
        "geometry": geometry,
        "geometryType": geometry_type,
        "inSR": "4326",
        "outSR": out_sr,
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "false",
    }


def _wgs84_to_web_mercator(geom):
    transformer = Transformer.from_crs(WGS84, WEB_MERCATOR, always_xy=True)
    return transform(transformer.transform, geom)


def _web_mercator_to_wgs84(geom):
    transformer = Transformer.from_crs(WEB_MERCATOR, WGS84, always_xy=True)
    return transform(transformer.transform, geom)


def corridor_geometry(
    from_lon: float,
    from_lat: float,
    to_lon: float,
    to_lat: float,
    buffer_m: float,
) -> tuple[str, str]:
    line = LineString([(from_lon, from_lat), (to_lon, to_lat)])
    line_3857 = _wgs84_to_web_mercator(line)
    corridor_3857 = line_3857.buffer(buffer_m)
    corridor_wgs84 = _web_mercator_to_wgs84(corridor_3857)
    coords = [[[float(x), float(y)] for x, y in corridor_wgs84.exterior.coords]]
    return json.dumps({"rings": coords, "spatialReference": {"wkid": 4326}}), "esriGeometryPolygon"


def point_geometry(lon: float, lat: float) -> tuple[str, str]:
    return f"{lon},{lat}", "esriGeometryPoint"


def bbox_geometry(west: float, south: float, east: float, north: float) -> tuple[str, str]:
    geom = {
        "xmin": west,
        "ymin": south,
        "xmax": east,
        "ymax": north,
        "spatialReference": {"wkid": 4326},
    }
    return json.dumps(geom), "esriGeometryEnvelope"


def locate_remote_tiles(
    provider: str,
    dataset: str,
    *,
    geometry: str,
    geometry_type: str,
    timeout: int = 60,
) -> list[dict[str, Any]]:
    config = _dataset_config(provider, dataset)
    response = requests.get(
        config["query_url"],
        params=_query_params(geometry=geometry, geometry_type=geometry_type),
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    features = payload.get("features", [])
    return [feature.get("attributes", {}) for feature in features]


def summarize_remote_tiles(
    provider: str,
    dataset: str,
    *,
    geometry: str,
    geometry_type: str,
    timeout: int = 60,
) -> list[dict[str, Any]]:
    config = _dataset_config(provider, dataset)
    summaries: list[dict[str, Any]] = []
    for attrs in locate_remote_tiles(
        provider,
        dataset,
        geometry=geometry,
        geometry_type=geometry_type,
        timeout=timeout,
    ):
        summary = {
            "provider": provider,
            "dataset": dataset,
            "tile_id": attrs.get("tile_id"),
            "updated": attrs.get("Aktualitaet"),
            "primary_url": attrs.get(config["primary_url_field"]),
        }
        for field in config["url_fields"]:
            if field in attrs:
                summary[field] = attrs[field]
        summaries.append(summary)
    return summaries
