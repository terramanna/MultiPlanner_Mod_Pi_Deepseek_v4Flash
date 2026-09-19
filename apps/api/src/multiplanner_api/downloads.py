from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from threading import Lock
from typing import Callable
import re
import warnings
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
import zipfile

import requests
from urllib3.exceptions import InsecureRequestWarning

from multiplanner_api.config import load_settings
from multiplanner_api.ellipse_exports import _export_for_ellipse, _export_grd
from multiplanner_api.semantic_grc_exports import export_semantic_grc
from multiplanner_api.models import (
    DownloadFailure,
    DownloadSubsetRequest,
    DownloadSubsetResponse,
    DownloadedFile,
    LocateSubsetRequest,
    LocateSubsetResponse,
)
from multiplanner_api.subsets import locate_subsets

# Provider hosts that are allowed for downloads.
# Each is a validated, known geodata provider. If a provider index
# ever returns a URL pointing elsewhere, the download is rejected.
_KNOWN_PROVIDER_HOSTS = frozenset({
    "www.opengeodata.nrw.de",
    "geocloud.landesvermessung.sachsen.de",
    "inspirehessen.de",
    "geodaten.bayern.de",
    "geoservices.bayern.de",
    "opengeodata.lgl-bw.de",
    "isk.geobasis-bb.de",
    "data.geobasis-bb.de",
    "geodaten.schleswig-holstein.de",
    "www.geodaten-mv.de",
    "gdi2.geo.bremen.de",
    "gdi.berlin.de",
    "geoportal.geoportal-th.de",
    "geoportal.saarland.de",
    "www.geodatenportal.sachsen-anhalt.de",
    "geobasis-rlp.de",
    "api.hamburg.de",
    "daten-hamburg.de",
    "archiv.transparenz.hamburg.de",
    "services-eu1.arcgis.com",
    "geodaten.sachsen.de",
})



    requests.exceptions.ConnectionError,
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.Timeout,
)
ProgressCallback = Callable[[str, str, str, int, int, bool], None]


def download_subset(
    request: DownloadSubsetRequest,
    *,
    on_progress: ProgressCallback | None = None,
) -> DownloadSubsetResponse:
    subset_response = locate_subsets(_locate_request(request))
    total_tiles = sum(len(result.tiles) for result in subset_response.results)
    settings = load_settings()
    selection_name = request.selection_name or _default_selection_name()
    output_dir = _resolve_output_dir(settings.cache_root, selection_name, settings.output_dir)
    downloaded_files, downloaded_by_dataset, failures, download_warnings = _download_located_files(
        subset_response,
        output_dir,
        group_by_provider=request.provider == "auto",
        default_provider=request.provider,
        on_progress=on_progress,
        total_tiles=total_tiles,
    )
    exports, export_warnings = _export_or_skip(request, downloaded_by_dataset, failures, output_dir, settings.ellipse_gdal_dir)
    return DownloadSubsetResponse(
        provider=request.provider,
        selection_name=selection_name,
        export_profile=request.export_profile,
        output_dir=str(output_dir),
        expected_file_count=total_tiles,
        file_count=len(downloaded_files),
        files=downloaded_files,
        failed_downloads=failures,
        exports=exports,
        warnings=[*getattr(subset_response, "warnings", []), *download_warnings, *export_warnings],
        total_estimated_source_bytes=getattr(subset_response, "total_estimated_source_bytes", 0),
        total_estimated_ellipse_bytes=getattr(subset_response, "total_estimated_ellipse_bytes", 0),
    )


def _locate_request(request: DownloadSubsetRequest) -> LocateSubsetRequest:
    return LocateSubsetRequest(
        provider=request.provider,
        datasets=request.datasets,
        geometry=request.geometry,
    )


def _resolve_output_dir(cache_root: str, selection_name: str, custom_output_dir: str = "") -> Path:
    if custom_output_dir:
        output_dir = Path(custom_output_dir) / _slugify(selection_name)
    else:
        output_dir = Path(cache_root) / "saved_subsets" / _slugify(selection_name)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir.resolve()


