from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable
import json
import os
import re
import struct
import subprocess
import warnings
from pathlib import Path
import zipfile

import requests
from urllib3.exceptions import InsecureRequestWarning

from multiplanner_api.config import load_settings
from multiplanner_api.models import (
    DownloadSubsetRequest,
    DownloadSubsetResponse,
    DownloadedFile,
    LocateSubsetRequest,
    LocateSubsetResponse,
)
from multiplanner_api.subsets import locate_subsets

WGS84_UTM32 = "EPSG:32632"
MAPINFO_WGS84_UTM32 = '  CoordSys Earth Projection 8, 104, "m", 9, 0, 0.9996, 500000, 0'
ELEVATION_DATASETS = frozenset({"dgm1", "dom1"})
ORTHO_DATASETS = frozenset({"dop20"})
GRD_DRIVER = "NWT_GRD"


def download_subset(
    request: DownloadSubsetRequest,
    *,
    on_progress: Callable[[str, int, int], None] | None = None,
) -> DownloadSubsetResponse:
    subset_response = locate_subsets(_locate_request(request))
    total_tiles = sum(len(result.tiles) for result in subset_response.results)
    settings = load_settings()
    selection_name = request.selection_name or _default_selection_name()
    output_dir = _resolve_output_dir(settings.cache_root, selection_name, settings.output_dir)
    downloaded_files, downloaded_by_dataset, download_warnings = _download_located_files(
        subset_response,
        output_dir,
        group_by_provider=request.provider == "auto",
        default_provider=request.provider,
        on_progress=on_progress,
        total_tiles=total_tiles,
    )
    exports, export_warnings = _export_subset(
        request.export_profile,
        downloaded_by_dataset,
        output_dir,
        settings.ellipse_gdal_dir,
    )
    return DownloadSubsetResponse(
        provider=request.provider,
        selection_name=selection_name,
        export_profile=request.export_profile,
        output_dir=str(output_dir),
        file_count=len(downloaded_files),
        files=downloaded_files,
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
    on_progress: Callable[[str, int, int], None] | None = None,
    total_tiles: int = 0,
) -> tuple[list[DownloadedFile], dict[str, list[Path]], list[str]]:
    downloaded_files: list[DownloadedFile] = []
    downloaded_by_dataset: dict[str, list[Path]] = {}
    warnings_list: list[str] = []
    subset_provider = getattr(subset_response, "provider", default_provider)
    tile_counter: list[int] = [0]
    for result in subset_response.results:
        provider = getattr(result, "provider", None) or subset_provider
        result_files, result_paths, result_warnings = _download_result_files(
            result,
            output_dir,
            provider,
            group_by_provider,
            on_progress=on_progress,
            tile_counter=tile_counter,
            total_tiles=total_tiles,
        )
        downloaded_files.extend(result_files)
        warnings_list.extend(result_warnings)
        for dataset, paths in result_paths.items():
            downloaded_by_dataset.setdefault(dataset, []).extend(paths)
    return downloaded_files, downloaded_by_dataset, warnings_list


def _download_result_files(
    result: object,
    output_dir: Path,
    provider: str,
    group_by_provider: bool,
    *,
    on_progress: Callable[[str, int, int], None] | None = None,
    tile_counter: list[int] | None = None,
    total_tiles: int = 0,
) -> tuple[list[DownloadedFile], dict[str, list[Path]], list[str]]:
    downloaded_files: list[DownloadedFile] = []
    downloaded_by_dataset: dict[str, list[Path]] = {}
    warnings_list: list[str] = []
    dataset_dir = _dataset_directory(output_dir, provider, result.dataset, group_by_provider)
    for tile in result.tiles:
        if not tile.primary_url:
            continue
        if on_progress is not None and tile_counter is not None:
            tile_counter[0] += 1
            on_progress(tile.tile_id or "tile", tile_counter[0], total_tiles)
        target_path = dataset_dir / _target_filename(tile.primary_url, tile.tile_id)
        try:
            _download_file(tile.primary_url, target_path)
        except Exception as exc:
            warnings_list.append(f"{provider}/{result.dataset}/{tile.tile_id or 'unnamed-tile'} failed: {exc}")
            continue
        downloaded_files.append(
            DownloadedFile(
                provider=provider,
                dataset=result.dataset,
                tile_id=tile.tile_id,
                source_url=tile.primary_url,
                saved_path=str(target_path.resolve()),
            )
        )
        tile_path = _maybe_extract_tif(target_path, dataset_dir) or target_path
        downloaded_by_dataset.setdefault(result.dataset, []).append(tile_path)
    return downloaded_files, downloaded_by_dataset, warnings_list


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
        return _export_for_ellipse(downloaded_by_dataset, output_dir, ellipse_gdal_dir), []
    if export_profile == "ellipse_grd":
        return _export_grd(downloaded_by_dataset, output_dir, ellipse_gdal_dir)
    return [], []


