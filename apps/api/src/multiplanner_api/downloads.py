from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re
import subprocess

import requests

from multiplanner_api.config import load_settings
from multiplanner_api.models import (
    DownloadSubsetRequest,
    DownloadSubsetResponse,
    DownloadedFile,
    LocateSubsetRequest,
)
from multiplanner_api.subsets import locate_subsets

WGS84_UTM32 = "EPSG:32632"
MAPINFO_WGS84_UTM32 = '  CoordSys Earth Projection 8, 104, "m", 9, 0, 0.9996, 500000, 0'


def download_subset(request: DownloadSubsetRequest) -> DownloadSubsetResponse:
    locate_request = LocateSubsetRequest(
        provider=request.provider,
        datasets=request.datasets,
        geometry=request.geometry,
    )
    subset_response = locate_subsets(locate_request)

    settings = load_settings()
    selection_name = request.selection_name or _default_selection_name()
    selection_slug = _slugify(selection_name)
    output_dir = Path(settings.cache_root) / "saved_subsets" / selection_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    downloaded_files: list[DownloadedFile] = []
    downloaded_by_dataset: dict[str, list[Path]] = {}
    for result in subset_response.results:
        dataset_dir = output_dir / result.dataset
        dataset_dir.mkdir(parents=True, exist_ok=True)
        for tile in result.tiles:
            if not tile.primary_url:
                continue
            target_path = dataset_dir / _target_filename(tile.primary_url, tile.tile_id)
            _download_file(tile.primary_url, target_path)
            downloaded_files.append(
                DownloadedFile(
                    dataset=result.dataset,
                    tile_id=tile.tile_id,
                    source_url=tile.primary_url,
                    saved_path=str(target_path),
                )
            )
            downloaded_by_dataset.setdefault(result.dataset, []).append(target_path)

    exports: list[str] = []
    if request.export_profile == "ellipse_mapinfo_tab":
        exports = _export_for_ellipse(
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
    )


def _default_selection_name() -> str:
    return datetime.now(UTC).strftime("subset_%Y%m%dT%H%M%SZ")


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip())
    return cleaned.strip("-_") or _default_selection_name()


def _target_filename(url: str, tile_id: str | None) -> str:
    suffix = Path(url).suffix or ".bin"
    if tile_id:
        return f"{tile_id}{suffix}"
    return Path(url).name or f"download{suffix}"


def _download_file(url: str, target_path: Path) -> None:
    with requests.get(url, stream=True, timeout=120) as response:
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
    gdal_translate = gdal_dir / "gdal_translate.exe"
    gdalinfo = gdal_dir / "gdalinfo.exe"

    if not (gdalbuildvrt.exists() and gdal_translate.exists() and gdalinfo.exists()):
        raise ValueError(
            "Ellipse export requested, but GDAL tools were not found. "
            "Set MULTIPLANNER_ELLIPSE_GDAL_DIR to the Ellipse GDAL folder."
        )

    export_dir = output_dir / "utm32"
    export_dir.mkdir(parents=True, exist_ok=True)
    exports: list[str] = []

    for dataset, tile_paths in downloaded_by_dataset.items():
        if not tile_paths:
            continue
        vrt_path = export_dir / f"{dataset}.vrt"
        tif_path = export_dir / f"{dataset}.tif"
        tab_path = export_dir / f"{dataset}.TAB"
        _build_vrt(gdalbuildvrt, vrt_path, tile_paths)
        _translate_vrt(gdal_translate, vrt_path, tif_path)
        _write_mapinfo_tab(gdalinfo, tif_path, tab_path)
        exports.append(str(tif_path))
        exports.append(str(tab_path))

    return exports


def _build_vrt(gdalbuildvrt: Path, vrt_path: Path, tile_paths: list[Path]) -> None:
    subprocess.run(
        [str(gdalbuildvrt), str(vrt_path), *[str(path) for path in tile_paths]],
        check=True,
    )


def _translate_vrt(gdal_translate: Path, vrt_path: Path, tif_path: Path) -> None:
    subprocess.run(
        [
            str(gdal_translate),
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
    )


def _write_mapinfo_tab(gdalinfo: Path, tif_path: Path, tab_path: Path) -> None:
    info = subprocess.run(
        [str(gdalinfo), "-json", str(tif_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(info.stdout)
    width, height = payload["size"]
    corners = payload["cornerCoordinates"]
    upper_left = corners["upperLeft"]
    upper_right = corners["upperRight"]
    lower_right = corners["lowerRight"]
    lower_left = corners["lowerLeft"]

    content = "\n".join(
        [
            "!table",
            "!version 300",
            "!charset WindowsLatin1",
            "",
            "Definition Table",
            f'  File "{tif_path.name}"',
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
    tab_path.write_text(content, encoding="ascii")
