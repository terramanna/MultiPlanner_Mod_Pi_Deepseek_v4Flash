"""Download the reproducible Munich semantic-clutter pilot source set.

Run from the repository root with the project virtual environment. The script
uses the installed MapInfo Raster API to write separate building and tree GRCs.
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from multiplanner_api.downloads import download_subset
from multiplanner_api.ellipse_exports import _gdal_environment, _write_mapinfo_tab
from multiplanner_api.http_client import get_with_ssl_fallback
from multiplanner_api.models import BboxGeometryInput, DownloadSubsetRequest
from multiplanner_api.semantic_clutter import (
    agl_height_grid,
    brd20_clutter_grid,
    dlm_vegetation_features,
    lod2_building_features,
    write_geojson,
    write_mapinfo_class_profile,
)

PILOT_NAME = "munich_marienplatz_4km_semantic_pilot"
PILOT_BBOX = BboxGeometryInput(kind="bbox", west=11.5486, south=48.1192, east=11.6026, north=48.1552)
WFS_URL = "https://geoservices.bayern.de/wfs/v1/ogc_atkis_basisdlm.cgi"
WFS_QUERY = "urn:adv:def:query:OGC-WFS::AlleObjekteAnhandBboxUndCrs"
PILOT_BOUNDS_25832 = (689611.216, 5332758.053, 693611.216, 5336758.053)
RESOLUTION_M = 2
GDAL_DIR = Path(os.environ.get("MULTIPLANNER_ELLIPSE_GDAL_DIR", r"C:\Program Files\InfoVista\Ellipse 9\gdal"))
BRD20_PATH = Path(os.environ.get("MULTIPLANNER_BRD20_CLUTTER_PATH", r"D:\Gis\Ellipse\Geodata\Clutter\BRD20m_clutter.grc"))


def main() -> None:
    response = download_subset(_download_request())
    output_dir = Path(response.output_dir)
    _write_manifest(output_dir, response.model_dump())
    _download_basis_dlm(output_dir)
    _ensure_terrain_exports(output_dir)
    _build_semantic_intermediate(output_dir)
    print(f"Cached pilot inputs in {output_dir}")


def _download_request() -> DownloadSubsetRequest:
    return DownloadSubsetRequest(
        provider="ldbv-by",
        datasets=["dgm1", "dom1", "bdom"],
        geometry=PILOT_BBOX,
        selection_name=PILOT_NAME,
        export_profile="source_tiles",
    )


def _terrain_export_request() -> DownloadSubsetRequest:
    return DownloadSubsetRequest(
        provider="ldbv-by",
        datasets=["dgm1", "dom1"],
        geometry=PILOT_BBOX,
        selection_name=PILOT_NAME,
        export_profile="ellipse_mapinfo_tab_pyramids",
    )


def _ensure_terrain_exports(output_dir: Path) -> None:
    if _has_terrain_exports(output_dir):
        return
    response = download_subset(_terrain_export_request())
    if response.warnings:
        raise RuntimeError(f"Terrain export warnings: {response.warnings}")


def _has_terrain_exports(output_dir: Path) -> bool:
    try:
        _terrain_paths(output_dir)
    except FileNotFoundError:
        return False
    return True


def _write_manifest(output_dir: Path, payload: dict[str, object]) -> None:
    (output_dir / "pilot-source-manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _download_basis_dlm(output_dir: Path) -> None:
    target = output_dir / "basis_dlm"
    target.mkdir(exist_ok=True)
    basis_dlm_path = target / "munich_pilot_basis_dlm.gml"
    if basis_dlm_path.exists() and basis_dlm_path.stat().st_size > 0:
        return
    min_x, min_y, max_x, max_y = PILOT_BOUNDS_25832
    response = get_with_ssl_fallback(
        WFS_URL,
        params={
            "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
            "STOREDQUERY_ID": WFS_QUERY, "CRS": "urn:ogc:def:crs:EPSG::25832",
            "x1": min_x, "y1": min_y, "x2": max_x, "y2": max_y,
        },
        timeout=180,
    )
    response.raise_for_status()
    basis_dlm_path.write_bytes(response.content)


def _build_semantic_intermediate(output_dir: Path) -> None:
    semantic_dir = output_dir / "semantic_clutter"
    semantic_dir.mkdir(exist_ok=True)
    _write_vectors(output_dir, semantic_dir)
    dgm_path, dom_path = _terrain_paths(output_dir)
    dgm_2m = semantic_dir / "munich_pilot_dgm_2m.tif"
    dom_2m = semantic_dir / "munich_pilot_dom_2m.tif"
    mask_path = semantic_dir / "munich_pilot_semantic_mask_2m.tif"
    base_path = semantic_dir / "munich_pilot_brd20_base_2m.tif"
    final_path = semantic_dir / "munich_pilot_brd_schema_clutter_2m.tif"
    _warp_to_grid(dgm_path, dgm_2m, "bilinear", "Float32")
    _warp_to_grid(dom_path, dom_2m, "bilinear", "Float32")
    _create_mask(mask_path)
    _rasterize_vectors(semantic_dir, mask_path)
    mask_grd = _write_grd_source(mask_path)
    _write_separate_grc(mask_grd, semantic_dir)
    agl_path = _write_agl_height(dgm_2m, dom_2m, mask_path, semantic_dir)
    _warp_brd20_base(base_path)
    _write_brd20_clutter(base_path, agl_path, mask_path, final_path)
    _finish_raster(final_path)
    _write_grd_source(final_path)
    _write_mapinfo_class_profile(semantic_dir)
    _write_summary(semantic_dir, final_path)


def _write_vectors(output_dir: Path, semantic_dir: Path) -> None:
    dlm_path = output_dir / "basis_dlm" / "munich_pilot_basis_dlm.gml"
    lod2_paths = sorted((output_dir / "bdom").rglob("*.gml"))
    vegetation = semantic_dir / "munich_pilot_dlm_vegetation.geojson"
    buildings = semantic_dir / "munich_pilot_lod2_buildings.geojson"
    if not _is_complete(vegetation):
        write_geojson(vegetation, dlm_vegetation_features(dlm_path))
    if not _is_complete(buildings):
        write_geojson(buildings, lod2_building_features(lod2_paths))


def _is_complete(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def _terrain_paths(output_dir: Path) -> tuple[Path, Path]:
    utm32_dir = output_dir / "utm32"
    dgm_paths = sorted(utm32_dir.glob("*_dgm1_*_ellipse_pyramids.tif"))
    dom_paths = sorted(utm32_dir.glob("*_dom1_*_ellipse_pyramids.tif"))
    if not dgm_paths or not dom_paths:
        raise FileNotFoundError("Missing DGM/DOM Ellipse GeoTIFF exports in the pilot utm32 folder.")
    return dgm_paths[0], dom_paths[0]


def _warp_to_grid(source: Path, target: Path, resampling: str, dtype: str) -> None:
    min_x, min_y, max_x, max_y = PILOT_BOUNDS_25832
    _run_gdal([
        "gdalwarp.exe", "-overwrite", "-t_srs", "EPSG:32632", "-te",
        str(min_x), str(min_y), str(max_x), str(max_y), "-tr",
        str(RESOLUTION_M), str(RESOLUTION_M), "-r", resampling, "-ot", dtype,
        "-of", "GTiff", "-co", "COMPRESS=LZW", str(source), str(target),
    ])


def _create_mask(target: Path) -> None:
    target.unlink(missing_ok=True)
    min_x, min_y, max_x, max_y = PILOT_BOUNDS_25832
    width = int((max_x - min_x) / RESOLUTION_M)
    height = int((max_y - min_y) / RESOLUTION_M)
    _run_gdal([
        "gdal_create.exe", "-of", "GTiff", "-ot", "Byte", "-outsize",
        str(width), str(height), "-a_srs", "EPSG:32632", "-a_ullr",
        str(min_x), str(max_y), str(max_x), str(min_y), "-a_nodata", "0",
        str(target),
    ])


def _rasterize_vectors(semantic_dir: Path, mask_path: Path) -> None:
    vegetation = semantic_dir / "munich_pilot_dlm_vegetation.geojson"
    buildings = semantic_dir / "munich_pilot_lod2_buildings.geojson"
    _run_gdal(["gdal_rasterize.exe", "-a", "burn", str(vegetation), str(mask_path)])
    _run_gdal(["gdal_rasterize.exe", "-a", "burn", str(buildings), str(mask_path)])


def _write_agl_height(dgm_path: Path, dom_path: Path, mask_path: Path, output_dir: Path) -> Path:
    dgm = np.asarray(Image.open(dgm_path), dtype=np.float32)
    dom = np.asarray(Image.open(dom_path), dtype=np.float32)
    mask = np.asarray(Image.open(mask_path), dtype=np.uint8)
    target = output_dir / "munich_pilot_agl_height_2m.tif"
    Image.fromarray(agl_height_grid(dgm, dom, mask), mode="F").save(target)
    _finish_numeric_raster(target)
    _write_numeric_grd(target)
    _write_mapinfo_mrr(target)
    return target


def _warp_brd20_base(target: Path) -> None:
    if not BRD20_PATH.exists():
        raise FileNotFoundError(f"Missing BRD20 clutter base: {BRD20_PATH}")
    _warp_to_grid(BRD20_PATH, target, "near", "Byte")


def _write_brd20_clutter(base_path: Path, agl_path: Path, mask_path: Path, target: Path) -> None:
    base = np.asarray(Image.open(base_path), dtype=np.uint8)
    agl_height = np.asarray(Image.open(agl_path), dtype=np.float32)
    mask = np.asarray(Image.open(mask_path), dtype=np.uint8)
    Image.fromarray(brd20_clutter_grid(base, agl_height, mask), mode="L").save(target)


def _write_mapinfo_mrr(path: Path) -> None:
    target = path.with_suffix(".mrr")
    if target.exists() and target.stat().st_mtime >= path.stat().st_mtime:
        return
    temporary = target.with_name(target.stem + ".building.mrr")
    temporary.unlink(missing_ok=True)
    powershell = shutil.which("powershell.exe")
    converter = Path(__file__).with_name("convert_mapinfo_mrr.ps1")
    if not powershell or not converter.exists():
        raise FileNotFoundError("MapInfo MRR converter requires Windows PowerShell and scripts/convert_mapinfo_mrr.ps1")
    try:
        subprocess.run([powershell, "-NoProfile", "-File", str(converter), "-InputPath", str(path), "-OutputPath", str(temporary)], check=True)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def _finish_raster(path: Path) -> None:
    translated_path = path.with_name(path.stem + "_georef.tif")
    _translate_with_georef(path, translated_path)
    path.unlink()
    translated_path.rename(path)
    _run_gdal(["gdaladdo.exe", "-r", "mode", str(path), "2", "4", "8", "16"])
    _write_mapinfo_tab(_gdal_tool("gdalinfo.exe"), path, path.with_suffix(".TAB"), _environment(), require_utm32=True)


def _write_grd_source(path: Path) -> Path:
    grd_path = path.with_name(path.stem + "_source.grd")
    grd_path.unlink(missing_ok=True)
    _run_gdal(["gdal_translate.exe", "-of", "NWT_GRD", "-ot", "Float32", str(path), str(grd_path)])
    return grd_path


def _write_separate_grc(mask_grd: Path, output_dir: Path) -> None:
    targets = {
        "buildings": output_dir / "munich_pilot_buildings_2m.grc",
        "trees": output_dir / "munich_pilot_trees_2m.grc",
    }
    for layer, target in targets.items():
        _write_mapinfo_grc(mask_grd, target, layer)


def _write_mapinfo_grc(source: Path, target: Path, layer: str) -> None:
    if target.exists() and target.stat().st_mtime >= source.stat().st_mtime:
        return
    temporary = target.with_name(target.stem + ".converting.grc")
    temporary.unlink(missing_ok=True)
    powershell = shutil.which("powershell.exe")
    converter = Path(__file__).with_name("convert_mapinfo_grc.ps1")
    if not powershell or not converter.exists():
        raise FileNotFoundError("MapInfo GRC converter requires Windows PowerShell and scripts/convert_mapinfo_grc.ps1")
    try:
        subprocess.run(
            [powershell, "-NoProfile", "-File", str(converter), "-InputPath", str(source),
             "-OutputPath", str(temporary), "-Layer", layer],
            check=True,
        )
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def _write_numeric_grd(path: Path) -> None:
    grd_path = path.with_suffix(".grd")
    grd_path.unlink(missing_ok=True)
    _run_gdal(["gdal_translate.exe", "-of", "NWT_GRD", "-ot", "Float32", str(path), str(grd_path)])


def _finish_numeric_raster(path: Path) -> None:
    translated_path = path.with_name(path.stem + "_georef.tif")
    _translate_with_georef(path, translated_path)
    path.unlink()
    translated_path.rename(path)
    _run_gdal(["gdaladdo.exe", "-r", "average", str(path), "2", "4", "8", "16"])
    _write_mapinfo_tab(_gdal_tool("gdalinfo.exe"), path, path.with_suffix(".TAB"), _environment(), require_utm32=True)


def _translate_with_georef(source: Path, target: Path) -> None:
    min_x, min_y, max_x, max_y = PILOT_BOUNDS_25832
    _run_gdal([
        "gdal_translate.exe", "-of", "GTiff", "-a_srs", "EPSG:32632", "-a_ullr",
        str(min_x), str(max_y), str(max_x), str(min_y), "-co", "COMPRESS=LZW",
        "-co", "TILED=YES", str(source), str(target),
    ])


def _write_summary(semantic_dir: Path, final_path: Path) -> None:
    counts = _class_counts(final_path)
    rows = [{"code": code, "cells": cells, "square_m": cells * RESOLUTION_M * RESOLUTION_M} for code, cells in counts.items()]
    with (semantic_dir / "munich_pilot_brd_schema_counts.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["code", "cells", "square_m"])
        writer.writeheader()
        writer.writerows(rows)


def _write_mapinfo_class_profile(semantic_dir: Path) -> None:
    write_mapinfo_class_profile(semantic_dir / "munich_pilot_brd20_clutter.class")


def _class_counts(path: Path) -> dict[int, int]:
    values, counts = np.unique(np.asarray(Image.open(path), dtype=np.uint8), return_counts=True)
    return {int(value): int(count) for value, count in zip(values, counts, strict=True)}


def _run_gdal(args: list[str]) -> None:
    command = [str(_gdal_tool(args[0])), *args[1:]]
    subprocess.run(command, check=True, env=_environment())


def _gdal_tool(name: str) -> Path:
    path = GDAL_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing GDAL tool: {path}")
    return path


def _environment() -> dict[str, str]:
    return _gdal_environment(GDAL_DIR)


if __name__ == "__main__":
    main()