def _default_selection_name() -> str:
    return datetime.now(UTC).strftime("subset_%Y%m%dT%H%M%SZ")


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip())
    return cleaned.strip("-_") or _default_selection_name()


def _target_filename(url: str, tile_id: str | None) -> str:
    suffix = Path(url).suffix or ".tif"
    if tile_id:
        return f"{tile_id}{suffix}"
    return Path(url).name or f"download{suffix}"


def _maybe_extract_tif(zip_path: Path, dest_dir: Path) -> Path | None:
    """Extract the first .tif from *zip_path* into *dest_dir* and return its path.

    Returns None if the file is not a ZIP or contains no GeoTIFF.
    """
    if zip_path.suffix.lower() != ".zip":
        return None
    with zipfile.ZipFile(zip_path) as zf:
        tif_entries = [n for n in zf.namelist() if n.lower().endswith((".tif", ".tiff"))]
        if not tif_entries:
            return None
        zf.extract(tif_entries[0], dest_dir)
        return dest_dir / tif_entries[0]


def _download_file(url: str, target_path: Path) -> None:
    try:
        _stream_download_file(url, target_path, verify=True)
    except requests.exceptions.SSLError:
        warnings.warn(
            f"SSL verification failed for {url}; retrying without certificate verification.",
            stacklevel=2,
        )
        _stream_download_file(url, target_path, verify=False)


def _stream_download_file(url: str, target_path: Path, *, verify: bool) -> None:
    with warnings.catch_warnings():
        if not verify:
            warnings.simplefilter("ignore", InsecureRequestWarning)
        with requests.get(url, stream=True, timeout=120, verify=verify) as response:
            response.raise_for_status()
            with target_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        handle.write(chunk)


def _export_for_ellipse(
    downloaded_by_dataset: dict[str, list[Path]],
    output_dir: Path,
    ellipse_gdal_dir: str,
) -> list[str]:
    gdal_dir = Path(ellipse_gdal_dir)
    gdalbuildvrt = gdal_dir / "gdalbuildvrt.exe"
    gdalwarp = gdal_dir / "gdalwarp.exe"
    gdalinfo = gdal_dir / "gdalinfo.exe"
    if not (gdalbuildvrt.exists() and gdalwarp.exists() and gdalinfo.exists()):
        raise ValueError("Ellipse export requested, but GDAL tools were not found. Set MULTIPLANNER_ELLIPSE_GDAL_DIR to the Ellipse GDAL folder.")

    export_dir = output_dir / "utm32"
    export_dir.mkdir(parents=True, exist_ok=True)
    exports: list[str] = []
    environment = _gdal_environment(gdal_dir)
    for dataset, tile_paths in downloaded_by_dataset.items():
        exports.extend(_export_ellipse_dataset(dataset, tile_paths, export_dir, gdalbuildvrt, gdalwarp, gdalinfo, environment, output_dir.name))
    return exports


def _export_ellipse_dataset(
    dataset: str,
    tile_paths: list[Path],
    export_dir: Path,
    gdalbuildvrt: Path,
    gdalwarp: Path,
    gdalinfo: Path,
    environment: dict[str, str],
    selection_name: str,
) -> list[str]:
    if not tile_paths:
        return []
    export_stem = _slugify(f"{selection_name}_{dataset}_{len(tile_paths)}tiles_utm32n_ellipse")
    vrt_path = export_dir / f"{export_stem}.vrt"
    tif_path = export_dir / f"{export_stem}.tif"
    tab_path = export_dir / f"{export_stem}.TAB"
    _build_vrt(gdalbuildvrt, vrt_path, tile_paths, environment)
    _warp_vrt(gdalwarp, vrt_path, tif_path, environment)
    _write_mapinfo_tab(gdalinfo, tif_path, tab_path, environment)
    return [str(tif_path.resolve()), str(tab_path.resolve())]


