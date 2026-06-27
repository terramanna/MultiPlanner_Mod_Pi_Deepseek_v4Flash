from __future__ import annotations

from hashlib import sha1
from math import atan, degrees, pi, sinh
import os
from pathlib import Path
import subprocess

from pyproj.datadir import get_data_dir

from multiplanner_api.config import load_settings
from multiplanner_api.downloads import _download_file, _expanded_download_paths, _target_filename
from multiplanner_api.models import BboxGeometryInput, LocateSubsetRequest, TileSummary
from multiplanner_api.subsets import locate_subsets

WEB_MERCATOR_WORLD = 20037508.342789244
SUPPORTED_DATASETS = frozenset({"dgm1", "dom1"})
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
    source_paths = _source_paths(provider, dataset, z, x, y)
    if not source_paths:
        raise ValueError(f"No {dataset} coverage for tile {z}/{x}/{y}.")
    _render_tile_png(source_paths, dataset, z, x, y, target_path)
    return target_path


def _validate_request(provider: str, dataset: str, z: int, x: int, y: int) -> None:
    if provider != "geobasis-nrw":
        raise ValueError(f"Unsupported tile provider: {provider}")
    if dataset not in SUPPORTED_DATASETS:
        raise ValueError(f"Unsupported raster tile dataset: {dataset}")
    if z < 0 or x < 0 or y < 0:
        raise ValueError("Tile coordinates must be non-negative.")


def _tile_cache_path(provider: str, dataset: str, z: int, x: int, y: int) -> Path:
    path = Path(load_settings().cache_root) / "raster_tiles" / provider / dataset / str(z) / str(x) / f"{y}.png"
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
    return [path.resolve() for path in _expanded_download_paths(target_path, cache_dir) if path.suffix.lower() in {".tif", ".tiff"}]


def _render_tile_png(source_paths: list[Path], dataset: str, z: int, x: int, y: int, target_path: Path) -> None:
    key = sha1("|".join(str(path) for path in sorted(source_paths)).encode("utf-8")).hexdigest()[:16]
    vrt_path = target_path.with_name(f"{target_path.stem}-{key}.vrt")
    warped_path = target_path.with_name(f"{target_path.stem}-{key}-warp.tif")
    _gdal_run("gdalbuildvrt.exe", [str(vrt_path), *[str(path) for path in source_paths]])
    _warp_to_tile(vrt_path, warped_path, z, x, y)
    if dataset == "dgm1":
        _render_hillshade_png(warped_path, target_path)
    else:
        _translate_png(warped_path, target_path)


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


def _render_hillshade_png(warped_path: Path, target_path: Path) -> None:
    hillshade_path = target_path.with_name(f"{target_path.stem}-hillshade.tif")
    _gdal_run("gdaldem.exe", ["hillshade", str(warped_path), str(hillshade_path), "-compute_edges"])
    _translate_png(hillshade_path, target_path, scale=False)


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
    env = os.environ.copy()
    env.setdefault("PROJ_LIB", get_data_dir())
    subprocess.run([str(executable), *args], check=True, capture_output=True, text=True, env=env)


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
