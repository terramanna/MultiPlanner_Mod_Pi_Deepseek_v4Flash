"""Semantic clutter helpers for Ellipse classified-grid pilots."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from shapely.geometry import MultiPoint, Polygon, mapping, shape
from shapely.ops import unary_union

NO_DATA = 0

BRD20_CLASSES = (
    (1, "sea", (0, 0, 160)),
    (2, "inland water", (0, 255, 255)),
    (3, "wetland", (0, 128, 128)),
    (4, "barren", (255, 255, 128)),
    (5, "low vegetation", (0, 255, 0)),
    (6, "sparse forest", (0, 128, 0)),
    (7, "forest", (128, 128, 0)),
    (8, "village", (128, 128, 255)),
    (9, "residential with trees", (255, 128, 192)),
    (10, "residential with few trees", (255, 128, 255)),
    (11, "dense residential", (255, 0, 255)),
    (12, "urban", (255, 0, 128)),
    (13, "dense urban", (128, 0, 255)),
    (14, "high buildings", (128, 0, 64)),
    (15, "building blocks", (0, 0, 0)),
    (16, "commercial-industrial", (255, 128, 0)),
    (17, "airport", (128, 64, 0)),
    (18, "open in urban", (191, 191, 191)),
)


@dataclass(frozen=True)
class ClassFamily:
    name: str
    start_code: int
    color: tuple[int, int, int]


CLASS_FAMILIES = {
    "forest": ClassFamily("forest", 1, (34, 139, 34)),
    "woodland": ClassFamily("woodland", 43, (107, 142, 35)),
    "building": ClassFamily("building", 85, (145, 84, 46)),
}


def agl_height_grid(dgm: np.ndarray, dom: np.ndarray, semantic_mask: np.ndarray) -> np.ndarray:
    """Return obstacle height in metres only where semantic clutter exists."""
    if dgm.shape != dom.shape or dgm.shape != semantic_mask.shape:
        raise ValueError("DGM, DOM, and semantic mask must have identical shapes")
    valid = (semantic_mask != NO_DATA) & np.isfinite(dgm) & np.isfinite(dom)
    height = np.zeros(dgm.shape, dtype=np.float32)
    height[valid] = np.maximum(dom[valid] - dgm[valid], 0)
    return height


def brd20_clutter_grid(base: np.ndarray, agl_height: np.ndarray, semantic_mask: np.ndarray) -> np.ndarray:
    """Overlay DLM vegetation and LoD2 buildings on a BRD20 class grid."""
    if base.shape != agl_height.shape or base.shape != semantic_mask.shape:
        raise ValueError("Base clutter, AGL height, and semantic mask must have identical shapes")
    clutter = base.astype(np.uint8, copy=True)
    clutter[semantic_mask == CLASS_FAMILIES["forest"].start_code] = 7
    clutter[semantic_mask == CLASS_FAMILIES["woodland"].start_code] = 6
    buildings = semantic_mask == CLASS_FAMILIES["building"].start_code
    clutter[buildings & (agl_height < 8)] = 12
    clutter[buildings & (agl_height >= 8) & (agl_height < 25)] = 13
    clutter[buildings & (agl_height >= 25)] = 14
    return clutter


def write_geojson(path: Path, features: Iterable[dict[str, object]]) -> None:
    payload = {
        "type": "FeatureCollection",
        "name": path.stem,
        "crs": {"type": "name", "properties": {"name": "EPSG:32632"}},
        "features": list(features),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_mapinfo_class_profile(path: Path) -> None:
    """Write MapInfo Raster's native XML classification-profile format."""
    root = ET.Element(
        "ClassifiedIntervalStoreType",
        {"xmlns:xsd": "http://www.w3.org/2001/XMLSchema", "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance"},
    )
    ET.SubElement(root, "GridOutputType").text = "Classified"
    ET.SubElement(root, "GridInputType").text = "Numeric"
    intervals = ET.SubElement(root, "IntervalList")
    for code, label, color in BRD20_CLASSES:
        _add_mapinfo_interval(intervals, code, label, color)
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def _add_mapinfo_interval(parent: ET.Element, code: int, label: str, color: tuple[int, int, int]) -> None:
    interval = ET.SubElement(parent, "IntervalLine")
    for name in ("LowerLimitIsValid", "UpperLimitIsValid", "IsIntervalLineValid"):
        ET.SubElement(interval, name).text = "true"
    ET.SubElement(interval, "LowerLimit").text = str(code)
    ET.SubElement(interval, "UpperLimit").text = str(code + 1)
    ET.SubElement(interval, "NewClassName").text = label
    _add_mapinfo_color(interval, "ColorValue", 255, color)
    ET.SubElement(interval, "NewValue").text = str(code)
    _add_mapinfo_color(interval, "ClassifiedColorValue", 0, (0, 0, 0))
    ET.SubElement(interval, "ClassifiedNewValue").text = "0"


