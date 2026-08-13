from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree

import numpy as np

from multiplanner_api.models import BboxGeometryInput, PointGeometryInput
from multiplanner_api.semantic_grc_exports import (
    RESOLUTION_M,
    _masked_height_grids,
    _selection_bounds,
    _write_height_grcs,
    _write_grc_files,
    export_semantic_grc,
)


def test_height_grids_store_dom_minus_dgm_only_for_matching_class() -> None:
    dgm = np.array([[100, 100, 100], [100, 100, 100]], dtype=np.float32)
    dom = np.array([[115, 130, 108], [95, 112, 125]], dtype=np.float32)
    mask = np.array([[85, 1, 43], [85, 0, 1]], dtype=np.uint8)

    buildings, trees = _masked_height_grids(dgm, dom, mask)

    np.testing.assert_array_equal(buildings, [[15, 0, 0], [0, 0, 0]])
    np.testing.assert_array_equal(trees, [[0, 30, 8], [0, 0, 25]])


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


def test_height_grcs_use_variable_height_classification(monkeypatch, tmp_path) -> None:
    calls = []
    monkeypatch.setattr(
        "multiplanner_api.semantic_grc_exports._convert_height_grc",
        lambda source, target, layer, maximum: calls.append((source, target, layer, maximum)),
    )
    building_values = np.array([[0, 3.2], [10.7, 0]], dtype=np.float32)
    tree_values = np.array([[0.5, 25.4], [0, 8]], dtype=np.float32)

    outputs = _write_height_grcs(
        tmp_path / "building.tif", tmp_path / "tree.tif",
        building_values, tree_values, tmp_path, 2,
    )

    assert [path.name for path in outputs] == [
        "buildings_2m_utm32n.grc", "trees_2m_utm32n.grc",
        "buildings_2m_height_table.vse", "trees_2m_height_table.vse",
        "buildings_2m_height_definition.xml", "trees_2m_height_definition.xml",
    ]
    assert [(call[2], call[3]) for call in calls] == [
        ("building_heights", np.float32(10.7)), ("tree_heights", 41.0),
    ]
    tree_style = (tmp_path / "trees_2m_height_table.vse").read_text(encoding="utf-8")
    assert '"229,254,250" "Forest 0.5m"' in tree_style
    assert '"216,244,232" "Forest 1.5m"' in tree_style
    building_style = (tmp_path / "buildings_2m_height_table.vse").read_text(encoding="utf-8")
    assert building_style.splitlines()[3] == "23"
    tree_definition = ElementTree.parse(tmp_path / "trees_2m_height_definition.xml")
    settings = tree_definition.findall("./echelle/settings_type")
    values = tree_definition.findall("./echelle/echelle_values")
    assert settings[0].attrib["height"] == "0"
    assert settings[3].attrib["height"] == "1.5"
    assert values[3].attrib == {
        "setting_type": "CSettingsType_Height",
        "clutter_item_text": "Forest 1.5m",
        "clutter_item_val": "3",
    }
    assert settings[-1].attrib["height"] == "41"
    assert values[-1].attrib["clutter_item_text"] == "Forest 41.0m"


def test_export_reports_missing_gdal_tools_as_warning(tmp_path) -> None:
    exports, warnings = export_semantic_grc(
        geometry=PointGeometryInput(kind="point", lon=11.5756, lat=48.1372),
        lod2_paths=[],
        dgm_paths=[],
        dom_paths=[],
        output_dir=tmp_path,
        ellipse_gdal_dir=str(tmp_path / "missing-gdal"),
    )

    assert exports == []
    assert warnings[0].startswith("Buildings + trees GRC export failed: missing Ellipse GDAL tool(s):")
