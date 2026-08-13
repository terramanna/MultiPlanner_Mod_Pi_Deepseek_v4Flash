"""Geometry-driven Bayern building and tree GRC exports for Ellipse."""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image
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
FOREST_COLORS = (
    (229, 254, 250), (220, 247, 238), (212, 240, 227), (203, 234, 215), (197, 229, 206),
    (196, 228, 198), (194, 226, 190), (192, 225, 182), (190, 223, 174), (189, 222, 166),
    (187, 220, 158), (185, 219, 148), (183, 217, 140), (182, 216, 132), (180, 214, 124),
    (178, 213, 116), (177, 211, 108), (175, 210, 100), (173, 208, 92), (170, 207, 87),
    (163, 204, 85), (154, 202, 84), (147, 199, 82), (139, 197, 80), (132, 195, 79),
    (125, 192, 77), (117, 190, 76), (110, 188, 74), (103, 185, 73), (95, 183, 71),
    (88, 181, 69), (80, 178, 68), (72, 176, 66), (65, 173, 64), (57, 171, 63),
    (50, 168, 61), (42, 166, 60), (35, 164, 58), (28, 161, 57), (20, 159, 55),
    (13, 157, 53), (6, 154, 52),
)
GeometryInput = PointGeometryInput | BboxGeometryInput | PolygonGeometryInput | CorridorGeometryInput


