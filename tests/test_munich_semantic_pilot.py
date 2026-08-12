from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_munich_semantic_pilot.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_munich_semantic_pilot", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_writes_buildings_and_trees_to_separate_grc_files(tmp_path: Path) -> None:
    module = _load_script()
    conversions: list[tuple[Path, Path, str]] = []
    module._write_mapinfo_grc = lambda source, target, layer: conversions.append(
        (source, target, layer)
    )
    source = tmp_path / "semantic-mask.grd"

    module._write_separate_grc(source, tmp_path)

    assert conversions == [
        (source, tmp_path / "munich_pilot_buildings_2m.grc", "buildings"),
        (source, tmp_path / "munich_pilot_trees_2m.grc", "trees"),
    ]


def test_grc_converter_receives_requested_layer(tmp_path: Path, monkeypatch) -> None:
    module = _load_script()
    source = tmp_path / "semantic-mask.grd"
    target = tmp_path / "trees.grc"
    source.write_bytes(b"source")
    converter = SCRIPT_PATH.with_name("convert_mapinfo_grc.ps1")
    calls: list[list[str]] = []

    monkeypatch.setattr(module.shutil, "which", lambda name: "powershell.exe")

    def run(command: list[str], *, check: bool) -> None:
        assert check
        calls.append(command)
        Path(command[command.index("-OutputPath") + 1]).write_bytes(b"grc")

    monkeypatch.setattr(module.subprocess, "run", run)
    module._write_mapinfo_grc(source, target, "trees")

    assert target.read_bytes() == b"grc"
    assert calls == [[
        "powershell.exe", "-NoProfile", "-File", str(converter),
        "-InputPath", str(source), "-OutputPath",
        str(tmp_path / "trees.converting.grc"), "-Layer", "trees",
    ]]
