from __future__ import annotations

import math
import os
from pathlib import Path
import re
import subprocess
from threading import Lock

from pyproj import Transformer
from pyproj.datadir import get_data_dir

from multiplanner_api.cache_eviction import evict_lru
from multiplanner_api.config import load_settings
from multiplanner_api.downloads import _download_file, _expanded_download_paths, _target_filename
from multiplanner_api.http_client import get_with_ssl_fallback

# Providers that expose a direct elevation REST API for DGM probes.
# Value is (api_url, native_crs).  Only dgm1 is supported via these APIs.
_ELEVATION_API: dict[str, tuple[str, str]] = {
    "geobasis-bb": ("https://isk.geobasis-bb.de/elevation/latlon/point", "EPSG:25833"),
    "gdi-be":      ("https://isk.geobasis-bb.de/elevation/latlon/point", "EPSG:25833"),
}

# WGS84 bboxes (W, S, E, N) for providers in _ELEVATION_API — used by the auto
# probe to route DGM requests to the fast REST API before trying WCS tile download.
_ELEVATION_API_BBOX: dict[str, tuple[float, float, float, float]] = {
    "geobasis-bb": (11.26, 51.36, 14.76, 53.56),
    "gdi-be":      (13.09, 52.34, 13.76, 52.68),
}

# CRS for providers whose tiles are ASCII XYZ (no embedded CRS).
# gdal_translate assigns the CRS when converting to GeoTIFF.
_PROVIDER_XYZ_CRS: dict[str, str] = {
    "lgl-bw": "EPSG:25832",
    "lgv-hh": "EPSG:25832",
    "lginf-hb": "EPSG:25832",
    "gdi-be": "EPSG:25833",
}

# Providers whose WCS servers return GeoTIFFs without an embedded SRS.
# gdal_translate -a_srs is applied once after download to create a tagged copy.
_PROVIDER_WCS_MISSING_SRS: dict[str, str] = {
    "geobasis-bb": "EPSG:25833",
}

_SAMPLE_PATH_LOCKS: dict[Path, Lock] = {}
_SAMPLE_PATH_LOCKS_GUARD = Lock()

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
    dgm_probe = _probe_multi_dataset(result, request, "dgm1", "dgm_m", "dgm_error")
    dom_provider = request.provider
    if request.provider == "auto" and dgm_probe is not None:
        result.provider = dgm_probe.provider
        if not _provider_supports_probe_dataset(dgm_probe.provider, "dom1"):
            dom_provider = dgm_probe.provider
    _probe_multi_dataset(result, request, "dom1", "dom_m", "dom_error", provider=dom_provider)
    if result.dgm_m is not None and result.dom_m is not None:
        result.ndsm_m = max(result.dom_m - result.dgm_m, 0.0)
    return result


def _probe_multi_dataset(
    result: MultiProbeResponse,
    request: MultiProbeRequest,
    dataset: str,
    value_field: str,
    error_field: str,
    *,
    provider: str | None = None,
) -> PointProbeResponse | None:
    probe_provider = provider or request.provider
    if not _provider_supports_probe_dataset(probe_provider, dataset):
        setattr(result, error_field, _unsupported_probe_dataset_message(probe_provider, dataset))
        return None
    try:
        response = probe_point(
            PointProbeRequest(provider=probe_provider, dataset=dataset, lon=request.lon, lat=request.lat)
        )
        setattr(result, value_field, response.height_m)
        return response
    except Exception as exc:
        setattr(result, error_field, str(exc))
        return None


def _provider_supports_probe_dataset(provider: str, dataset: str) -> bool:
    if provider == "auto":
        return True
    from multiplanner_api.providers import provider_dataset_names
    return dataset in provider_dataset_names(provider)


def _unsupported_probe_dataset_message(provider: str, dataset: str) -> str:
    return f"{provider} does not support {dataset} point probing."


def probe_point(request: PointProbeRequest) -> PointProbeResponse:
    if request.dataset == "ndsm":
        return _probe_surface_height_delta(request)

    # Fast path: direct elevation REST API (BB/BE for DGM, named provider or auto)
    if request.dataset == "dgm1":
        api_entry = _ELEVATION_API.get(request.provider)
        if api_entry is None and request.provider == "auto":
            api_entry = _elevation_api_for_point(request.lon, request.lat)
        if api_entry is not None:
            api_url, crs = api_entry
            height_m = _probe_elevation_api(api_url, crs, request.lon, request.lat)
            return PointProbeResponse(
                provider=request.provider,
                dataset=request.dataset,
                lon=request.lon,
                lat=request.lat,
                height_m=height_m,
                tile_id="elevation-api",
                sampled_path=api_url,
            )

    # Auto: try each provider independently, return first success
    if request.provider == "auto":
        return _probe_point_auto(request)

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