def export_semantic_grc(
    *, geometry: GeometryInput, lod2_paths: list[Path], dgm_paths: list[Path],
    dom_paths: list[Path], output_dir: Path, ellipse_gdal_dir: str, resolution_m: int = RESOLUTION_M,
) -> tuple[list[str], list[str]]:
    """Write separate semantic classes and variable AGL heights."""
    try:
        return _build_semantic_grc(
            geometry, lod2_paths, dgm_paths, dom_paths, output_dir, Path(ellipse_gdal_dir), resolution_m
        )
    except (FileNotFoundError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        return [], [f"Buildings + trees GRC export failed: {exc}"]


def _build_semantic_grc(
    geometry: GeometryInput, lod2_paths: list[Path], dgm_paths: list[Path],
    dom_paths: list[Path], output_dir: Path, gdal_dir: Path, resolution_m: int,
) -> tuple[list[str], list[str]]:
    tools = _required_tools(gdal_dir)
    bounds = _selection_bounds(geometry, resolution_m)
    _validate_grid(bounds, resolution_m)
    export_dir = output_dir / "semantic_grc"
    export_dir.mkdir(parents=True, exist_ok=True)
    vegetation_path = export_dir / "bayern_basis_dlm.gml"
    _download_vegetation(bounds, vegetation_path)
    mask_path = export_dir / f"semantic_mask_{resolution_m}m.tif"
    _create_mask(mask_path, bounds, tools, gdal_dir, resolution_m)
    warnings = _burn_semantics(mask_path, vegetation_path, lod2_paths, export_dir, tools, gdal_dir)
    exports = _write_height_files(
        dgm_paths, dom_paths, mask_path, bounds, export_dir, tools, gdal_dir, resolution_m
    )
    return [str(path.resolve()) for path in exports], warnings


def _required_tools(gdal_dir: Path) -> dict[str, Path]:
    names = (
        "gdal_create.exe", "gdal_rasterize.exe", "gdal_translate.exe",
        "gdalbuildvrt.exe", "gdalwarp.exe",
    )
    tools = {name: gdal_dir / name for name in names}
    missing = [str(path) for path in tools.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing Ellipse GDAL tool(s): {', '.join(missing)}")
    return tools


def _selection_bounds(
    geometry: GeometryInput, resolution_m: int = RESOLUTION_M
) -> tuple[float, float, float, float]:
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:32632", always_xy=True)
    source = _geometry_shape(geometry)
    projected = transform(transformer.transform, source)
    if isinstance(geometry, PointGeometryInput):
        projected = projected.buffer(500)
    elif isinstance(geometry, CorridorGeometryInput):
        projected = projected.buffer(geometry.buffer_m)
    return _snap_bounds(projected.bounds, resolution_m)


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


def _snap_bounds(
    bounds: tuple[float, float, float, float], resolution_m: int
) -> tuple[float, float, float, float]:
    west, south, east, north = bounds
    return (
        math.floor(west / resolution_m) * resolution_m,
        math.floor(south / resolution_m) * resolution_m,
        math.ceil(east / resolution_m) * resolution_m,
        math.ceil(north / resolution_m) * resolution_m,
    )


def _validate_grid(bounds: tuple[float, float, float, float], resolution_m: int) -> None:
    west, south, east, north = bounds
    cells = int((east - west) / resolution_m) * int((north - south) / resolution_m)
    if cells <= 0:
        raise ValueError("selection has no raster area")
    if cells > MAX_CELLS:
        raise ValueError(f"{resolution_m} m semantic grid would contain {cells:,} cells; reduce the selected area")


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
    target: Path, bounds: tuple[float, float, float, float], tools: dict[str, Path],
    gdal_dir: Path, resolution_m: int,
) -> None:
    west, south, east, north = bounds
    width = int((east - west) / resolution_m)
    height = int((north - south) / resolution_m)
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


def _write_grc_files(source: Path, export_dir: Path, resolution_m: int = RESOLUTION_M) -> list[Path]:
    converter = Path(__file__).parents[4] / "scripts" / "convert_mapinfo_grc.ps1"
    powershell = shutil.which("powershell.exe")
    if not powershell or not converter.exists():
        raise FileNotFoundError("MapInfo GRC conversion requires Windows PowerShell and convert_mapinfo_grc.ps1")
    targets = [
        export_dir / f"buildings_{resolution_m}m_utm32n.grc",
        export_dir / f"trees_{resolution_m}m_utm32n.grc",
    ]
    for layer, target in zip(("buildings", "trees"), targets, strict=True):
        target.unlink(missing_ok=True)
        subprocess.run(
            [powershell, "-NoProfile", "-File", str(converter), "-InputPath", str(source),
             "-OutputPath", str(target), "-Layer", layer],
            check=True,
        )
    return targets


def _write_height_files(
    dgm_paths: list[Path], dom_paths: list[Path], mask_path: Path,
    bounds: tuple[float, float, float, float], export_dir: Path,
    tools: dict[str, Path], gdal_dir: Path, resolution_m: int,
) -> list[Path]:
    if not dgm_paths or not dom_paths:
        raise ValueError("DGM and DOM source rasters are required for variable semantic heights")
    dgm_path = _warp_height_sources("dgm", dgm_paths, bounds, export_dir, tools, gdal_dir, resolution_m)
    dom_path = _warp_height_sources("dom", dom_paths, bounds, export_dir, tools, gdal_dir, resolution_m)
    dgm = np.asarray(Image.open(dgm_path), dtype=np.float32)
    dom = np.asarray(Image.open(dom_path), dtype=np.float32)
    mask = np.asarray(Image.open(mask_path), dtype=np.uint8)
    building_heights, tree_heights = _masked_height_grids(dgm, dom, mask)
    building_mrr, building_tif = _write_height_mrr(
        "building", building_heights, bounds, export_dir, tools, gdal_dir, resolution_m
    )
    tree_mrr, tree_tif = _write_height_mrr(
        "tree", tree_heights, bounds, export_dir, tools, gdal_dir, resolution_m
    )
    grcs = _write_height_grcs(
        building_tif, tree_tif, building_heights, tree_heights, export_dir, resolution_m
    )
    return [*grcs, building_mrr, tree_mrr]


def _warp_height_sources(
    name: str, paths: list[Path], bounds: tuple[float, float, float, float],
    export_dir: Path, tools: dict[str, Path], gdal_dir: Path, resolution_m: int,
) -> Path:
    vrt_path = export_dir / f"{name}_height_source.vrt"
    target = export_dir / f"{name}_height_source_{resolution_m}m.tif"
    _run([tools["gdalbuildvrt.exe"], vrt_path, *paths], gdal_dir)
    west, south, east, north = bounds
    _run([
        tools["gdalwarp.exe"], "-overwrite", "-t_srs", "EPSG:32632", "-te",
        west, south, east, north, "-tr", resolution_m, resolution_m,
        "-r", "bilinear", "-ot", "Float32", "-of", "GTiff", vrt_path, target,
    ], gdal_dir)
    return target


def _masked_height_grids(
    dgm: np.ndarray, dom: np.ndarray, mask: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    if dgm.shape != dom.shape or dgm.shape != mask.shape:
        raise ValueError("DGM, DOM, and semantic mask grids must align")
    agl = np.maximum(dom - dgm, 0).astype(np.float32)
    valid = np.isfinite(dgm) & np.isfinite(dom)
    building_heights = np.where(valid & (mask == 85), agl, 0).astype(np.float32)
    tree_heights = np.where(valid & np.isin(mask, (1, 43)), agl, 0).astype(np.float32)
    return building_heights, tree_heights


def _write_height_mrr(
    layer: str, values: np.ndarray, bounds: tuple[float, float, float, float],
    export_dir: Path, tools: dict[str, Path], gdal_dir: Path, resolution_m: int,
) -> tuple[Path, Path]:
    raw_path = export_dir / f"{layer}_heights_agl_{resolution_m}m_raw.tif"
    georef_path = export_dir / f"{layer}_heights_agl_{resolution_m}m_utm32n.tif"
    target = export_dir / f"{layer}_heights_agl_{resolution_m}m_utm32n.mrr"
    Image.fromarray(values, mode="F").save(raw_path)
    west, south, east, north = bounds
    _run([
        tools["gdal_translate.exe"], "-of", "GTiff", "-a_srs", "EPSG:32632",
        "-a_ullr", west, north, east, south, "-co", "COMPRESS=LZW", raw_path, georef_path,
    ], gdal_dir)
    _convert_to_mrr(georef_path, target)
    return target, georef_path


def _write_height_grcs(
    building_tif: Path, tree_tif: Path, building_values: np.ndarray, tree_values: np.ndarray,
    export_dir: Path, resolution_m: int,
) -> list[Path]:
    building_max = _maximum_height(building_values)
    tree_max = _maximum_height(tree_values, minimum=41.0)
    sources = (("building_heights", building_tif, building_values), ("tree_heights", tree_tif, tree_values))
    targets = [
        export_dir / f"buildings_{resolution_m}m_utm32n.grc",
        export_dir / f"trees_{resolution_m}m_utm32n.grc",
    ]
    for (layer, source, _values), target, maximum in zip(
        sources, targets, (building_max, tree_max), strict=True
    ):
        _convert_height_grc(source, target, layer, maximum)
    styles = [
        export_dir / f"buildings_{resolution_m}m_height_table.vse",
        export_dir / f"trees_{resolution_m}m_height_table.vse",
    ]
    definitions = [
        export_dir / f"buildings_{resolution_m}m_height_definition.xml",
        export_dir / f"trees_{resolution_m}m_height_definition.xml",
    ]
    ground_types = [
        export_dir / f"buildings_{resolution_m}m_ground_type.xml",
        export_dir / f"trees_{resolution_m}m_ground_type.xml",
    ]
    building_colors = _building_colors(building_max)
    tree_colors = _forest_colors(tree_max)
    _write_height_vse(styles[0], "Building", building_colors)
    _write_height_vse(styles[1], "Forest", tree_colors)
    _write_height_definition(definitions[0], "Building", len(building_colors))
    _write_height_definition(definitions[1], "Forest", len(tree_colors))
    _write_ground_type_definition(
        ground_types[0], "Building", len(building_colors), "average_ground"
    )
    _write_ground_type_definition(
        ground_types[1], "Forest", len(tree_colors), "tree_foliage_medium"
    )
    return [*targets, *styles, *definitions, *ground_types]


def _maximum_height(values: np.ndarray, minimum: float = 1.0) -> float:
    finite = values[np.isfinite(values)]
    return max(minimum, float(finite.max(initial=0)))


def _building_colors(max_height: float) -> tuple[tuple[int, int, int], ...]:
    top = max(1, math.ceil(max_height * 2))
    start, end = (232, 213, 195), (125, 76, 45)
    return tuple(
        tuple(round(start[index] + ((end[index] - start[index]) * step / top)) for index in range(3))
        for step in range(1, top + 1)
    )


def _forest_colors(max_height: float) -> tuple[tuple[int, int, int], ...]:
    return tuple(_forest_color(step / 2) for step in range(1, max(1, math.ceil(max_height * 2)) + 1))


def _forest_color(height: float) -> tuple[int, int, int]:
    if height <= 0.5:
        return FOREST_COLORS[0]
    low = min(41, math.floor(height))
    high = min(41, math.ceil(height))
    fraction = height - math.floor(height)
    return tuple(round(a + ((b - a) * fraction)) for a, b in zip(FOREST_COLORS[low], FOREST_COLORS[high], strict=True))


def _write_height_vse(path: Path, prefix: str, colors: tuple[tuple[int, int, int], ...]) -> None:
    labels = [f"{prefix} {(step / 2):.1f}m" for step in range(1, len(colors) + 1)]
    rows = ['"237,234,217" "No data"']
    rows.extend(f'"{red},{green},{blue}" "{label}"' for (red, green, blue), label in zip(colors, labels, strict=True))
    content = "\n".join(("VSE_Color_Type", "False", "False", str(len(rows)), *rows, ""))
    path.write_text(content, encoding="utf-8")


def _write_height_definition(path: Path, prefix: str, class_count: int) -> None:
    root = ET.Element("generic_scale")
    scale = ET.SubElement(root, "echelle", {
        "type": "CEchelleDiscrete_Raster`1", "name": "Height definition",
        "printLegend": "True", "Legend": "",
    })
    for index in range(class_count + 1):
        height = index / 2
        label = "No data" if index == 0 else f"{prefix} {height:.1f}m"
        ET.SubElement(scale, "settings_type", {
            "name": "CSettingsType_Height", "type": "CSettingsType_Height",
            "height": f"{height:g}",
        })
        ET.SubElement(scale, "echelle_values", {
            "setting_type": "CSettingsType_Height", "clutter_item_text": label,
            "clutter_item_val": str(index),
        })
    tree = ET.ElementTree(root)
    ET.indent(tree, space="\t")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _write_ground_type_definition(
    path: Path, prefix: str, class_count: int, class_ground_type: str,
) -> None:
    root = ET.Element("generic_scale")
    scale = ET.SubElement(root, "echelle", {
        "type": "CEchelleDiscrete_Raster`1", "name": "Ground Type",
        "printLegend": "True", "Legend": "",
    })
    for index in range(class_count + 1):
        label = "No data" if index == 0 else f"{prefix} {(index / 2):.1f}m"
        ground_type = "unknown" if index == 0 else class_ground_type
        ET.SubElement(scale, "settings_type", {
            "name": "CSettingsType_GroundTypes", "type": "CSettingsType_GroundTypes",
            "ground_type": ground_type,
        })
        ET.SubElement(scale, "echelle_values", {
            "setting_type": "CSettingsType_GroundTypes", "clutter_item_text": label,
            "clutter_item_val": str(index),
        })
    tree = ET.ElementTree(root)
    ET.indent(tree, space="\t")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _convert_height_grc(source: Path, target: Path, layer: str, max_height: float) -> None:
    converter = Path(__file__).parents[4] / "scripts" / "convert_mapinfo_grc.ps1"
    powershell = shutil.which("powershell.exe")
    if not powershell or not converter.exists():
        raise FileNotFoundError("MapInfo GRC conversion requires Windows PowerShell and convert_mapinfo_grc.ps1")
    target.unlink(missing_ok=True)
    subprocess.run(
        [powershell, "-NoProfile", "-File", str(converter), "-InputPath", str(source),
         "-OutputPath", str(target), "-Layer", layer, "-MaxHeight", str(max_height)],
        check=True,
    )


def _convert_to_mrr(source: Path, target: Path) -> None:
    converter = Path(__file__).parents[4] / "scripts" / "convert_mapinfo_mrr.ps1"
    powershell = shutil.which("powershell.exe")
    if not powershell or not converter.exists():
        raise FileNotFoundError("MapInfo MRR conversion requires Windows PowerShell and convert_mapinfo_mrr.ps1")
    target.unlink(missing_ok=True)
    subprocess.run(
        [powershell, "-NoProfile", "-File", str(converter), "-InputPath", str(source),
         "-OutputPath", str(target)],
        check=True,
    )


def _run(args: list[object], gdal_dir: Path) -> None:
    command = [str(value) for value in args]
    subprocess.run(command, check=True, env=_gdal_environment(gdal_dir))
