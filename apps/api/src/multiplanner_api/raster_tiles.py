from __future__ import annotations

from hashlib import sha1
from math import atan, degrees, pi, sinh
import os
from pathlib import Path
import subprocess
import sys
import zlib
import struct

import numpy as np
from pyproj.datadir import get_data_dir

from multiplanner_api.cache_eviction import evict_lru
from multiplanner_api.config import load_settings
from multiplanner_api.downloads import _download_file, _expanded_download_paths, _target_filename
from multiplanner_api.models import BboxGeometryInput, LocateSubsetRequest, TileSummary
from multiplanner_api.subsets import locate_subsets

WEB_MERCATOR_WORLD = 20037508.342789244
SUPPORTED_DATASETS = frozenset({"dgm1", "dom1", "ndsm"})
TILE_STYLE_VERSION = "v2"
NDSM_COLOR_RELIEF_FILE = Path(__file__).with_name("ndsm-color-relief.txt")
WEB_MERCATOR_WKT = (
    'PROJCS["WGS 84 / Pseudo-Mercator",'
    'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],'
    'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]],'
    'PROJECTION["Mercator_1SP"],PARAMETER["central_meridian",0],'
    'PARAMETER["scale_factor",1],PARAMETER["false_easting",0],'
    'PARAMETER["false_northing",0],UNIT["metre",1],AXIS["X",EAST],AXIS["Y",NORTH]]'
)


def render_cached_tile(provider: str, dataset: str, z: int, x: int, y: int) -> Path:
    _validate_request(provider, dataset, z, x, y)
    target_path = _tile_cache_path(provider, dataset, z, x, y)
    if target_path.exists():
        return target_path
    if dataset == "ndsm":
        _render_ndsm_tile(provider, z, x, y, target_path)
    else:
        source_paths = _source_paths(provider, dataset, z, x, y)
        if not source_paths:
            raise ValueError(f"No {dataset} coverage for tile {z}/{x}/{y}.")
        _render_tile_png(source_paths, dataset, z, x, y, target_path)
    _evict_tile_cache()
    return target_path


def _validate_request(provider: str, dataset: str, z: int, x: int, y: int) -> None:
    if provider != "geobasis-nrw":
        raise ValueError(f"Unsupported tile provider: {provider}")
    if dataset not in SUPPORTED_DATASETS:
        raise ValueError(f"Unsupported raster tile dataset: {dataset}")
    if z < 0 or x < 0 or y < 0:
        raise ValueError("Tile coordinates must be non-negative.")


def _tile_cache_path(provider: str, dataset: str, z: int, x: int, y: int) -> Path:
    path = Path(load_settings().cache_root) / "raster_tiles" / TILE_STYLE_VERSION / provider / dataset / str(z) / str(x) / f"{y}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _source_paths(provider: str, dataset: str, z: int, x: int, y: int) -> list[Path]:
    west, south, east, north = _tile_bounds_wgs84(z, x, y)
    response = locate_subsets(
        LocateSubsetRequest(
            provider=provider,
            datasets=[dataset],
            geometry=BboxGeometryInput(kind="bbox", west=west, south=south, east=east, north=north),
        )
    )
    return [path for result in response.results for tile in result.tiles for path in _download_tile_sources(provider, dataset, tile)]


def _download_tile_sources(provider: str, dataset: str, tile: TileSummary) -> list[Path]:
    cache_dir = Path(load_settings().cache_root) / "raster_tile_sources" / provider / dataset
    cache_dir.mkdir(parents=True, exist_ok=True)
    target_path = cache_dir / _target_filename(tile.primary_url or "", tile.tile_id)
    if not target_path.exists():
        _download_file(tile.primary_url or "", target_path)
        _evict_source_cache()
    return [path.resolve() for path in _expanded_download_paths(target_path, cache_dir) if path.suffix.lower() in {".tif", ".tiff"}]


def _evict_source_cache() -> None:
    s = load_settings()
    evict_lru(Path(s.cache_root) / "raster_tile_sources", s.source_cache_max_bytes)


def _evict_tile_cache() -> None:
    s = load_settings()
    evict_lru(Path(s.cache_root) / "raster_tiles", s.tile_cache_max_bytes)