def _probe_elevation_api(api_url: str, native_crs: str, lon: float, lat: float) -> float:
    """Query a direct elevation REST API (e.g. LGB Brandenburg) instead of downloading a tile."""
    transformer = Transformer.from_crs("EPSG:4326", native_crs, always_xy=True)
    x, y = transformer.transform(lon, lat)
    resp = get_with_ssl_fallback(api_url, params={"coordinates": f"{x:.3f},{y:.3f}"}, timeout=15)
    resp.raise_for_status()
    text = resp.text.strip()
    if not text:
        raise ValueError(f"Elevation API returned empty response for {lat:.6f}, {lon:.6f}.")
    return float(text)


def _elevation_api_for_point(lon: float, lat: float) -> tuple[str, str] | None:
    """Return (api_url, crs) for the first elevation-API provider whose bbox covers (lon, lat)."""
    for provider, (w, s, e, n) in _ELEVATION_API_BBOX.items():
        if w <= lon <= e and s <= lat <= n:
            return _ELEVATION_API[provider]
    return None


def _probe_point_auto(request: PointProbeRequest) -> PointProbeResponse:
    """Try every provider that supports the requested dataset; return first success."""
    from multiplanner_api.providers import SERVICE_PROVIDERS, provider_dataset_names
    errors: list[str] = []
    for provider in SERVICE_PROVIDERS:
        if request.dataset not in provider_dataset_names(provider):
            continue
        try:
            return probe_point(request.model_copy(update={"provider": provider}))
        except Exception as exc:
            errors.append(f"{provider}: {exc}")
    raise ValueError(
        f"No provider returned height at {request.lat:.6f}, {request.lon:.6f} "
        f"for {request.dataset}. Errors: {'; '.join(errors)}"
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
    with _sample_path_lock(target_path):
        if not target_path.exists():
            _download_file(tile.primary_url or "", target_path)
            settings = load_settings()
            evict_lru(Path(settings.cache_root) / "raster_tile_sources", settings.source_cache_max_bytes)
        paths = _expanded_download_paths(target_path, cache_dir)
    return _resolve_sample_path(paths, request.provider, lon=request.lon, lat=request.lat)


def _sample_path_lock(target_path: Path) -> Lock:
    with _SAMPLE_PATH_LOCKS_GUARD:
        return _SAMPLE_PATH_LOCKS.setdefault(target_path, Lock())


def _shared_source_cache_dir(provider: str, dataset: str) -> Path:
    cache_dir = Path(load_settings().cache_root) / "raster_tile_sources" / provider / dataset
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir.resolve()


def _resolve_sample_path(paths: list[Path], provider: str, *, lon: float | None = None, lat: float | None = None) -> Path:
    ordered_paths = _point_ordered_paths(paths, provider, lon=lon, lat=lat)
    for path in ordered_paths:
        if path.suffix.lower() in {".tif", ".tiff"}:
            missing_srs_crs = _PROVIDER_WCS_MISSING_SRS.get(provider)
            if missing_srs_crs:
                return _assign_srs_if_missing(path.resolve(), missing_srs_crs)
            return path.resolve()
    crs = _PROVIDER_XYZ_CRS.get(provider)
    if crs:
        for path in ordered_paths:
            if path.suffix.lower() == ".xyz":
                return _xyz_to_geotiff(path, crs).resolve()
    raise ValueError(f"Point probe: no usable GeoTIFF or known-CRS XYZ tile for {provider}.")


def _point_ordered_paths(paths: list[Path], provider: str, *, lon: float | None, lat: float | None) -> list[Path]:
    point_cell = _point_grid_cell(provider, lon, lat)
    if point_cell is None:
        return paths
    for index, path in enumerate(paths):
        if _path_grid_cell(path) == point_cell:
            return [path, *paths[:index], *paths[index + 1:]]
    return paths


def _point_grid_cell(provider: str, lon: float | None, lat: float | None) -> tuple[int, int] | None:
    crs = _PROVIDER_XYZ_CRS.get(provider) or _PROVIDER_WCS_MISSING_SRS.get(provider)
    if crs is None or lon is None or lat is None:
        return None
    x, y = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform(lon, lat)
    return math.floor(x / 1000), math.floor(y / 1000)


def _path_grid_cell(path: Path) -> tuple[int, int] | None:
    match = re.search(r"_32_(\d+)_(\d+)_", path.name)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _assign_srs_if_missing(tif_path: Path, crs: str) -> Path:
    """Return a CRS-tagged copy of tif_path (suffix _crs.tif) if the original lacks SRS."""
    tagged = tif_path.with_name(tif_path.stem + "_crs.tif")
    if tagged.exists():
        return tagged
    executable = _gdal_exe("gdal_translate")
    try:
        subprocess.run(
            [str(executable), "-a_srs", crs, str(tif_path), str(tagged)],
            check=True, capture_output=True, text=True, env=_gdal_env(),
        )
    except subprocess.CalledProcessError as exc:
        msg = exc.stderr.strip() or f"exit {exc.returncode}"
        raise ValueError(f"gdal_translate SRS assignment failed for {tif_path.name}: {msg}") from None
    return tagged


def _xyz_to_geotiff(xyz_path: Path, crs: str) -> Path:
    tif_path = xyz_path.with_suffix(".tif")
    if tif_path.exists():
        return tif_path
    executable = _gdal_exe("gdal_translate")
    try:
        subprocess.run(
            [str(executable), "-of", "GTiff", "-a_srs", crs, str(xyz_path), str(tif_path)],
            check=True,
            capture_output=True,
            text=True,
            env=_gdal_env(),
        )
    except subprocess.CalledProcessError as exc:
        msg = exc.stderr.strip() or f"exit {exc.returncode}"
        raise ValueError(f"gdal_translate failed for {xyz_path.name}: {msg}") from None
    return tif_path


def _sample_height(sample_path: Path, lon: float, lat: float) -> float:
    _assert_valid_geotiff(sample_path)
    executable = _gdal_exe("gdallocationinfo")
    try:
        result = subprocess.run(
            [str(executable), "-wgs84", "-valonly", str(sample_path), str(lon), str(lat)],
            check=True,
            capture_output=True,
            text=True,
            env=_gdal_env(),
        )
    except subprocess.CalledProcessError as exc:
        msg = exc.stderr.strip() or f"exit {exc.returncode}"
        raise ValueError(f"gdallocationinfo failed for {sample_path.name}: {msg}") from None
    value = result.stdout.strip()
    if not value:
        raise ValueError(f"No data value at {lat:.6f}, {lon:.6f} in {sample_path.name}.")
    return float(value)


def _assert_valid_geotiff(path: Path) -> None:
    """Raise ValueError if the file looks like an XML error response rather than a GeoTIFF."""
    try:
        with path.open("rb") as fh:
            header = fh.read(512)
    except OSError:
        return
    stripped = header.lstrip()
    if stripped.startswith(b"<?xml") or stripped.startswith(b"<"):
        snippet = header.decode("utf-8", errors="replace")[:200].replace("\n", " ")
        raise ValueError(f"WCS/server returned XML error instead of raster data: {snippet}")


def _prepare_preview_path(sample_path: Path) -> Path:
    preview_path = sample_path.with_suffix(".png")
    if preview_path.exists():
        return preview_path
    executable = _gdal_exe("gdal_translate")
    try:
        subprocess.run(
            [str(executable), "-of", "PNG", "-ot", "Byte", "-scale", str(sample_path), str(preview_path)],
            check=True,
            capture_output=True,
            text=True,
            env=_gdal_env(),
        )
    except subprocess.CalledProcessError as exc:
        msg = exc.stderr.strip() or f"exit {exc.returncode}"
        raise ValueError(f"gdal_translate preview failed for {sample_path.name}: {msg}") from None
    return preview_path


def _tile_bounds_wgs84(sample_path: Path) -> tuple[float, float, float, float]:
    executable = _gdal_exe("gdalinfo")
    result = subprocess.run(
        [str(executable), "-json", str(sample_path)],
        check=True,
        capture_output=True,
        text=True,
        env=_gdal_env(),
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


def _gdal_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PROJ_LIB", get_data_dir())
    return env
