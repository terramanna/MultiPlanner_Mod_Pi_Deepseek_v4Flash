from __future__ import annotations

from pathlib import Path
import subprocess

from multiplanner_api.config import load_settings
from multiplanner_api.downloads import _download_file, _expanded_download_paths, _target_filename
from multiplanner_api.models import (
    LocateSubsetRequest,
    MultiProbeRequest,
    MultiProbeResponse,
    PointGeometryInput,
    PointProbeRequest,
    PointProbeResponse,
    TilePreviewRequest,
    TilePreviewResponse,
    TileSummary,
)
from multiplanner_api.subsets import locate_subsets


def probe_point_multi(request: MultiProbeRequest) -> MultiProbeResponse:
    result = MultiProbeResponse(provider=request.provider, lon=request.lon, lat=request.lat)
    for dataset, dgm_field, err_field in [
        ("dgm1", "dgm_m", "dgm_error"),
        ("dom1", "dom_m", "dom_error"),
    ]:
        try:
            r = probe_point(PointProbeRequest(provider=request.provider, dataset=dataset, lon=request.lon, lat=request.lat))
            setattr(result, dgm_field, r.height_m)
        except Exception as exc:
            setattr(result, err_field, str(exc))
    if result.dgm_m is not None and result.dom_m is not None:
        result.ndsm_m = max(result.dom_m - result.dgm_m, 0.0)
    return result


def probe_point(request: PointProbeRequest) -> PointProbeResponse:
    if request.dataset == "ndsm":
        return _probe_surface_height_delta(request)
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


def _probe_surface_height_delta(request: PointProbeRequest) -> PointProbeResponse:
    dom_request = request.model_copy(update={"dataset": "dom1"})
    dgm_request = request.model_copy(update={"dataset": "dgm1"})
    dom_probe = probe_point(dom_request)
    dgm_probe = probe_point(dgm_request)
    return PointProbeResponse(
        provider=request.provider,
        dataset="ndsm",
        lon=request.lon,
        lat=request.lat,
        height_m=max(dom_probe.height_m - dgm_probe.height_m, 0.0),
        tile_id=dom_probe.tile_id,
        sampled_path=f"{dom_probe.sampled_path} - {dgm_probe.sampled_path}",
    )


def preview_tile(request: TilePreviewRequest) -> TilePreviewResponse:
    tile = _locate_point_tile(request)
    sample_path = _prepare_sample_path(request, tile)
    image_path = _prepare_preview_path(sample_path)
    west, south, east, north = _tile_bounds_wgs84(sample_path)
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
    raise ValueError(f"No downloadable {request.dataset} tile covers {request.lat:.6f}, {request.lon:.6f}.")


def _prepare_sample_path(request: PointProbeRequest, tile: TileSummary) -> Path:
    cache_dir = _shared_source_cache_dir(request.provider, request.dataset)
    target_path = cache_dir / _target_filename(tile.primary_url or "", tile.tile_id)
    if not target_path.exists():
        _download_file(tile.primary_url or "", target_path)
    return _sample_source_path(_expanded_download_paths(target_path, cache_dir))


def _shared_source_cache_dir(provider: str, dataset: str) -> Path:
    cache_dir = Path(load_settings().cache_root) / "raster_tile_sources" / provider / dataset
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir.resolve()


def _sample_source_path(paths: list[Path]) -> Path:
    for path in paths:
        if path.suffix.lower() in {".tif", ".tiff"}:
            return path.resolve()
    raise ValueError("Point probe currently supports GeoTIFF source tiles only.")


def _sample_height(sample_path: Path, lon: float, lat: float) -> float:
    executable = _gdal_exe("gdallocationinfo")
    result = subprocess.run(
        [str(executable), "-wgs84", "-valonly", str(sample_path), str(lon), str(lat)],
        check=True,
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip()
    if not value:
        raise ValueError(f"No data value at {lat:.6f}, {lon:.6f} in {sample_path.name}.")
    return float(value)


def _prepare_preview_path(sample_path: Path) -> Path:
    preview_path = sample_path.with_suffix(".png")
    if preview_path.exists():
        return preview_path
    executable = _gdal_exe("gdal_translate")
    subprocess.run(
        [str(executable), "-of", "PNG", "-ot", "Byte", "-scale", str(sample_path), str(preview_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return preview_path


def _tile_bounds_wgs84(sample_path: Path) -> tuple[float, float, float, float]:
    executable = _gdal_exe("gdalinfo")
    result = subprocess.run(
        [str(executable), "-json", str(sample_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    import json
    info = json.loads(result.stdout)
    coords = info["wgs84Extent"]["coordinates"][0]
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return min(lons), min(lats), max(lons), max(lats)


def _gdal_exe(name: str) -> Path:
    executable = Path(load_settings().ellipse_gdal_dir) / f"{name}.exe"
    if not executable.exists():
        raise ValueError(f"{name}.exe not found in {executable.parent}.")
    return executable