def _render_tile_png(source_paths: list[Path], dataset: str, z: int, x: int, y: int, target_path: Path) -> None:
    key = sha1("|".join(str(path) for path in sorted(source_paths)).encode("utf-8")).hexdigest()[:16]
    vrt_path = target_path.with_name(f"{target_path.stem}-{key}.vrt")
    warped_path = target_path.with_name(f"{target_path.stem}-{key}-warp.tif")
    _gdal_run("gdalbuildvrt.exe", [str(vrt_path), *[str(path) for path in source_paths]])
    _warp_to_tile(vrt_path, warped_path, z, x, y)
    _render_dataset_png(warped_path, target_path, dataset)


def _warp_to_tile(vrt_path: Path, warped_path: Path, z: int, x: int, y: int) -> None:
    west, south, east, north = _tile_bounds_mercator(z, x, y)
    args = [
        "-overwrite",
        "-t_srs", WEB_MERCATOR_WKT,
        "-te", str(west), str(south), str(east), str(north),
        "-ts", "256", "256",
        "-r", "bilinear",
        "-dstalpha",
        str(vrt_path),
        str(warped_path),
    ]
    _gdal_run("gdalwarp.exe", args)


def _render_dataset_png(warped_path: Path, target_path: Path, dataset: str) -> None:
    if dataset == "dgm1":
        _render_hillshade_png(warped_path, target_path)
        return
    _render_grayscale_png(warped_path, target_path)


def _render_ndsm_tile(provider: str, z: int, x: int, y: int, target_path: Path) -> None:
    dgm_paths = _source_paths(provider, "dgm1", z, x, y)
    dom_paths = _source_paths(provider, "dom1", z, x, y)
    if not dgm_paths or not dom_paths:
        raise ValueError(f"No ndsm coverage for tile {z}/{x}/{y}.")
    key = _source_key(dgm_paths + dom_paths)
    dgm_vrt_path = target_path.with_name(f"{target_path.stem}-{key}-dgm.vrt")
    dom_vrt_path = target_path.with_name(f"{target_path.stem}-{key}-dom.vrt")
    dgm_warped_path = target_path.with_name(f"{target_path.stem}-{key}-dgm-warp.tif")
    dom_warped_path = target_path.with_name(f"{target_path.stem}-{key}-dom-warp.tif")
    diff_path = target_path.with_name(f"{target_path.stem}-{key}-ndsm.tif")
    _gdal_run("gdalbuildvrt.exe", [str(dgm_vrt_path), *[str(path) for path in dgm_paths]])
    _gdal_run("gdalbuildvrt.exe", [str(dom_vrt_path), *[str(path) for path in dom_paths]])
    _warp_to_tile(dgm_vrt_path, dgm_warped_path, z, x, y)
    _warp_to_tile(dom_vrt_path, dom_warped_path, z, x, y)
    _subtract_surface_model(dom_warped_path, dgm_warped_path, diff_path)
    _render_ndsm_png(diff_path, target_path)


def _source_key(source_paths: list[Path]) -> str:
    return sha1("|".join(str(path) for path in sorted(source_paths)).encode("utf-8")).hexdigest()[:16]


def _render_hillshade_png(warped_path: Path, target_path: Path) -> None:
    hillshade_path = target_path.with_name(f"{target_path.stem}-hillshade.tif")
    _gdal_run(
        "gdaldem.exe",
        ["hillshade", str(warped_path), str(hillshade_path), "-z", "2.5", "-multidirectional", "-compute_edges"],
    )
    _translate_png(hillshade_path, target_path, scale=False)


def _render_grayscale_png(warped_path: Path, target_path: Path) -> None:
    _translate_png(warped_path, target_path, scale=True)


def _subtract_surface_model(dom_path: Path, dgm_path: Path, diff_path: Path) -> None:
    dom_band = _read_warp_band(dom_path, band=1, dtype="Float32")
    dgm_band = _read_warp_band(dgm_path, band=1, dtype="Float32")
    dom_alpha = _read_warp_band(dom_path, band=2, dtype="Byte")
    dgm_alpha = _read_warp_band(dgm_path, band=2, dtype="Byte")
    diff = np.maximum(dom_band - dgm_band, 0.0)
    alpha = np.minimum(dom_alpha, dgm_alpha)
    _write_ndsm_png(diff_path.with_suffix(".png"), diff, alpha)