def _export_grd(
    downloaded_by_dataset: dict[str, list[Path]],
    output_dir: Path,
    ellipse_gdal_dir: str,
) -> tuple[list[str], list[str]]:
    gdal_dir = Path(ellipse_gdal_dir)
    gdalbuildvrt = gdal_dir / "gdalbuildvrt.exe"
    gdalwarp = gdal_dir / "gdalwarp.exe"
    gdalinfo = gdal_dir / "gdalinfo.exe"
    if not (gdalbuildvrt.exists() and gdalwarp.exists() and gdalinfo.exists()):
        raise ValueError("GRD export requested, but GDAL tools were not found. Set MULTIPLANNER_ELLIPSE_GDAL_DIR to the Ellipse GDAL folder.")

    export_dir = output_dir / "utm32_grd"
    export_dir.mkdir(parents=True, exist_ok=True)
    environment = _gdal_environment(gdal_dir)
    exports: list[str] = []
    warnings_list: list[str] = []
    for dataset, tile_paths in downloaded_by_dataset.items():
        export_paths = _export_grd_dataset(dataset, tile_paths, export_dir, gdalbuildvrt, gdalwarp, gdalinfo, environment, output_dir.name)
        exports.extend(export_paths[0])
        warnings_list.extend(export_paths[1])
    return exports, warnings_list


def _export_grd_dataset(
    dataset: str,
    tile_paths: list[Path],
    export_dir: Path,
    gdalbuildvrt: Path,
    gdalwarp: Path,
    gdalinfo: Path,
    environment: dict[str, str],
    selection_name: str,
) -> tuple[list[str], list[str]]:
    if not tile_paths:
        return [], []
    stem = _slugify(f"{selection_name}_{dataset}_{len(tile_paths)}tiles")
    vrt_path = export_dir / f"{stem}.vrt"
    try:
        _build_vrt(gdalbuildvrt, vrt_path, tile_paths, environment)
        if dataset in ELEVATION_DATASETS:
            return _export_grd_elevation(stem, export_dir, gdalwarp, gdalinfo, environment, vrt_path), []
        if dataset in ORTHO_DATASETS:
            return _export_grd_orthophoto(stem, export_dir, gdalwarp, gdalinfo, environment, vrt_path), []
        return [], [f"GRD export skipped for unsupported dataset {dataset}."]
    except subprocess.CalledProcessError as exc:
        return [], [f"GRD export failed for {dataset}: {exc}"]


def _export_grd_elevation(
    stem: str,
    export_dir: Path,
    gdalwarp: Path,
    gdalinfo: Path,
    environment: dict[str, str],
    vrt_path: Path,
) -> list[str]:
    grd_path = export_dir / f"{stem}_utm32.grd"
    tab_path = export_dir / f"{stem}_utm32.TAB"
    tif_path = export_dir / f"{stem}_utm32_grd_src.tif"
    gdal_translate = gdalwarp.with_name("gdal_translate.exe")
    _warp_vrt(gdalwarp, vrt_path, tif_path, environment)
    _translate_to_grd(gdal_translate, tif_path, grd_path, environment)
    _write_mapinfo_tab(gdalinfo, grd_path, tab_path, environment)
    tif_path.unlink(missing_ok=True)
    vrt_path.unlink(missing_ok=True)
    return [str(grd_path.resolve()), str(tab_path.resolve())]


def _export_grd_orthophoto(
    stem: str,
    export_dir: Path,
    gdalwarp: Path,
    gdalinfo: Path,
    environment: dict[str, str],
    vrt_path: Path,
) -> list[str]:
    tif_path = export_dir / f"{stem}_utm32.tif"
    tab_path = export_dir / f"{stem}_utm32.TAB"
    _warp_vrt(gdalwarp, vrt_path, tif_path, environment)
    _write_mapinfo_tab(gdalinfo, tif_path, tab_path, environment)
    vrt_path.unlink(missing_ok=True)
    return [str(tif_path.resolve()), str(tab_path.resolve())]


def _translate_to_grd(gdal_translate: Path, tif_path: Path, grd_path: Path, environment: dict[str, str]) -> None:
    # NWT_GRD stores elevations as 16-bit ints scaled between the header's Z-min/
    # Z-max. gdalwarp's Create path can't know that range before streaming pixels,
    # so it bakes in garbage min/max (~+/-2e38) and every elevation collapses onto
    # a single quantization level -> a flat surface of bogus values. gdal_translate
    # uses CreateCopy, which derives the true min/max from the already-warped
    # Float32 GeoTIFF, so the elevation export must go warp -> GTiff -> translate.
    subprocess.run(
        [
            str(gdal_translate),
            "-of", GRD_DRIVER,
            "-ot", "Float32",
            "-b", "1",
            str(tif_path),
            str(grd_path),
        ],
        check=True,
        env=environment,
    )
    _patch_grd_style(grd_path)


