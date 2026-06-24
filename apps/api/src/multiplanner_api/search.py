from __future__ import annotations

import re

import requests

from multiplanner_api.config import load_settings
from multiplanner_api.models import SearchCandidate, SearchPlacesResponse

COORDINATE_PATTERN = re.compile(
    r"^\s*(-?\d+(?:\.\d+)?)\s*[,;\s]\s*(-?\d+(?:\.\d+)?)\s*$"
)


def search_places(query: str) -> SearchPlacesResponse:
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("Query must not be empty.")

    coordinate_candidate = _parse_coordinates(cleaned)
    if coordinate_candidate is not None:
        return SearchPlacesResponse(query=query, candidates=[coordinate_candidate])

    return SearchPlacesResponse(query=query, candidates=_search_nominatim(cleaned))


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


def _search_nominatim(query: str) -> list[SearchCandidate]:
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

    response = requests.get(
        settings.geocoder_url,
        params=params,
        headers={"User-Agent": "MultiPlanner/0.1"},
        timeout=30,
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
