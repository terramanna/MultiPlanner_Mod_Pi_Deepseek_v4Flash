from __future__ import annotations

import json
from typing import Any

import requests
from pyproj import Transformer
from shapely.geometry import LineString
from shapely.ops import transform

from multiplanner_api.bb import locate_tiles as locate_bb_tiles
from multiplanner_api.bb import summarize_tiles as summarize_bb_tiles
from multiplanner_api.bw import locate_tiles as locate_bw_tiles
from multiplanner_api.bw import summarize_tiles as summarize_bw_tiles
from multiplanner_api.by import locate_tiles as locate_by_tiles
from multiplanner_api.by import summarize_tiles as summarize_by_tiles
from multiplanner_api.hh import locate_tiles as locate_hh_tiles
from multiplanner_api.hh import summarize_tiles as summarize_hh_tiles
from multiplanner_api.geosn import locate_tiles as locate_geosn_tiles
from multiplanner_api.geosn import summarize_tiles as summarize_geosn_tiles
from multiplanner_api.he import locate_tiles as locate_he_tiles
from multiplanner_api.he import summarize_tiles as summarize_he_tiles
from multiplanner_api.st import locate_tiles as locate_st_tiles
from multiplanner_api.st import summarize_tiles as summarize_st_tiles
from multiplanner_api.nrw import locate_tiles as locate_nrw_tiles
from multiplanner_api.nrw import summarize_tiles as summarize_nrw_tiles
from multiplanner_api.be import locate_tiles as locate_be_tiles
from multiplanner_api.be import summarize_tiles as summarize_be_tiles
from multiplanner_api.hb import locate_tiles as locate_hb_tiles
from multiplanner_api.hb import summarize_tiles as summarize_hb_tiles
from multiplanner_api.mv import locate_tiles as locate_mv_tiles
from multiplanner_api.mv import summarize_tiles as summarize_mv_tiles
from multiplanner_api.sh import locate_tiles as locate_sh_tiles
from multiplanner_api.sh import summarize_tiles as summarize_sh_tiles

