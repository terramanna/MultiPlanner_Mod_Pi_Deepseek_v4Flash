from __future__ import annotations

import json
import os
import re
import struct
import subprocess
from pathlib import Path

WGS84_UTM32 = "EPSG:32632"
MAPINFO_WGS84_UTM32 = '  CoordSys Earth Projection 8, 104, "m", 9, 0, 0.9996, 500000, 0'
ELEVATION_DATASETS = frozenset({"dgm1", "dom1"})
ORTHO_DATASETS = frozenset({"dop20"})
GRD_DRIVER = "NWT_GRD"
PYRAMID_LEVELS = ("2", "4", "8", "16", "32")
ASCII_SOURCE_CRS_BY_TOKEN = {
    "sh_dgm": "EPSG:25832",
    "_bw": "EPSG:25832",
    "_hh": "EPSG:25832",
    "_hb": "EPSG:25832",
    "_sh": "EPSG:25832",
    "_th": "EPSG:25832",
    "_be": "EPSG:25833",
}


def _export_for_ellipse(
    downloaded_by_dataset: dict[str, list[Path]],
    output_dir: Path,
    ellipse_gdal_dir: str,
    *,
    build_pyramids: bool,
) -> tuple[list[str], list[str]]:
    gdal_dir = Path(ellipse_gdal_dir)
    gdalbuildvrt = gdal_dir / "gdalbuildvrt.exe"
    gdalwarp = gdal_dir / "gdalwarp.exe"
    gdalinfo = gdal_dir / "gdalinfo.exe"
    gdaladdo = gdal_dir / "gdaladdo.exe"
    required_tools = gdalbuildvrt.exists() and gdalwarp.exists() and gdalinfo.exists() and (gdaladdo.exists() or not build_pyramids)
    if not required_tools:
        return [], ["UTM32N GeoTIFF + TAB export failed: GDAL tools were not found. Set MULTIPLANNER_ELLIPSE_GDAL_DIR to the Ellipse GDAL folder."]

    export_dir = output_dir / "utm32"
    export_dir.mkdir(parents=True, exist_ok=True)
    exports: list[str] = []
    warnings_list: list[str] = []
    environment = _gdal_environment(gdal_dir)
    for dataset, tile_paths in downloaded_by_dataset.items():
        try:
            exports.extend(_export_ellipse_dataset(dataset, tile_paths, export_dir, gdalbuildvrt, gdalwarp, gdalinfo, gdaladdo, environment, output_dir.name, build_pyramids))
        except ValueError as exc:
            warnings_list.append(f"UTM32N GeoTIFF + TAB export failed for {dataset}: {exc}")
    return exports, warnings_list


def _export_ellipse_dataset(
    dataset: str,
    tile_paths: list[Path],
    export_dir: Path,
    gdalbuildvrt: Path,
    gdalwarp: Path,
    gdalinfo: Path,
    gdaladdo: Path,
    environment: dict[str, str],
    selection_name: str,
    build_pyramids: bool,
) -> list[str]:
    if not tile_paths:
        return []
    suffix = "utm32n_ellipse_pyramids" if build_pyramids else "utm32n_ellipse"
    export_stem = _slugify(f"{selection_name}_{dataset}_{len(tile_paths)}tiles_{suffix}")
    vrt_path = export_dir / f"{export_stem}.vrt"
    tif_path = export_dir / f"{export_stem}.tif"
    tab_path = export_dir / f"{export_stem}.TAB"
    export_sources = _prepare_export_sources(tile_paths, gdalbuildvrt.with_name("gdal_translate.exe"), environment)
    _build_vrt(gdalbuildvrt, vrt_path, export_sources, environment)
    _warp_vrt(gdalwarp, vrt_path, tif_path, environment)
    if build_pyramids:
        _build_geotiff_pyramids(gdaladdo, tif_path, environment)
    _write_mapinfo_tab(gdalinfo, tif_path, tab_path, environment, require_utm32=True)
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
        export_paths, dataset_warnings = _export_grd_dataset(dataset, tile_paths, export_dir, gdalbuildvrt, gdalwarp, gdalinfo, environment, output_dir.name)
        exports.extend(export_paths)
        warnings_list.extend(dataset_warnings)
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
        export_sources = _prepare_export_sources(tile_paths, gdalbuildvrt.with_name("gdal_translate.exe"), environment)
        _build_vrt(gdalbuildvrt, vrt_path, export_sources, environment)
        if dataset in ELEVATION_DATASETS:
            return _export_grd_elevation(stem, export_dir, gdalwarp, gdalinfo, environment, vrt_path), []
        if dataset in ORTHO_DATASETS:
            return _export_grd_orthophoto(stem, export_dir, gdalwarp, gdalinfo, environment, vrt_path), []
        return [], [f"GRD export skipped for unsupported dataset {dataset}."]
    except ValueError as exc:
        return [], [f"GRD export failed for {dataset}: {exc}"]