def _download_located_files(
    subset_response: LocateSubsetResponse,
    output_dir: Path,
    *,
    group_by_provider: bool,
    default_provider: str,
    on_progress: ProgressCallback | None = None,
    total_tiles: int = 0,
) -> tuple[list[DownloadedFile], dict[str, list[Path]], list[DownloadFailure], list[str]]:
    downloaded_files: list[DownloadedFile] = []
    downloaded_by_dataset: dict[str, list[Path]] = {}
    failures: list[DownloadFailure] = []
    warnings_list: list[str] = []
    subset_provider = getattr(subset_response, "provider", default_provider)
    tile_counter: list[int] = [0]
    for result in subset_response.results:
        provider = getattr(result, "provider", None) or subset_provider
        result_files, result_paths, result_failures, result_warnings = _download_result_files(
            result,
            output_dir,
            provider,
            group_by_provider,
            on_progress=on_progress,
            tile_counter=tile_counter,
            total_tiles=total_tiles,
        )
        downloaded_files.extend(result_files)
        failures.extend(result_failures)
        warnings_list.extend(result_warnings)
        for dataset, paths in result_paths.items():
            downloaded_by_dataset.setdefault(dataset, []).extend(paths)
    return downloaded_files, downloaded_by_dataset, failures, warnings_list


def _download_result_files(
    result: object,
    output_dir: Path,
    provider: str,
    group_by_provider: bool,
    *,
    on_progress: ProgressCallback | None = None,
    tile_counter: list[int] | None = None,
    total_tiles: int = 0,
) -> tuple[list[DownloadedFile], dict[str, list[Path]], list[DownloadFailure], list[str]]:
    downloaded_files: list[DownloadedFile] = []
    downloaded_by_dataset: dict[str, list[Path]] = {}
    failures: list[DownloadFailure] = []
    warnings_list: list[str] = []
    dataset_dir = _dataset_directory(output_dir, provider, result.dataset, group_by_provider)
    for tile in result.tiles:
        if not tile.primary_url:
            failures.append(_download_failure(provider, result.dataset, tile, "Missing source URL."))
            _notify_download_progress(on_progress, tile_counter, provider, result.dataset, tile.tile_id, total_tiles, False)
            continue

        # SSRF guard: only allow known geodata provider hosts.
        parsed = urlparse(tile.primary_url)
        if parsed.hostname not in _KNOWN_PROVIDER_HOSTS:
            failures.append(_download_failure(provider, result.dataset, tile, f"Blocked download from unknown host: {parsed.hostname}"))
            _notify_download_progress(on_progress, tile_counter, provider, result.dataset, tile.tile_id, total_tiles, False)
            continue
        target_path = dataset_dir / _target_filename(tile.primary_url, tile.tile_id)
        try:
            _download_file(tile.primary_url, target_path)
        except Exception as exc:
            warnings_list.append(f"{provider}/{result.dataset}/{tile.tile_id or 'unnamed-tile'} failed: {exc}")
            failures.append(_download_failure(provider, result.dataset, tile, str(exc)))
            _notify_download_progress(on_progress, tile_counter, provider, result.dataset, tile.tile_id, total_tiles, False)
            continue
        _notify_download_progress(on_progress, tile_counter, provider, result.dataset, tile.tile_id, total_tiles, True)
        downloaded_files.append(
            DownloadedFile(
                provider=provider,
                dataset=result.dataset,
                tile_id=tile.tile_id,
                source_url=tile.primary_url,
                saved_path=str(target_path.resolve()),
            )
        )
        expanded_paths = _expanded_download_paths(target_path, dataset_dir)
        warnings_list.extend(_expanded_source_warnings(provider, result.dataset, tile, target_path, expanded_paths))
        downloaded_by_dataset.setdefault(result.dataset, []).extend(expanded_paths)
    return downloaded_files, downloaded_by_dataset, failures, warnings_list


def _notify_download_progress(
    on_progress: ProgressCallback | None,
    tile_counter: list[int] | None,
    provider: str,
    dataset: str,
    tile_id: str | None,
    total_tiles: int,
    success: bool,
) -> None:
    if on_progress is None or tile_counter is None:
        return
    tile_counter[0] += 1
    on_progress(provider, dataset, tile_id or "", tile_counter[0], total_tiles, success)


def _download_failure(provider: str, dataset: str, tile: object, reason: str) -> DownloadFailure:
    return DownloadFailure(
        provider=provider,
        dataset=dataset,
        tile_id=getattr(tile, "tile_id", None),
        source_url=getattr(tile, "primary_url", None),
        reason=reason,
    )