def _render_ndsm_png(diff_path: Path, target_path: Path) -> None:
    png_path = diff_path.with_suffix(".png")
    if not png_path.exists():
        raise ValueError("nDSM render did not produce a PNG tile.")
    png_path.replace(target_path)


def _translate_png(source_path: Path, target_path: Path, *, scale: bool = True) -> None:
    args = ["-of", "PNG", "-ot", "Byte"]
    if scale:
        args.append("-scale")
    args.extend([str(source_path), str(target_path)])
    _gdal_run("gdal_translate.exe", args)


def _gdal_run(executable_name: str, args: list[str]) -> None:
    executable = Path(load_settings().ellipse_gdal_dir) / executable_name
    if not executable.exists():
        raise ValueError(f"{executable_name} not found in {executable.parent}.")
    subprocess.run([str(executable), *args], check=True, capture_output=True, text=True, env=_gdal_env())


def _gdal_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PROJ_LIB", get_data_dir())
    return env


def _read_warp_band(source_path: Path, *, band: int, dtype: str) -> np.ndarray:
    raw_path = source_path.with_name(f"{source_path.stem}-band{band}.bin")
    _gdal_run(
        "gdal_translate.exe",
        ["-b", str(band), "-of", "ENVI", "-ot", dtype, str(source_path), str(raw_path)],
    )
    np_dtype = np.float32 if dtype == "Float32" else np.uint8
    return np.fromfile(raw_path, dtype=np_dtype).reshape((256, 256))


def _write_ndsm_png(target_path: Path, values: np.ndarray, alpha: np.ndarray) -> None:
    rgba = np.zeros((256, 256, 4), dtype=np.uint8)
    rgba[..., :3] = _ndsm_rgb(values)
    rgba[..., 3] = np.where(values > 0.5, alpha, 0).astype(np.uint8)
    _write_png_rgba(target_path, rgba)


def _ndsm_rgb(values: np.ndarray) -> np.ndarray:
    stops = _ndsm_stops()
    rgb = np.zeros(values.shape + (3,), dtype=np.uint8)
    for (start_value, start_rgb), (end_value, end_rgb) in zip(stops, stops[1:]):
        mask = (values >= start_value) & (values < end_value)
        if not np.any(mask):
            continue
        ratio = (values[mask] - start_value) / (end_value - start_value)
        rgb[mask] = np.round(start_rgb + (end_rgb - start_rgb) * ratio[:, None]).astype(np.uint8)
    rgb[values >= stops[-1][0]] = stops[-1][1]
    return rgb


def _ndsm_stops() -> list[tuple[float, np.ndarray]]:
    stops = []
    for line in NDSM_COLOR_RELIEF_FILE.read_text(encoding="ascii").splitlines():
        if not line.strip():
            continue
        height, red, green, blue, _alpha = line.split()
        if float(height) < 0:
            continue
        stops.append((float(height), np.array([int(red), int(green), int(blue)], dtype=np.float32)))
    return stops


def _write_png_rgba(target_path: Path, rgba: np.ndarray) -> None:
    rows = b"".join(b"\x00" + rgba[index].tobytes() for index in range(rgba.shape[0]))
    payload = _png_chunk(b"IHDR", struct.pack(">IIBBBBB", rgba.shape[1], rgba.shape[0], 8, 6, 0, 0, 0))
    payload += _png_chunk(b"IDAT", zlib.compress(rows, level=6))
    payload += _png_chunk(b"IEND", b"")
    target_path.write_bytes(b"\x89PNG\r\n\x1a\n" + payload)


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)


def _tile_bounds_mercator(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    tile_span = (2 * WEB_MERCATOR_WORLD) / (2**z)
    west = -WEB_MERCATOR_WORLD + x * tile_span
    east = west + tile_span
    north = WEB_MERCATOR_WORLD - y * tile_span
    south = north - tile_span
    return west, south, east, north


def _tile_bounds_wgs84(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    west = _tile_lon(x, z)
    east = _tile_lon(x + 1, z)
    north = _tile_lat(y, z)
    south = _tile_lat(y + 1, z)
    return west, south, east, north


def _tile_lon(x: int, z: int) -> float:
    return x / (2**z) * 360.0 - 180.0


def _tile_lat(y: int, z: int) -> float:
    return degrees(atan(sinh(pi * (1 - 2 * y / (2**z)))))