SERVICE_PROVIDERS = {
    "lgln-ni": {
        "label": "Saxony Lower LGLN",
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
    },
    "geobasis-nrw": {
        "label": "NRW Geobasis",
        "adapter": "nrw_grid",
        "datasets": {
            "dgm1": {
                "base_url": "https://www.opengeodata.nrw.de/produkte/geobasis/hm/dgm1_tiff/dgm1_tiff/",
                "catalog_url": "https://www.opengeodata.nrw.de/produkte/geobasis/hm/dgm1_tiff/dgm1_tiff/",
                "filename_prefix": "dgm1",
            },
            "dom1": {
                "base_url": "https://www.opengeodata.nrw.de/produkte/geobasis/hm/dom1_tiff/dom1_tiff/",
                "catalog_url": "https://www.opengeodata.nrw.de/produkte/geobasis/hm/dom1_tiff/dom1_tiff/",
                "filename_prefix": "dom1",
            },
        },
    },
    "geosn-sn": {
        "label": "Saxony GeoSN",
        "adapter": "geosn_grid",
        "datasets": {
            "dgm1": {
                "base_url": "https://geocloud.landesvermessung.sachsen.de/public.php/dav/files/JCcXyifaNdLDnxZ/",
            },
            "dom1": {
                "base_url": "https://geocloud.landesvermessung.sachsen.de/public.php/dav/files/S6wwnFwX7882sZm/",
            },
        },
    },
    "hvbg-he": {
        "label": "Hessen HVBG",
        "adapter": "hvbg_he_wcs",
        "datasets": {
            "dgm1": {},
            "dom1": {},
        },
    },
    "lvermgeo-st": {
        "label": "Saxony-Anhalt LVermGeo",
        "adapter": "lvermgeo_st_wcs",
        "datasets": {
            "dgm1": {},
        },
    },
    "geobasis-bb": {
        "label": "Brandenburg Geobasis",
        "adapter": "geobasis_bb_wcs",
        "datasets": {
            "dgm1": {},
        },
    },
    "lgl-bw": {
        "label": "Baden-Wuerttemberg LGL",
        "adapter": "lgl_bw_gridzip",
        "datasets": {
            "dgm1": {},
        },
    },
    "ldbv-by": {
        "label": "Bayern LDBV",
        "adapter": "ldbv_by_metalink",
        "datasets": {
            "dgm1": {},
        },
    },
    "lgv-hh": {
        "label": "Hamburg LGV",
        "adapter": "lgv_hh_ogc",
        "datasets": {
            "dgm1": {},
        },
    },
    "lvermgeo-sh": {
        "label": "Schleswig-Holstein LVermGeo",
        "adapter": "lvermgeo_sh_geojson",
        "datasets": {
            "dgm1": {},
        },
    },
    "laiv-mv": {
        "label": "Mecklenburg-Vorpommern LAiV",
        "adapter": "laiv_mv_wcs",
        "datasets": {
            "dgm1": {},
        },
    },
    "lginf-hb": {
        "label": "Bremen Landesamt Geoinformation",
        "adapter": "lginf_hb_bulk",
        "datasets": {
            "dgm1": {},
        },
    },
    "gdi-be": {
        "label": "Berlin GDI",
        "adapter": "gdi_be_atom",
        "datasets": {
            "dgm1": {},
            "dom1": {},
            "bdom": {},
        },
    },
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


def polygon_geometry(coordinates: list[tuple[float, float]]) -> tuple[str, str]:
    if len(coordinates) < 3:
        raise ValueError("A polygon selection needs at least three coordinates.")
    ring = [[float(lon), float(lat)] for lon, lat in coordinates]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return json.dumps({"rings": [ring], "spatialReference": {"wkid": 4326}}), "esriGeometryPolygon"


def locate_remote_tiles(
    provider: str,
    dataset: str,
    *,
    geometry: str,
    geometry_type: str,
    timeout: int = 60,
) -> list[dict[str, Any]]:
    if SERVICE_PROVIDERS[provider].get("adapter") == "geosn_grid":
        return locate_geosn_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)
    if SERVICE_PROVIDERS[provider].get("adapter") == "hvbg_he_wcs":
        return locate_he_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)
    if SERVICE_PROVIDERS[provider].get("adapter") == "lvermgeo_st_wcs":
        return locate_st_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)
    if SERVICE_PROVIDERS[provider].get("adapter") == "geobasis_bb_wcs":
        return locate_bb_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)
    if SERVICE_PROVIDERS[provider].get("adapter") == "lgl_bw_gridzip":
        return locate_bw_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)
    if SERVICE_PROVIDERS[provider].get("adapter") == "ldbv_by_metalink":
        return locate_by_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)
    if SERVICE_PROVIDERS[provider].get("adapter") == "lgv_hh_ogc":
        return locate_hh_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)
    if SERVICE_PROVIDERS[provider].get("adapter") == "nrw_grid":
        return locate_nrw_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)
    if SERVICE_PROVIDERS[provider].get("adapter") == "lvermgeo_sh_geojson":
        return locate_sh_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)
    if SERVICE_PROVIDERS[provider].get("adapter") == "laiv_mv_wcs":
        return locate_mv_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)
    if SERVICE_PROVIDERS[provider].get("adapter") == "lginf_hb_bulk":
        return locate_hb_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)
    if SERVICE_PROVIDERS[provider].get("adapter") == "gdi_be_atom":
        return locate_be_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)

    config = _dataset_config(provider, dataset)
    response = requests.post(
        config["query_url"],
        data=_query_params(geometry=geometry, geometry_type=geometry_type),
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
    if SERVICE_PROVIDERS[provider].get("adapter") == "geosn_grid":
        return summarize_geosn_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)
    if SERVICE_PROVIDERS[provider].get("adapter") == "hvbg_he_wcs":
        return summarize_he_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)
    if SERVICE_PROVIDERS[provider].get("adapter") == "lvermgeo_st_wcs":
        return summarize_st_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)
    if SERVICE_PROVIDERS[provider].get("adapter") == "geobasis_bb_wcs":
        return summarize_bb_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)
    if SERVICE_PROVIDERS[provider].get("adapter") == "lgl_bw_gridzip":
        return summarize_bw_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)
    if SERVICE_PROVIDERS[provider].get("adapter") == "ldbv_by_metalink":
        return summarize_by_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)
    if SERVICE_PROVIDERS[provider].get("adapter") == "lgv_hh_ogc":
        return summarize_hh_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)
    if SERVICE_PROVIDERS[provider].get("adapter") == "nrw_grid":
        return summarize_nrw_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)
    if SERVICE_PROVIDERS[provider].get("adapter") == "lvermgeo_sh_geojson":
        return summarize_sh_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)
    if SERVICE_PROVIDERS[provider].get("adapter") == "laiv_mv_wcs":
        return summarize_mv_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)
    if SERVICE_PROVIDERS[provider].get("adapter") == "lginf_hb_bulk":
        return summarize_hb_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)
    if SERVICE_PROVIDERS[provider].get("adapter") == "gdi_be_atom":
        return summarize_be_tiles(dataset, config=_dataset_config(provider, dataset), geometry=geometry, geometry_type=geometry_type, timeout=timeout)

    config = _dataset_config(provider, dataset)
    summaries: list[dict[str, Any]] = []
    for attrs in locate_remote_tiles(
        provider,
        dataset,
        geometry=geometry,
        geometry_type=geometry_type,
        timeout=timeout,
    ):
        summaries.append(_tile_summary(provider, dataset, attrs, config))
    return summaries


def _tile_summary(provider: str, dataset: str, attrs: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
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
    return summary
