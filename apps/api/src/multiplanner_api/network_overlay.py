"""Read-only network overlay: queries the NSP/Ellipse inventory DB and returns
a GeoJSON FeatureCollection of sites (Points) and links (LineStrings).

Only Primary and Nominal links are included. The result is cached by DB
mtime so repeated requests are instant. The cache is invalidated automatically
when the DB file changes (e.g. after a fresh import in the NSP tool).

Configure the DB path via MULTIPLANNER_NETWORK_DB_PATH env var.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

_CACHE: dict = {}

_ACTIVE_STATES = ("30_Primary", "20_Nominal")

_SITE_SQL = """
    SELECT site_name, site_name_2, latitude, longitude,
           site_type, site_status, s_number, flags_csv
    FROM ellipse_site_current
    WHERE is_active = 1
      AND latitude  BETWEEN -90  AND 90
      AND longitude BETWEEN -180 AND 180
      AND site_status GLOB '[0-8]*'
"""

_LINK_SQL = """
    SELECT DISTINCT
        l.link_name, l.link_state, l.link_status, l.license_status,
        l.radio_type, l.channel,
        l.site_a_name, l.site_b_name,
        l.site_status_a, l.site_status_b,
        l.s_number_a, l.s_number_b,
        l.bnetza_link_id,
        sa.latitude  AS lat_a, sa.longitude AS lon_a,
        sb.latitude  AS lat_b, sb.longitude AS lon_b,
        st_a.radio_circuit_planer, st_a.directional_radio_planer,
        st_a.project_id, st_a.project_status, st_a.customer,
        st_a.site_status  AS tracker_status_a,
        st_b.site_status  AS tracker_status_b
    FROM ellipse_link_current l
    JOIN ellipse_site_current sa ON sa.site_name = l.site_a_name
    JOIN ellipse_site_current sb ON sb.site_name = l.site_b_name
    LEFT JOIN site_tracker_current st_a
           ON st_a.link_name = l.link_name AND st_a.side = 'A' AND st_a.is_active = 1
    LEFT JOIN site_tracker_current st_b
           ON st_b.link_name = l.link_name AND st_b.side = 'B' AND st_b.is_active = 1
    WHERE l.is_active = 1
      AND l.link_state IN ('30_Primary', '20_Nominal')
      AND sa.latitude BETWEEN -90 AND 90
      AND sb.latitude BETWEEN -90 AND 90
"""


def load_network_geojson(db_path: str) -> dict:
    """Return a cached GeoJSON FeatureCollection; empty if DB not configured."""
    if not db_path:
        return _empty_fc()
    path = Path(db_path)
    if not path.exists():
        return _empty_fc()
    cache_key = (str(path.resolve()), path.stat().st_mtime)
    if cache_key in _CACHE:
        return _CACHE[cache_key]
    result = _build_geojson(str(path))
    _CACHE.clear()
    _CACHE[cache_key] = result
    return result


def _empty_fc() -> dict:
    return {"type": "FeatureCollection", "features": []}


def _build_geojson(db_path: str) -> dict:
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        features = _query_sites(cur) + _query_links(cur)
        return {"type": "FeatureCollection", "features": features}
    finally:
        conn.close()


def _query_sites(cur: sqlite3.Cursor) -> list[dict]:
    cur.execute(_SITE_SQL)
    return [_site_feature(row) for row in cur.fetchall()]


def _query_links(cur: sqlite3.Cursor) -> list[dict]:
    cur.execute(_LINK_SQL)
    return [_link_feature(row) for row in cur.fetchall()]


def _site_feature(row: sqlite3.Row) -> dict:
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [row["longitude"], row["latitude"]],
        },
        "properties": {
            "layer": "site",
            "name": row["site_name"],
            "name2": row["site_name_2"] or "",
            "site_type": row["site_type"] or "",
            "site_status": row["site_status"] or "",
            "s_number": row["s_number"] or "",
            "flags": row["flags_csv"] or "",
            "lat": row["latitude"],
            "lon": row["longitude"],
        },
    }


def _link_feature(row: sqlite3.Row) -> dict:
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [row["lon_a"], row["lat_a"]],
                [row["lon_b"], row["lat_b"]],
            ],
        },
        "properties": {
            "layer": "link",
            "name": row["link_name"],
            "state": row["link_state"],
            "status": row["link_status"] or "",
            "license_status": row["license_status"] or "",
            "radio_type": row["radio_type"] or "",
            "channel": row["channel"] or "",
            "site_a": row["site_a_name"],
            "site_b": row["site_b_name"],
            "site_status_a": row["site_status_a"] or "",
            "site_status_b": row["site_status_b"] or "",
            "tracker_status_a": row["tracker_status_a"] or "",
            "tracker_status_b": row["tracker_status_b"] or "",
            "s_number_a": row["s_number_a"] or "",
            "s_number_b": row["s_number_b"] or "",
            "bnetza_link_id": row["bnetza_link_id"] or "",
            "rc_planer": row["radio_circuit_planer"] or "",
            "dr_planer": row["directional_radio_planer"] or "",
            "project_id": row["project_id"] or "",
            "project_status": row["project_status"] or "",
            "customer": row["customer"] or "",
            "lat_a": row["lat_a"],
            "lon_a": row["lon_a"],
            "lat_b": row["lat_b"],
            "lon_b": row["lon_b"],
        },
    }