def _add_mapinfo_color(parent: ET.Element, name: str, alpha: int, color: tuple[int, int, int]) -> None:
    color_node = ET.SubElement(parent, name)
    channels = (alpha, *color)
    for channel_name, value in zip(("A", "R", "G", "B"), channels, strict=True):
        ET.SubElement(color_node, channel_name).text = str(value)
    scaled = (alpha / 255, *(_linear_srgb(value) for value in color))
    for channel_name, value in zip(("ScA", "ScR", "ScG", "ScB"), scaled, strict=True):
        ET.SubElement(color_node, channel_name).text = f"{value:.9g}"


def _linear_srgb(value: int) -> float:
    normalized = value / 255
    return normalized / 12.92 if normalized <= 0.04045 else ((normalized + 0.055) / 1.055) ** 2.4


def dlm_vegetation_features(path: Path) -> list[dict[str, object]]:
    features: list[dict[str, object]] = []
    for _, elem in ET.iterparse(path, events=("end",)):
        name = _local_name(elem.tag)
        if name in {"AX_Wald", "AX_Gehoelz"}:
            features.extend(_dlm_element_features(elem, name))
            elem.clear()
    return features


def lod2_building_features(paths: Iterable[Path]) -> list[dict[str, object]]:
    features: list[dict[str, object]] = []
    for path in paths:
        features.extend(_lod2_file_features(path))
    return features


def _dlm_element_features(elem: ET.Element, name: str) -> list[dict[str, object]]:
    family = "forest" if name == "AX_Wald" else "woodland"
    features = []
    for polygon in _polygon_shapes(elem):
        features.append(_feature(polygon, {"family": family, "burn": CLASS_FAMILIES[family].start_code}))
    return features


def _lod2_file_features(path: Path) -> list[dict[str, object]]:
    features: list[dict[str, object]] = []
    for _, elem in ET.iterparse(path, events=("end",)):
        if _local_name(elem.tag) == "Building":
            footprint = _building_footprint(elem)
            if footprint is not None:
                features.append(_feature(footprint, {"family": "building", "burn": CLASS_FAMILIES["building"].start_code}))
            elem.clear()
    return features


def _building_footprint(elem: ET.Element):
    polygons = [poly for poly in _polygon_shapes(elem) if poly.area > 0.5]
    if not polygons:
        return None
    merged = unary_union(polygons)
    if merged.is_empty:
        return None
    return merged


def _polygon_shapes(elem: ET.Element) -> list[Polygon]:
    polygons = []
    for polygon in _children_by_name(elem, "Polygon"):
        shape_polygon = _polygon_from_element(polygon)
        if shape_polygon is not None:
            polygons.append(shape_polygon)
    return polygons


def _polygon_from_element(elem: ET.Element) -> Polygon | None:
    rings = [_coords_from_pos_list(pos_list) for pos_list in _children_by_name(elem, "posList")]
    rings = [ring for ring in rings if len(ring) >= 3]
    if not rings:
        return None
    polygon = Polygon(rings[0], rings[1:])
    if polygon.is_valid and polygon.area > 0:
        return polygon
    hull = MultiPoint(rings[0]).convex_hull
    return hull if isinstance(hull, Polygon) and hull.area > 0 else None


def _coords_from_pos_list(elem: ET.Element) -> list[tuple[float, float]]:
    values = [float(value) for value in (elem.text or "").split()]
    dimension = int(elem.attrib.get("srsDimension", "3" if len(values) % 3 == 0 else "2"))
    return [(values[index], values[index + 1]) for index in range(0, len(values) - 1, dimension)]


def _children_by_name(elem: ET.Element, name: str) -> Iterable[ET.Element]:
    return (child for child in elem.iter() if _local_name(child.tag) == name)


def _feature(geometry, properties: dict[str, object]) -> dict[str, object]:
    cleaned = shape(mapping(geometry)).buffer(0)
    return {"type": "Feature", "properties": properties, "geometry": mapping(cleaned)}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
