"""Geometry-driven Bayern building and tree GRC exports for Ellipse."""

from __future__ import annotations

import math
import os
import shutil
import subprocess
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import transform

from multiplanner_api.ellipse_exports import _gdal_environment
from multiplanner_api.http_client import get_with_ssl_fallback
from multiplanner_api.models import (
    BboxGeometryInput,
    CorridorGeometryInput,
    PointGeometryInput,
    PolygonGeometryInput,
)
from multiplanner_api.semantic_clutter import dlm_vegetation_features, lod2_building_features, write_geojson

WFS_URL = "https://geoservices.bayern.de/wfs/v1/ogc_atkis_basisdlm.cgi"
WFS_QUERY = "urn:adv:def:query:OGC-WFS::AlleObjekteAnhandBboxUndCrs"
RESOLUTION_M = 2
MAX_CELLS = 50_000_000
GeometryInput = PointGeometryInput | BboxGeometryInput | PolygonGeometryInput | CorridorGeometryInput


def export_semantic_grc(
    *, geometry: GeometryInput, lod2_paths: list[Path], output_dir: Path, ellipse_gdal_dir: str
) -> tuple[list[str], list[str]]:
    """Write separate building and tree GRCs for one Bayern selection."""
    try:
        return _build_semantic_grc(geometry, lod2_paths, output_dir, Path(ellipse_gdal_dir))
    except (FileNotFoundError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        return [], [f"Buildings + trees GRC export failed: {exc}"]


def _build_semantic_grc(
    geometry: GeometryInput, lod2_paths: list[Path], output_dir: Path, gdal_dir: Path
) -> tuple[list[str], list[str]]:
    tools = _required_tools(gdal_dir)
    bounds = _selection_bounds(geometry)
    _validate_grid(bounds)
    export_dir = output_dir / "semantic_grc"
    export_dir.mkdir(parents=True, exist_ok=True)
    vegetation_path = export_dir / "bayern_basis_dlm.gml"
    _download_vegetation(bounds, vegetation_path)
    mask_path = export_dir / "semantic_mask_2m.tif"
    _create_mask(mask_path, bounds, tools, gdal_dir)
    warnings = _burn_semantics(mask_path, vegetation_path, lod2_paths, export_dir, tools, gdal_dir)
    source_path = export_dir / "semantic_mask_2m_source.grd"
    _translate_mask(mask_path, source_path, tools, gdal_dir)
    exports = _write_grc_files(source_path, export_dir)
    return [str(path.resolve()) for path in exports], warnings


def _required_tools(gdal_dir: Path) -> dict[str, Path]:
    names = ("gdal_create.exe", "gdal_rasterize.exe", "gdal_translate.exe")
    tools = {name: gdal_dir / name for name in names}
    missing = [str(path) for path in tools.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing Ellipse GDAL tool(s): {', '.join(missing)}")
    return tools


def _selection_bounds(geometry: GeometryInput) -> tuple[float, float, float, float]:
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:32632", always_xy=True)
    source = _geometry_shape(geometry)
    projected = transform(transformer.transform, source)
    if isinstance(geometry, PointGeometryInput):
        projected = projected.buffer(500)
    elif isinstance(geometry, CorridorGeometryInput):
        projected = projected.buffer(geometry.buffer_m)
    return _snap_bounds(projected.bounds)


def _geometry_shape(geometry: GeometryInput):
    if isinstance(geometry, PointGeometryInput):
        return Point(geometry.lon, geometry.lat)
    if isinstance(geometry, BboxGeometryInput):
        return box(geometry.west, geometry.south, geometry.east, geometry.north)
    if isinstance(geometry, PolygonGeometryInput):
        return Polygon(geometry.coordinates)
    if isinstance(geometry, CorridorGeometryInput):
        return LineString([(geometry.from_lon, geometry.from_lat), (geometry.to_lon, geometry.to_lat)])
    raise ValueError(f"Unsupported geometry kind: {geometry.kind}")


def _snap_bounds(bounds: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    west, south, east, north = bounds
    return (
        math.floor(west / RESOLUTION_M) * RESOLUTION_M,
        math.floor(south / RESOLUTION_M) * RESOLUTION_M,
        math.ceil(east / RESOLUTION_M) * RESOLUTION_M,
        math.ceil(north / RESOLUTION_M) * RESOLUTION_M,
    )


def _validate_grid(bounds: tuple[float, float, float, float]) -> None:
    west, south, east, north = bounds
    cells = int((east - west) / RESOLUTION_M) * int((north - south) / RESOLUTION_M)
    if cells <= 0:
        raise ValueError("selection has no raster area")
    if cells > MAX_CELLS:
        raise ValueError(f"2 m semantic grid would contain {cells:,} cells; reduce the selected area")


def _download_vegetation(bounds: tuple[float, float, float, float], target: Path) -> None:
    west, south, east, north = bounds
    response = get_with_ssl_fallback(
        WFS_URL,
        params={
            "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
            "STOREDQUERY_ID": WFS_QUERY, "CRS": "urn:ogc:def:crs:EPSG::25832",
            "x1": west, "y1": south, "x2": east, "y2": north,
        },
        timeout=180,
    )
    response.raise_for_status()
    target.write_bytes(response.content)


def _create_mask(
    target: Path, bounds: tuple[float, float, float, float], tools: dict[str, Path], gdal_dir: Path
) -> None:
    west, south, east, north = bounds
    width = int((east - west) / RESOLUTION_M)
    height = int((north - south) / RESOLUTION_M)
    target.unlink(missing_ok=True)
    _run([
        tools["gdal_create.exe"], "-of", "GTiff", "-ot", "Byte", "-outsize", width, height,
        "-a_srs", "EPSG:32632", "-a_ullr", west, north, east, south, "-a_nodata", 0, target,
    ], gdal_dir)


def _burn_semantics(
    mask_path: Path, vegetation_path: Path, lod2_paths: list[Path], export_dir: Path,
    tools: dict[str, Path], gdal_dir: Path,
) -> list[str]:
    tree_features = dlm_vegetation_features(vegetation_path)
    building_features = lod2_building_features(_gml_paths(lod2_paths))
    tree_path = export_dir / "trees.geojson"
    building_path = export_dir / "buildings.geojson"
    write_geojson(tree_path, tree_features)
    write_geojson(building_path, building_features)
    if tree_features:
        _rasterize(tree_path, mask_path, tools, gdal_dir)
    if building_features:
        _rasterize(building_path, mask_path, tools, gdal_dir)
    return _empty_layer_warnings(tree_features, building_features)


def _gml_paths(paths: list[Path]) -> list[Path]:
    return [path for path in paths if path.is_file() and path.suffix.casefold() in {".gml", ".xml"}]


def _empty_layer_warnings(tree_features: list[object], building_features: list[object]) -> list[str]:
    warnings = []
    if not building_features:
        warnings.append("No LoD2 building features intersected the selected Bayern source tiles.")
    if not tree_features:
        warnings.append("No Basis-DLM forest or woodland features intersected the selection.")
    return warnings


def _rasterize(source: Path, target: Path, tools: dict[str, Path], gdal_dir: Path) -> None:
    _run([tools["gdal_rasterize.exe"], "-a", "burn", source, target], gdal_dir)


def _translate_mask(source: Path, target: Path, tools: dict[str, Path], gdal_dir: Path) -> None:
    target.unlink(missing_ok=True)
    _run([tools["gdal_translate.exe"], "-of", "NWT_GRD", "-ot", "Float32", source, target], gdal_dir)


def _write_grc_files(source: Path, export_dir: Path) -> list[Path]:
    converter = Path(__file__).parents[4] / "scripts" / "convert_mapinfo_grc.ps1"
    powershell = shutil.which("powershell.exe")
    if not powershell or not converter.exists():
        raise FileNotFoundError("MapInfo GRC conversion requires Windows PowerShell and convert_mapinfo_grc.ps1")
    targets = [export_dir / "buildings_2m_utm32n.grc", export_dir / "trees_2m_utm32n.grc"]
    for layer, target in zip(("buildings", "trees"), targets, strict=True):
        target.unlink(missing_ok=True)
        subprocess.run(
            [powershell, "-NoProfile", "-File", str(converter), "-InputPath", str(source),
             "-OutputPath", str(target), "-Layer", layer],
            check=True,
        )
    return targets


def _run(args: list[object], gdal_dir: Path) -> None:
    command = [str(value) for value in args]
    subprocess.run(command, check=True, env=_gdal_environment(gdal_dir))
