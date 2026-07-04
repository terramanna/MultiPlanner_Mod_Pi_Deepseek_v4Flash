from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Iterable

import requests

from multiplanner_api.config import load_settings
from multiplanner_api.models import SearchCandidate, SearchPlacesResponse
from multiplanner_api.network_overlay import load_network_geojson

COORDINATE_PATTERN = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?)\s*[,;\s]\s*(-?\d+(?:\.\d+)?)\s*$"
)
GEOCODER_TIMEOUT_SECONDS = 8
NETWORK_SEARCH_FIELDS = (
    "name",
    "name2",
    "site_a",
    "site_b",
    "s_number",
    "s_number_a",
    "s_number_b",
    "bnetza_link_id",
    "project_id",
    "customer",
    "channel",
    "radio_type",
    "flags",
)
_STATIC_NETWORK_CACHE: dict[str, object] = {}
_NETWORK_INDEX_CACHE: dict[str, object] = {}


def search_places(
    query: str,
    *,
    west: float | None = None,
    south: float | None = None,
    east: float | None = None,
    north: float | None = None,
) -> SearchPlacesResponse:
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("Query must not be empty.")
    bounds = _search_bounds(west, south, east, north)

    coordinate_candidate = _parse_coordinates(cleaned)
    if coordinate_candidate is not None:
        return SearchPlacesResponse(query=query, candidates=[coordinate_candidate])

    network_candidates = _search_network(cleaned, bounds)
    geocoder_candidates = _safe_search_nominatim(cleaned, network_candidates, bounds)
    return SearchPlacesResponse(query=query, candidates=[*network_candidates, *geocoder_candidates])


def _search_bounds(
    west: float | None,
    south: float | None,
    east: float | None,
    north: float | None,
) -> tuple[float, float, float, float] | None:
    values = (west, south, east, north)
    if all(value is None for value in values):
        return None
    if any(value is None for value in values):
        raise ValueError("Search bounds must include west, south, east, and north.")
    if not (-180 <= west <= 180 and -180 <= east <= 180 and -90 <= south <= 90 and -90 <= north <= 90):
        raise ValueError("Search bounds are out of range.")
    if west >= east or south >= north:
        raise ValueError("Search bounds are invalid.")
    return west, south, east, north


def _parse_coordinates(query: str) -> SearchCandidate | None:
    match = COORDINATE_PATTERN.match(query)
    if not match:
        return None

    first = float(match.group(1))
    second = float(match.group(2))

    lon = first
    lat = second
    if -90 <= first <= 90 and -180 <= second <= 180:
        lon = second
        lat = first

    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError("Coordinate input is out of bounds.")

    return SearchCandidate(
        label=f"{lat:.6f}, {lon:.6f}",
        lon=lon,
        lat=lat,
        source="coordinates",
    )


def _search_network(query: str, bounds: tuple[float, float, float, float] | None) -> list[SearchCandidate]:
    ranked: list[tuple[int, SearchCandidate]] = []
    for values, candidate in _network_index():
        if bounds is not None and not _candidate_in_bounds(candidate, bounds):
            continue
        score = _network_match_score(values, query)
        if score is None:
            continue
        ranked.append((score, candidate))
    ranked.sort(key=lambda item: (item[0], item[1].label))
    return _unique_candidates(candidate for _score, candidate in ranked)[:8]