def _dataset_directory(output_dir: Path, provider: str, dataset: str, group_by_provider: bool) -> Path:
    dataset_dir = output_dir / provider / dataset if group_by_provider else output_dir / dataset
    dataset_dir.mkdir(parents=True, exist_ok=True)
    return dataset_dir


def _export_subset(
    export_profile: str,
    downloaded_by_dataset: dict[str, list[Path]],
    output_dir: Path,
    ellipse_gdal_dir: str,
) -> tuple[list[str], list[str]]:
    if export_profile == "ellipse_mapinfo_tab":
        return _export_for_ellipse(downloaded_by_dataset, output_dir, ellipse_gdal_dir, build_pyramids=False)
    if export_profile == "ellipse_mapinfo_tab_pyramids":
        return _export_for_ellipse(downloaded_by_dataset, output_dir, ellipse_gdal_dir, build_pyramids=True)
    if export_profile == "ellipse_grd":
        return _export_grd(downloaded_by_dataset, output_dir, ellipse_gdal_dir)
    return [], []


def _export_or_skip(
    request: DownloadSubsetRequest,
    downloaded_by_dataset: dict[str, list[Path]],
    failures: list[DownloadFailure],
    output_dir: Path,
    ellipse_gdal_dir: str,
) -> tuple[list[str], list[str]]:
    if failures:
        return [], [f"Export skipped because {len(failures)} identified source file(s) failed to download."]
    if request.export_profile in {"ellipse_semantic_grc", "ellipse_semantic_grc_1m"}:
        if request.provider not in {"ldbv-by", "lvermgeo-sh"}:
            return [], ["Buildings + trees GRC export supports Bayern and Schleswig-Holstein selections only."]
        resolution_m = 1 if request.export_profile == "ellipse_semantic_grc_1m" else 2
        return _export_semantic_ellipse_bundle(
            request, downloaded_by_dataset, output_dir, ellipse_gdal_dir, resolution_m
        )
    return _export_subset(request.export_profile, downloaded_by_dataset, output_dir, ellipse_gdal_dir)


def _export_semantic_ellipse_bundle(
    request: DownloadSubsetRequest,
    downloaded_by_dataset: dict[str, list[Path]],
    output_dir: Path,
    ellipse_gdal_dir: str,
    resolution_m: int,
) -> tuple[list[str], list[str]]:
    terrain_sources = {name: downloaded_by_dataset.get(name, []) for name in ("dgm1", "dom1")}
    terrain_exports, terrain_warnings = _export_for_ellipse(
        terrain_sources, output_dir, ellipse_gdal_dir, build_pyramids=True
    )
    lod2_dataset = "bdom" if request.provider == "ldbv-by" else "lod2"
    semantic_exports, semantic_warnings = export_semantic_grc(
        provider=request.provider,
        geometry=request.geometry,
        lod2_paths=downloaded_by_dataset.get(lod2_dataset, []),
        dgm_paths=downloaded_by_dataset.get("dgm1", []),
        dom_paths=downloaded_by_dataset.get("dom1", []),
        output_dir=output_dir,
        ellipse_gdal_dir=ellipse_gdal_dir,
        resolution_m=resolution_m,
    )
    return [*terrain_exports, *semantic_exports], [*terrain_warnings, *semantic_warnings]


def _default_selection_name() -> str:
    return datetime.now(UTC).strftime("subset_%Y%m%dT%H%M%SZ")


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip())
    return cleaned.strip("-_") or _default_selection_name()


def _target_filename(url: str, tile_id: str | None) -> str:
    parsed = urlparse(url)
    query_file = parse_qs(parsed.query).get("file", [""])[0]
    source_name = Path(unquote(query_file or parsed.path)).name
    suffix = Path(source_name).suffix or ".tif"
    if tile_id:
        return f"{tile_id}{suffix}"
    return source_name or f"download{suffix}"


def _expanded_download_paths(path: Path, dest_dir: Path) -> list[Path]:
    extracted = _extract_supported_sources(path, dest_dir)
    return extracted or [path]