def _prepare_export_sources(paths: list[Path], gdal_translate: Path, environment: dict[str, str]) -> list[Path]:
    return [_prepare_export_source(path, gdal_translate, environment) for path in paths]


def _prepare_export_source(path: Path, gdal_translate: Path, environment: dict[str, str]) -> Path:
    if path.suffix.lower() not in {".xyz", ".csv"}:
        return path
    source_crs = _ascii_source_crs(path)
    if not source_crs:
        raise ValueError(f"Cannot export {path.name}: ASCII raster source CRS is unknown.")
    tif_path = path.with_suffix(f"{path.suffix}.tif")
    if tif_path.exists() and tif_path.stat().st_size > 0:
        return tif_path
    _translate_ascii_to_tif(gdal_translate, path, tif_path, source_crs, environment)
    return tif_path


def _ascii_source_crs(path: Path) -> str | None:
    name = path.name.casefold()
    for token, crs in ASCII_SOURCE_CRS_BY_TOKEN.items():
        if token in name:
            return crs
    return None


def _translate_ascii_to_tif(
    gdal_translate: Path,
    source_path: Path,
    tif_path: Path,
    source_crs: str,
    environment: dict[str, str],
) -> None:
    _run_gdal(
        [
            str(gdal_translate),
            "-of", "GTiff",
            "-a_srs", source_crs,
            "-co", "COMPRESS=LZW",
            str(source_path),
            str(tif_path),
        ],
        environment,
    )


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
    _run_gdal(
        [
            str(gdal_translate),
            "-of", GRD_DRIVER,
            "-ot", "Float32",
            "-b", "1",
            str(tif_path),
            str(grd_path),
        ],
        environment,
    )
    _patch_grd_style(grd_path)


def _patch_grd_style(grd_path: Path) -> None:
    with grd_path.open("r+b") as f:
        b = f.read(1024)
        fz_min = struct.unpack_from("<f", b, 45)[0]
        n_inflections = struct.unpack_from("<H", b, 516)[0]

        f.seek(512)
        f.write(b"\x07\x00\x00\x00")

        if n_inflections >= 3:
            entry1_z_off = 518 + 7
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
                pass


def _gdal_environment(gdal_dir: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["PROJ_LIB"] = str(gdal_dir / "projlib")
    environment["GDAL_DATA"] = str(gdal_dir / "gdal-data")
    return environment


def _build_vrt(gdalbuildvrt: Path, vrt_path: Path, tile_paths: list[Path], environment: dict[str, str]) -> None:
    _run_gdal([str(gdalbuildvrt), str(vrt_path), *[str(path) for path in tile_paths]], environment)


def _warp_vrt(gdalwarp: Path, vrt_path: Path, tif_path: Path, environment: dict[str, str]) -> None:
    _run_gdal(
        [
            str(gdalwarp),
            "-of", "GTiff",
            "-t_srs", WGS84_UTM32,
            "-co", "COMPRESS=LZW",
            "-co", "BIGTIFF=YES",
            "-co", "TILED=YES",
            "-co", "BLOCKXSIZE=512",
            "-co", "BLOCKYSIZE=512",
            str(vrt_path),
            str(tif_path),
        ],
        environment,
    )


def _write_mapinfo_tab(gdalinfo: Path, tif_path: Path, tab_path: Path, environment: dict[str, str], *, require_utm32: bool = False) -> None:
    payload = _gdalinfo_payload(gdalinfo, tif_path, environment)
    if require_utm32:
        _validate_utm32_payload(tif_path, payload)
    tab_path.write_text(_mapinfo_tab_content(tif_path.name, payload), encoding="ascii")


def _validate_utm32_payload(tif_path: Path, payload: dict[str, object]) -> None:
    coordinate_system = payload.get("coordinateSystem")
    serialized = json.dumps(coordinate_system or {})
    if WGS84_UTM32.removeprefix("EPSG:") not in serialized:
        raise ValueError(f"{tif_path.name} was not reprojected to {WGS84_UTM32}; conversion stopped.")


def _build_geotiff_pyramids(gdaladdo: Path, tif_path: Path, environment: dict[str, str]) -> None:
    _run_gdal(
        [
            str(gdaladdo),
            "-r", "average",
            "--config", "COMPRESS_OVERVIEW", "LZW",
            "--config", "BIGTIFF_OVERVIEW", "YES",
            str(tif_path),
            *PYRAMID_LEVELS,
        ],
        environment,
    )


def _gdalinfo_payload(gdalinfo: Path, tif_path: Path, environment: dict[str, str]) -> dict[str, object]:
    info = _run_gdal([str(gdalinfo), "-json", str(tif_path)], environment)
    return json.loads(info.stdout)


def _run_gdal(command: list[str], environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True, env=environment)
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or str(exc)).strip()
        raise ValueError(f"{Path(command[0]).name} failed: {message}") from None


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


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip())
    return cleaned.strip("-_") or "subset"