def _unique_candidates(candidates: Iterable[SearchCandidate]) -> list[SearchCandidate]:
    unique = []
    seen = set()
    for candidate in candidates:
        key = _candidate_key(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _candidate_key(candidate: SearchCandidate) -> tuple:
    return (
        candidate.source,
        candidate.link_name or candidate.label,
        round(candidate.lon, 7),
        round(candidate.lat, 7),
        round(candidate.site_a_lon or 0, 7),
        round(candidate.site_a_lat or 0, 7),
        round(candidate.site_b_lon or 0, 7),
        round(candidate.site_b_lat or 0, 7),
    )


def _safe_search_nominatim(
    query: str,
    network_candidates: list[SearchCandidate],
    bounds: tuple[float, float, float, float] | None,
) -> list[SearchCandidate]:
    if network_candidates and _looks_like_network_identifier(query):
        return []
    try:
        return _search_nominatim(query, bounds)
    except Exception:
        return []


def _search_nominatim(query: str, bounds: tuple[float, float, float, float] | None) -> list[SearchCandidate]:
    settings = load_settings()
    params = {
        "q": query,
        "format": "geocodejson",
        "limit": 5,
        "addressdetails": 1,
        "countrycodes": settings.geocoder_countrycodes,
    }
    if settings.geocoder_email:
        params["email"] = settings.geocoder_email
    if bounds is not None:
        west, south, east, north = bounds
        params["viewbox"] = f"{west},{north},{east},{south}"
        params["bounded"] = 1

    response = requests.get(
        settings.geocoder_url,
        params=params,
        headers={"User-Agent": "MultiPlanner/0.1"},
        timeout=GEOCODER_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    features = payload.get("features", [])
    candidates: list[SearchCandidate] = []
    for feature in features:
        coordinates = feature.get("geometry", {}).get("coordinates", [])
        if len(coordinates) < 2:
            continue
        properties = feature.get("properties", {})
        geocoding = properties.get("geocoding", {})
        label = geocoding.get("label") or properties.get("display_name") or query
        candidates.append(
            SearchCandidate(
                label=label,
                lon=float(coordinates[0]),
                lat=float(coordinates[1]),
                source="nominatim",
            )
        )
    return candidates


def _candidate_in_bounds(
    candidate: SearchCandidate,
    bounds: tuple[float, float, float, float],
) -> bool:
    west, south, east, north = bounds
    points = [(candidate.lon, candidate.lat)]
    if candidate.site_a_lon is not None and candidate.site_a_lat is not None:
        points.append((candidate.site_a_lon, candidate.site_a_lat))
    if candidate.site_b_lon is not None and candidate.site_b_lat is not None:
        points.append((candidate.site_b_lon, candidate.site_b_lat))
    return any(west <= lon <= east and south <= lat <= north for lon, lat in points)


def _network_index() -> list[tuple[tuple[str, ...], SearchCandidate]]:
    fc = _network_feature_collection()
    features = fc.get("features", []) if isinstance(fc, dict) else []
    cache_key = f"{id(fc)}:{len(features)}"
    if _NETWORK_INDEX_CACHE.get("key") != cache_key:
        _NETWORK_INDEX_CACHE.clear()
        _NETWORK_INDEX_CACHE["key"] = cache_key
        _NETWORK_INDEX_CACHE["value"] = _build_network_index(features)
    return _NETWORK_INDEX_CACHE["value"]  # type: ignore[return-value]


def _build_network_index(features: list[dict]) -> list[tuple[tuple[str, ...], SearchCandidate]]:
    entries = []
    site_lookup = _site_lookup(features)
    for feature in features:
        candidate = _network_candidate(feature, site_lookup)
        if candidate is None:
            continue
        values = _network_search_values(feature.get("properties", {}))
        entries.append((values, candidate))
    return entries


def _network_feature_collection() -> dict:
    settings = load_settings()
    if settings.network_db_path:
        return load_network_geojson(settings.network_db_path)
    return _static_network_geojson()


def _site_lookup(features: list[dict]) -> dict[str, dict]:
    return {
        feature.get("properties", {}).get("name", ""): feature.get("properties", {})
        for feature in features
        if feature.get("properties", {}).get("layer") == "site"
    }


def _static_network_geojson() -> dict:
    path = Path(__file__).resolve().parents[3] / "web" / "public" / "network.geojson"
    if not path.exists():
        return {"type": "FeatureCollection", "features": []}
    cache_key = f"{path}:{path.stat().st_mtime}"
    if _STATIC_NETWORK_CACHE.get("key") != cache_key:
        _STATIC_NETWORK_CACHE.clear()
        _STATIC_NETWORK_CACHE["key"] = cache_key
        _STATIC_NETWORK_CACHE["value"] = json.loads(path.read_text(encoding="utf-8"))
    return _STATIC_NETWORK_CACHE["value"]  # type: ignore[return-value]


def _network_search_values(properties: dict) -> tuple[str, ...]:
    values = [_field_text(properties, field).casefold() for field in NETWORK_SEARCH_FIELDS]
    return tuple(value for value in values if value)


def _network_match_score(values: tuple[str, ...], query: str) -> int | None:
    q = query.casefold()
    if any(value == q for value in values):
        return 0
    if any(value.startswith(q) for value in values):
        return 1
    if any(q in value for value in values):
        return 2
    return None


def _network_candidate(feature: dict, site_lookup: dict[str, dict]) -> SearchCandidate | None:
    props = feature.get("properties", {})
    geometry = feature.get("geometry", {})
    if props.get("layer") == "site":
        return _site_candidate(props, geometry)
    if props.get("layer") == "link":
        return _link_candidate(props, geometry, site_lookup)
    return None


def _site_candidate(props: dict, geometry: dict) -> SearchCandidate | None:
    lon, lat = _point_lon_lat(props, geometry)
    if lon is None or lat is None:
        return None
    label = f"Site {props.get('name', '')}"
    if props.get("s_number"):
        label = f"{label} ({props['s_number']})"
    if props.get("name2"):
        label = f"{label} - {props['name2']}"
    return SearchCandidate(label=label, lon=lon, lat=lat, source="network-site")


def _link_candidate(props: dict, geometry: dict, site_lookup: dict[str, dict]) -> SearchCandidate | None:
    endpoints = _line_endpoints(props, geometry)
    if endpoints is None:
        return None
    a_lon, a_lat, b_lon, b_lat = endpoints
    site_a = {**site_lookup.get(props.get("site_a", ""), {}), **props}
    site_b = {**site_lookup.get(props.get("site_b", ""), {}), **props}
    label = f"Link {props.get('name', '')} - {props.get('site_a', '')} to {props.get('site_b', '')}"
    return SearchCandidate(
        label=label,
        link_name=_field_text(props, "name"),
        lon=(a_lon + b_lon) / 2,
        lat=(a_lat + b_lat) / 2,
        source="network-link",
        distance_m=_distance_m(a_lat, a_lon, b_lat, b_lon),
        site_a_name=_field_text(props, "site_a"),
        site_a_label=_site_detail(site_a, "site_label_a", "name2"),
        site_a_id=_site_detail(site_a, "s_number_a", "s_number"),
        site_a_type=_site_detail(site_a, "site_type_a", "site_type"),
        site_a_structure=_site_structure(site_a, "site_structure_a", "flags_a", "flags"),
        site_a_lon=a_lon,
        site_a_lat=a_lat,
        site_b_name=_field_text(props, "site_b"),
        site_b_label=_site_detail(site_b, "site_label_b", "name2"),
        site_b_id=_site_detail(site_b, "s_number_b", "s_number"),
        site_b_type=_site_detail(site_b, "site_type_b", "site_type"),
        site_b_structure=_site_structure(site_b, "site_structure_b", "flags_b", "flags"),
        site_b_lon=b_lon,
        site_b_lat=b_lat,
    )


def _site_detail(props: dict, primary: str, fallback: str) -> str:
    return _field_text(props, primary) or _field_text(props, fallback)


def _site_structure(props: dict, primary: str, flags_primary: str, flags_fallback: str) -> str:
    return _field_text(props, primary) or _structure_from_flags(_site_detail(props, flags_primary, flags_fallback))


def _structure_from_flags(flags: str) -> str:
    known = ("Mast", "Dach", "Kamin", "Grundstück", "Cellular", "Aggregation")
    tokens = {value.strip().casefold(): value.strip() for value in flags.split(";") if value.strip()}
    for label in known:
        if label.casefold() in tokens:
            return tokens[label.casefold()]
    return ""


def _distance_m(first_lat: float, first_lon: float, second_lat: float, second_lon: float) -> float:
    radius_m = 6_371_000
    delta_lat = math.radians(second_lat - first_lat)
    delta_lon = math.radians(second_lon - first_lon)
    first_lat_r = math.radians(first_lat)
    second_lat_r = math.radians(second_lat)
    h = math.sin(delta_lat / 2) ** 2 + math.cos(first_lat_r) * math.cos(second_lat_r) * math.sin(delta_lon / 2) ** 2
    return 2 * radius_m * math.atan2(math.sqrt(h), math.sqrt(1 - h))


def _point_lon_lat(props: dict, geometry: dict) -> tuple[float | None, float | None]:
    coordinates = geometry.get("coordinates", [])
    lon = props.get("lon", coordinates[0] if len(coordinates) >= 2 else None)
    lat = props.get("lat", coordinates[1] if len(coordinates) >= 2 else None)
    return _float_or_none(lon), _float_or_none(lat)


def _line_endpoints(props: dict, geometry: dict) -> tuple[float, float, float, float] | None:
    coordinates = geometry.get("coordinates", [])
    if len(coordinates) >= 2:
        a_lon, a_lat = coordinates[0][:2]
        b_lon, b_lat = coordinates[-1][:2]
    else:
        a_lon, a_lat = props.get("lon_a"), props.get("lat_a")
        b_lon, b_lat = props.get("lon_b"), props.get("lat_b")
    values = [_float_or_none(value) for value in (a_lon, a_lat, b_lon, b_lat)]
    if any(value is None for value in values):
        return None
    return values[0], values[1], values[2], values[3]  # type: ignore[return-value]


def _field_text(properties: dict, field: str) -> str:
    value = properties.get(field)
    return str(value).strip() if value is not None else ""


def _looks_like_network_identifier(query: str) -> bool:
    clean = query.strip()
    has_alpha = any(char.isalpha() for char in clean)
    has_digit = any(char.isdigit() for char in clean)
    return "_" in clean or (has_alpha and has_digit and len(clean) >= 4)


def _float_or_none(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