def _expanded_source_warnings(provider: str, dataset: str, tile: object, source_path: Path, expanded_paths: list[Path]) -> list[str]:
    expected_count = _expected_package_raster_count(provider, source_path, tile)
    if expected_count is None or len(expanded_paths) >= expected_count:
        return []
    tile_id = getattr(tile, "tile_id", None) or source_path.stem
    return [
        f"{provider}/{dataset}/{tile_id} package contains {len(expanded_paths)} of {expected_count} expected raster file(s); exported mosaic may have gaps."
    ]


def _expected_package_raster_count(provider: str, source_path: Path, tile: object) -> int | None:
    source_url = getattr(tile, "primary_url", "") or ""
    package_name = f"{source_path.name} {source_url}"
    if provider == "lgl-bw" and re.search(r"_2_bw\.zip\b", package_name, re.IGNORECASE):
        return 4
    return None


def _extract_supported_sources(zip_path: Path, dest_dir: Path) -> list[Path]:
    """Extract supported raster-like sources from *zip_path* into *dest_dir*.

    Priority order:
    1. GeoTIFF files (.tif/.tiff)
    2. ASCII XYZ files (.xyz)
    3. CSV files (kept as a last resort for XYZ-style products)
    4. GML files (for 3D building tiles / CityGML products)

    Returns an empty list if *zip_path* is not a ZIP or contains no supported
    sources.
    """
    if zip_path.suffix.lower() != ".zip":
        return []
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        for suffixes in ((".tif", ".tiff"), (".xyz",), (".csv",), (".gml",)):
            matches = [name for name in names if name.lower().endswith(suffixes)]
            if not matches:
                continue
            extracted_paths: list[Path] = []
            for name in matches:
                zf.extract(name, dest_dir)
                extracted_paths.append(dest_dir / name)
            return extracted_paths
    return []


@lru_cache(maxsize=2_048)
def _download_lock(target_path: str) -> Lock:
    return Lock()


def _download_file(url: str, target_path: Path) -> None:
    with _download_lock(str(target_path.resolve())):
        _download_file_locked(url, target_path)


def _download_file_locked(url: str, target_path: Path) -> None:
    if target_path.exists() and target_path.stat().st_size > 0:
        _strip_sh_portal_html_footer(url, target_path)
        return
    first_error: Exception | None = None
    for _attempt in range(2):
        try:
            _download_file_once(url, target_path)
            _strip_sh_portal_html_footer(url, target_path)
            return
        except _TRANSIENT_DOWNLOAD_ERRORS as exc:
            if first_error is None:
                first_error = exc
                continue
            raise RuntimeError(f"Download failed after retry for {url}: {exc}") from exc


def _strip_sh_portal_html_footer(url: str, target_path: Path) -> None:
    parsed = urlparse(url)
    source_name = parse_qs(parsed.query).get("file", [""])[0]
    is_sh_download = parsed.hostname == "geodaten.schleswig-holstein.de" and parsed.path.endswith("/massen.php")
    if not is_sh_download or Path(source_name).suffix.casefold() not in {".xml", ".xyz"}:
        return
    tail_size = min(target_path.stat().st_size, 16_384)
    with target_path.open("r+b") as handle:
        handle.seek(-tail_size, 2)
        tail = handle.read(tail_size)
        marker_index = tail.find(b"<!DOCTYPE html>")
        if marker_index < 0:
            return
        handle.seek(-tail_size + marker_index, 2)
        handle.truncate()


def _download_file_once(url: str, target_path: Path) -> None:
    try:
        _stream_download_file(url, target_path, verify=True)
    except requests.exceptions.SSLError:
        warnings.warn(
            f"SSL verification failed for {url}; retrying without certificate verification.",
            stacklevel=2,
        )
        _stream_download_file(url, target_path, verify=False)


def _stream_download_file(url: str, target_path: Path, *, verify: bool) -> None:
    partial_path = target_path.with_name(f"{target_path.name}.part")
    partial_bytes = partial_path.stat().st_size if partial_path.exists() else 0
    headers = {"Range": f"bytes={partial_bytes}-"} if partial_bytes else {}
    with warnings.catch_warnings():
        if not verify:
            warnings.simplefilter("ignore", InsecureRequestWarning)
        with requests.Session() as session:
            session.trust_env = False
            with session.get(url, headers=headers, stream=True, timeout=120, verify=verify) as response:
                response.raise_for_status()
                mode = "ab" if partial_bytes and response.status_code == 206 else "wb"
                with partial_path.open(mode) as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            handle.write(chunk)
                partial_path.replace(target_path)
