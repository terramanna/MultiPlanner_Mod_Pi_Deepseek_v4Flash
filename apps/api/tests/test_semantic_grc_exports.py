from pathlib import Path
from types import SimpleNamespace

from multiplanner_api.models import BboxGeometryInput, PointGeometryInput
from multiplanner_api.semantic_grc_exports import (
    RESOLUTION_M,
    _selection_bounds,
    _write_grc_files,
    export_semantic_grc,
)


def test_selection_bounds_are_utm32_aligned_and_geometry_driven() -> None:
    small = BboxGeometryInput(kind="bbox", west=11.57, south=48.13, east=11.58, north=48.14)
    large = BboxGeometryInput(kind="bbox", west=11.57, south=48.13, east=11.60, north=48.16)

    small_bounds = _selection_bounds(small)
    large_bounds = _selection_bounds(large)

    assert all(value % RESOLUTION_M == 0 for value in small_bounds)
    assert large_bounds[2] - large_bounds[0] > small_bounds[2] - small_bounds[0]
    assert large_bounds[3] - large_bounds[1] > small_bounds[3] - small_bounds[1]


def test_point_export_uses_a_one_kilometre_work_area() -> None:
    bounds = _selection_bounds(PointGeometryInput(kind="point", lon=11.5756, lat=48.1372))

    assert 1_000 <= bounds[2] - bounds[0] <= 1_004
    assert 1_000 <= bounds[3] - bounds[1] <= 1_004


def test_mapinfo_conversion_writes_buildings_and_trees(monkeypatch, tmp_path) -> None:
    source = tmp_path / "mask.grd"
    source.write_bytes(b"grid")
    converter = Path(__file__).parents[4] / "scripts" / "convert_mapinfo_grc.ps1"
    calls = []

    monkeypatch.setattr("multiplanner_api.semantic_grc_exports.shutil.which", lambda _name: "powershell.exe")
    monkeypatch.setattr(converter.__class__, "exists", lambda self: True)

    def fake_run(command, check):
        calls.append(command)
        Path(command[command.index("-OutputPath") + 1]).write_bytes(b"grc")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("multiplanner_api.semantic_grc_exports.subprocess.run", fake_run)
    outputs = _write_grc_files(source, tmp_path)

    assert [path.name for path in outputs] == ["buildings_2m_utm32n.grc", "trees_2m_utm32n.grc"]
    assert [command[command.index("-Layer") + 1] for command in calls] == ["buildings", "trees"]


def test_export_reports_missing_gdal_tools_as_warning(tmp_path) -> None:
    exports, warnings = export_semantic_grc(
        geometry=PointGeometryInput(kind="point", lon=11.5756, lat=48.1372),
        lod2_paths=[],
        output_dir=tmp_path,
        ellipse_gdal_dir=str(tmp_path / "missing-gdal"),
    )

    assert exports == []
    assert warnings[0].startswith("Buildings + trees GRC export failed: missing Ellipse GDAL tool(s):")
