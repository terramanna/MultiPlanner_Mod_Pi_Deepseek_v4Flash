from __future__ import annotations

from importlib import util
from pathlib import Path
from types import SimpleNamespace


def load_widget_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "multiplanner_status_widget.py"
    spec = util.spec_from_file_location("multiplanner_status_widget", path)
    assert spec and spec.loader
    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pids_to_stop_includes_spawned_children(monkeypatch):
    module = load_widget_module()
    service = module.Service(
        name="Backend",
        url="http://127.0.0.1:8000/healthz",
        command=["python", "backend"],
        cwd=Path("."),
    )
    monkeypatch.setattr(module, "load_pid_registry", lambda: {"Backend": 28368})

    def fake_run(args, **kwargs):
        command = args if isinstance(args, str) else " ".join(args)
        if "netstat" in command:
            return SimpleNamespace(stdout="  TCP    127.0.0.1:8000    0.0.0.0:0    LISTENING    28368\n")
        if "ProcessId" in command and "ParentProcessId" in command:
            return SimpleNamespace(stdout="28368 25116\n33380 28368\n")
        if "multiplanner_api.main:app" in command:
            return SimpleNamespace(stdout="28368\n")
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert service.pids_to_stop() == [28368, 33380]


def test_pids_to_stop_includes_frontend_wrapper_chain(monkeypatch):
    module = load_widget_module()
    service = module.Service(
        name="Frontend",
        url="http://127.0.0.1:5173",
        command=["npm.cmd", "run", "dev"],
        cwd=Path("."),
    )
    monkeypatch.setattr(module, "load_pid_registry", lambda: {"Frontend": 30280})

    def fake_run(args, **kwargs):
        command = args if isinstance(args, str) else " ".join(args)
        if "netstat" in command:
            return SimpleNamespace(stdout="  TCP    127.0.0.1:5173    0.0.0.0:0    LISTENING    17020\n")
        if "ProcessId" in command and "ParentProcessId" in command:
            return SimpleNamespace(stdout="30280 28260\n25116 30280\n6624 25116\n17020 6624\n")
        if "npm.cmd run dev" in command:
            return SimpleNamespace(stdout="30280\n")
        return SimpleNamespace(stdout="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    pids = service.pids_to_stop()
    assert pids[0] == 30280
    assert set(pids) == {6624, 17020, 25116, 30280}


def test_stop_keeps_registry_when_backend_is_still_running(monkeypatch):
    module = load_widget_module()
    service = module.Service(
        name="Backend",
        url="http://127.0.0.1:8000/healthz",
        command=["python", "backend"],
        cwd=Path("."),
    )
    removed = []
    monkeypatch.setattr(service, "pids_to_stop", lambda: [])
    monkeypatch.setattr(service, "is_process_running", lambda: True)
    monkeypatch.setattr(service, "is_port_running", lambda: True)
    monkeypatch.setattr(service, "forget_pid", lambda: removed.append(True))

    assert service.stop() is False
    assert removed == []


def test_stop_terminates_own_launcher_handle_first(monkeypatch):
    module = load_widget_module()
    service = module.Service(
        name="Frontend",
        url="http://127.0.0.1:5173",
        command=["npm.cmd", "run", "dev"],
        cwd=Path("."),
    )
    terminated = []
    running = {"alive": True}

    service.process = SimpleNamespace(
        pid=30280,
        poll=lambda: None if running["alive"] else 0,
        terminate=lambda: (terminated.append(True), running.__setitem__("alive", False)),
    )
    monkeypatch.setattr(service, "pids_to_stop", lambda: [30280])
    monkeypatch.setattr(service, "is_process_running", lambda: False)
    monkeypatch.setattr(service, "is_port_running", lambda: False)
    monkeypatch.setattr(service, "forget_pid", lambda: None)

    assert service.stop() is True
    assert terminated == [True]


def test_effective_state_uses_display_override(monkeypatch):
    module = load_widget_module()
    service = module.Service(
        name="Frontend",
        url="http://127.0.0.1:5173",
        command=["npm.cmd", "run", "dev"],
        cwd=Path("."),
    )
    service.display_state = "stopping"
    monkeypatch.setattr(service, "health", lambda: "running")

    assert service.effective_state() == "stopping"


def test_status_lamp_mapping_is_stable():
    module = load_widget_module()

    assert module.StatusWidget.colors == {
        "running": "#16a34a",
        "starting": "#eab308",
        "stopping": "#f59e0b",
        "problem": "#f97316",
        "stopped": "#dc2626",
    }
    assert module.StatusWidget.labels == {
        "running": "Running",
        "starting": "Starting",
        "stopping": "Stopping",
        "problem": "Problem",
        "stopped": "Stopped",
    }
