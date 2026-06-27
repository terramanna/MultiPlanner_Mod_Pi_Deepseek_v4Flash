from __future__ import annotations

from pathlib import Path
import re
import subprocess

from pyproj import Transformer

from multiplanner_api.config import load_settings
from multiplanner_api.downloads import _download_file, _expanded_download_paths, _target_filename
from multiplanner_api.models import (
    LocateSubsetRequest,
    PointGeometryInput,
    PointProbeRequest,
    PointProbeResponse,
    TilePreviewRequest,
    TilePreviewResponse,
    TileSummary,
)
from multiplanner_api.subsets import locate_subsets

UTM32_TO_WGS84 = Transformer.from_crs("EPSG:25832", "EPSG:4326", always_xy=True)
WGS84_TO_UTM32 = Transformer.from_crs("EPSG:4326", "EPSG:25832", always_xy=True)
NRW_TILE_PATTERN = re.compile(r"_(?P<x>\d+)_(?P<y>\d+)_1_", re.IGNORECASE)


def probe_point(request: PointProbeRequest) -> PointProbeResponse:
    tile = _locate_point_tile(request)
    sample_path = _prepare_sample_path(request, tile)
    height_m = _sample_height(sample_path, request.lon, request.lat)
    return PointProbeResponse(
        provider=request.provider,
        dataset=request.dataset,
        lon=request.lon,
        lat=request.lat,
        height_m=height_m,
        tile_id=tile.tile_id,
        sampled_path=str(sample_path),
    )


def preview_tile(request: TilePreviewRequest) -> TilePreviewResponse:
    tile = _locate_point_tile(request)
    sample_path = _prepare_sample_path(request, tile)
    image_path = _prepare_preview_path(sample_path)
    west, south, east, north = _tile_bounds_wgs84(tile.tile_id)
    return TilePreviewResponse(
        provider=request.provider,
        dataset=request.dataset,
        tile_id=tile.tile_id,
        image_path=str(image_path),
        west=west,
        south=south,
        east=east,
        north=north,
    )


def _locate_point_tile(request: PointProbeRequest) -> TileSummary:
    response = locate_subsets(
        LocateSubsetRequest(
            provider=request.provider,
            datasets=[request.dataset],
            geometry=PointGeometryInput(kind="point", lon=request.lon, lat=request.lat),
        )
    )
    for result in response.results:
        if result.dataset != request.dataset:
            continue
        for tile in result.tiles:
            if tile.primary_url:
                return tile
    raise ValueError(f"No {request.dataset} tile covers {request.lat:.6f}, {request.lon:.6f}.")


def _prepare_sample_path(request: PointProbeRequest, tile: TileSummary) -> Path:
    cache_dir = _probe_cache_dir(request.provider, request.dataset)
    target_path = cache_dir / _target_filename(tile.primary_url or "", tile.tile_id)
    if not target_path.exists():
        _download_file(tile.primary_url or "", target_path)
    return _sample_source_path(_expanded_download_paths(target_path, cache_dir))


def _probe_cache_dir(provider: str, dataset: str) -> Path:
    cache_dir = Path(load_settings().cache_root) / "point_probe" / provider / dataset
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir.resolve()


def _sample_source_path(paths: list[Path]) -> Path:
    for path in paths:
        if path.suffix.lower() in {".tif", ".tiff"}:
            return path.resolve()
    raise ValueError("Point probe currently supports GeoTIFF source tiles only.")


def _sample_height(sample_path: Path, lon: float, lat: float) -> float:
    executable = Path(load_settings().ellipse_gdal_dir) / "gdallocationinfo.exe"
    if not executable.exists():
        raise ValueError(f"gdallocationinfo.exe not found in {executable.parent}.")
    easting, northing = WGS84_TO_UTM32.transform(lon, lat)
    result = subprocess.run(
        [str(executable), "-valonly", "-geoloc", str(sample_path), str(easting), str(northing)],
        check=True,
        capture_output=True,
        text=True,
    )
    return _parse_height(result.stdout)


def _parse_height(stdout: str) -> float:
    values = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not values:
        raise ValueError("No elevation value returned for that point.")
    try:
        return float(values[0].split()[0])
    except ValueError as exc:
        raise ValueError(f"Could not parse elevation value: {values[0]}") from exc


def _prepare_preview_path(sample_path: Path) -> Path:
    preview_path = sample_path.with_suffix(".png")
    if preview_path.exists():
        return preview_path
    executable = Path(load_settings().ellipse_gdal_dir) / "gdal_translate.exe"
    if not executable.exists():
        raise ValueError(f"gdal_translate.exe not found in {executable.parent}.")
    subprocess.run(
        [str(executable), "-of", "PNG", "-ot", "Byte", "-scale", str(sample_path), str(preview_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return preview_path


def _tile_bounds_wgs84(tile_id: str | None) -> tuple[float, float, float, float]:
    match = NRW_TILE_PATTERN.search(tile_id or "")
    if not match:
        raise ValueError(f"Could not derive NRW tile bounds from {tile_id!r}.")
    west_m = int(match["x"]) * 1000
    south_m = int(match["y"]) * 1000
    east_m = west_m + 1000
    north_m = south_m + 1000
    west, south = UTM32_TO_WGS84.transform(west_m, south_m)
    east, north = UTM32_TO_WGS84.transform(east_m, north_m)
    return west, south, east, north