def _patch_grd_style(grd_path: Path) -> None:
    # Three fixes needed to make GDAL-written NWT_GRD compatible with Ellipse,
    # compared against the known-good Vertical Mapper reference grid:
    #
    # 1. Style flags at offset 512 (int32): GDAL writes 0; Ellipse uses these to
    #    decide between continuous elevation surface (7) and classified/image (0).
    #    With 0 it reads byte color-ramp bands instead of the Float32 Z band.
    #
    # 2. Color table entry [1] Z value: GDAL writes a relative offset (half the
    #    Z-range) instead of an absolute elevation, so it falls below fZMin and
    #    makes the table invalid. Fix: add fZMin to convert to absolute.
    #
    # 3. Projection string at offset 256: GDAL omits the "CoordSys " prefix that
    #    MapInfo/Ellipse requires to parse it as a valid coordinate system.
    with grd_path.open("r+b") as f:
        b = f.read(1024)
        fz_min = struct.unpack_from("<f", b, 45)[0]
        n_inflections = struct.unpack_from("<H", b, 516)[0]

        f.seek(512)
        f.write(b"\x07\x00\x00\x00")

        if n_inflections >= 3:
            entry1_z_off = 518 + 7  # entry[1] follows the 7-byte entry[0]
            stored_z = struct.unpack_from("<f", b, entry1_z_off)[0]
            if stored_z < fz_min:
                f.seek(entry1_z_off)
                f.write(struct.pack("<f", fz_min + stored_z))

        proj_raw = b[256:512]
        null = proj_raw.find(0)
        proj_str = proj_raw[:null].decode("ascii", "replace") if null > 0 else ""
        if proj_str and not proj_str.startswith("CoordSys "):
            try:
                f.seek(256)
                f.write(("CoordSys " + proj_str).encode("ascii") + b"\x00")
            except UnicodeEncodeError:
                pass  # non-ASCII projection string; leave as-is


def _gdal_environment(gdal_dir: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["PROJ_LIB"] = str(gdal_dir / "projlib")
    environment["GDAL_DATA"] = str(gdal_dir / "gdal-data")
    return environment


def _build_vrt(gdalbuildvrt: Path, vrt_path: Path, tile_paths: list[Path], environment: dict[str, str]) -> None:
    subprocess.run([str(gdalbuildvrt), str(vrt_path), *[str(path) for path in tile_paths]], check=True, env=environment)


def _warp_vrt(gdalwarp: Path, vrt_path: Path, tif_path: Path, environment: dict[str, str]) -> None:
    subprocess.run(
        [
            str(gdalwarp),
            "-of",
            "GTiff",
            "-t_srs",
            WGS84_UTM32,
            "-co",
            "COMPRESS=LZW",
            "-co",
            "BIGTIFF=YES",
            "-co",
            "TILED=YES",
            "-co",
            "BLOCKXSIZE=512",
            "-co",
            "BLOCKYSIZE=512",
            str(vrt_path),
            str(tif_path),
        ],
        check=True,
        env=environment,
    )


def _write_mapinfo_tab(gdalinfo: Path, tif_path: Path, tab_path: Path, environment: dict[str, str]) -> None:
    payload = _gdalinfo_payload(gdalinfo, tif_path, environment)
    tab_path.write_text(_mapinfo_tab_content(tif_path.name, payload), encoding="ascii")


def _gdalinfo_payload(gdalinfo: Path, tif_path: Path, environment: dict[str, str]) -> dict[str, object]:
    info = subprocess.run([str(gdalinfo), "-json", str(tif_path)], check=True, capture_output=True, text=True, env=environment)
    return json.loads(info.stdout)


def _mapinfo_tab_content(filename: str, payload: dict[str, object]) -> str:
    width, height = payload["size"]
    corners = payload["cornerCoordinates"]
    upper_left = corners["upperLeft"]
    upper_right = corners["upperRight"]
    lower_right = corners["lowerRight"]
    lower_left = corners["lowerLeft"]
    return "\n".join(
        [
            "!table",
            "!version 300",
            "!charset WindowsLatin1",
            "",
            "Definition Table",
            f'  File "{filename}"',
            '  Type "RASTER"',
            f'  ({upper_left[0]},{upper_left[1]}) (0,0) Label "Pt 1",',
            f'  ({upper_right[0]},{upper_right[1]}) ({width},0) Label "Pt 2",',
            f'  ({lower_right[0]},{lower_right[1]}) ({width},{height}) Label "Pt 3",',
            f'  ({lower_left[0]},{lower_left[1]}) (0,{height}) Label "Pt 4"',
            MAPINFO_WGS84_UTM32,
            '  Units "m"',
            "  RasterStyle 4 1",
            "  RasterStyle 9 1",
            "",
        ]
    )
