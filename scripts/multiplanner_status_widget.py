from __future__ import annotations

import argparse
import ctypes
from collections import defaultdict
import json
import subprocess
import threading
import sys
import time
import tkinter as tk
from pathlib import Path
from urllib.parse import urlparse
from tkinter import messagebox
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser


REPO_ROOT = Path(__file__).resolve().parent.parent
API_ROOT = REPO_ROOT / "apps" / "api"
WEB_ROOT = REPO_ROOT / "apps" / "web"
VENV_PYTHON = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
WIDGET_WINDOW_TITLE = "MultiPlanner"
WIDGET_MUTEX_NAME = "Global\\MultiPlannerStatusWidget"
PID_REGISTRY_PATH = REPO_ROOT / ".tmp" / "multiplanner_service_pids.json"


def build_services() -> list["Service"]:
    return [
        Service(
            name="Backend",
            url="http://127.0.0.1:8000/healthz",
            command=[
                str(VENV_PYTHON),
                "-m",
                "uvicorn",
                "multiplanner_api.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
                "--reload",
            ],
            cwd=API_ROOT,
        ),
        Service(
            name="Frontend",
            url="http://127.0.0.1:5173",
            command=["npm.cmd", "run", "dev"],
            cwd=WEB_ROOT,
        ),
    ]


def environment_issues() -> list[str]:
    missing = []
    if not VENV_PYTHON.exists():
        missing.append(str(VENV_PYTHON))
    if not (WEB_ROOT / "node_modules").exists():
        missing.append(str(WEB_ROOT / "node_modules"))
    return missing


def run_service_action(action: str) -> int:
    services = build_services()
    if action == "stop":
        stopped = [service.stop() for service in services]
        return 0 if all(stopped) else 1
    missing = environment_issues()
    if missing:
        print("Run scripts\\bootstrap_local.ps1 first.")
        for path in missing:
            print(path)
        return 1
    if action == "start":
        for service in services:
            service.start()
        return 0
    if action == "restart":
        for service in services:
            service.stop()
        wait_for_services_to_stop(services, timeout=12.0)
        if any(service.is_process_running() or service.is_port_running() for service in services):
            return 1
        for service in services:
            service.start()
        return 0
    raise ValueError(f"Unknown action: {action}")


def wait_for_services_to_stop(services: list["Service"], timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if all(not service.is_process_running() and not service.is_port_running() for service in services):
            return
        time.sleep(0.25)


def load_pid_registry() -> dict[str, int]:
    try:
        if not PID_REGISTRY_PATH.exists():
            return {}
        payload = json.loads(PID_REGISTRY_PATH.read_text(encoding="utf-8"))
        return {str(key): int(value) for key, value in payload.items()}
    except Exception:
        return {}


def save_pid_registry(registry: dict[str, int]) -> None:
    PID_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    PID_REGISTRY_PATH.write_text(json.dumps(registry, separators=(",", ":")), encoding="utf-8")


class Service:
    def __init__(
        self,
        *,
        name: str,
        url: str,
        command: list[str],
        cwd: Path,
    ) -> None:
        self.name = name
        self.url = url
        self.command = command
        self.cwd = cwd
        self.process: subprocess.Popen[str] | None = None
        self.last_error = ""
        self.display_state: str | None = None
        self.port = self._parse_port(url)
        self.commandline_marker = self._commandline_marker(name)

    def start(self) -> None:
        if self.is_process_running() or self.is_port_running():
            return
        self.last_error = ""
        self.process = subprocess.Popen(
            self.command,
            cwd=self.cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            text=True,
        )
        self.remember_pid(self.process.pid)

    def stop(self) -> bool:
        self.display_state = "stopping"
        for _ in range(8):
            pids = self.pids_to_stop()
            if not pids:
                break
            for pid in pids:
                self.kill_process_tree(pid)
            time.sleep(0.4)
        if self.is_process_running() or self.is_port_running():
            self.last_error = f"{self.name} did not stop cleanly."
            return False
        self.last_error = ""
        self.process = None
        self.display_state = None
        self.forget_pid()
        return True

    def effective_state(self) -> str:
        if self.display_state:
            return self.display_state
        return self.health()

    def pids_to_stop(self) -> list[int]:
        pids = []
        if self.process and self.process.poll() is None:
            pids.append(self.process.pid)
        pids.extend(self.pids_from_registry())
        pids.extend(self.find_listener_pids())
        pids.extend(self.find_commandline_pids())
        related = self.expand_related_pids(pids)
        ordered = []
        for pid in pids:
            if pid in related and pid not in ordered:
                ordered.append(pid)
        for pid in sorted(related):
            if pid not in ordered:
                ordered.append(pid)
        return ordered

    def find_listener_pids(self) -> list[int]:
        if self.port is None:
            return []
        try:
            result = subprocess.run(
                [
                    "netstat",
                    "-ano",
                    "-p",
                    "tcp",
                ],
                check=True,
                capture_output=True,
                text=True,
                creationflags=CREATE_NO_WINDOW,
            )
        except Exception:
            return []

        pids = []
        needle = f":{self.port}"
        for line in result.stdout.splitlines():
            if needle not in line or "LISTENING" not in line.upper():
                continue
            parts = line.split()
            if not parts:
                continue
            try:
                pids.append(int(parts[-1]))
            except ValueError:
                continue
        return sorted(set(pids))

    def is_process_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def is_port_running(self) -> bool:
        return bool(self.find_listener_pids())

    def find_commandline_pids(self) -> list[int]:
        if sys.platform != "win32":
            return []
        marker = self.commandline_marker.replace("'", "''")
        return self._powershell_pids(
            f"Get-CimInstance Win32_Process | Where-Object {{$_.CommandLine -like '*{marker}*'}} | Select-Object -ExpandProperty ProcessId"
        )

    def _powershell_pids(self, command: str) -> list[int]:
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", command],
                check=True,
                capture_output=True,
                text=True,
                creationflags=CREATE_NO_WINDOW,
            )
        except Exception:
            return []

        pids = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                pids.append(int(line))
            except ValueError:
                continue
        return sorted(set(pids))

    def expand_related_pids(self, seed_pids: list[int]) -> set[int]:
        parent_by_pid = self.process_parent_map()
        children_by_pid: dict[int, set[int]] = defaultdict(set)
        for pid, parent_pid in parent_by_pid.items():
            children_by_pid[parent_pid].add(pid)

        pids = set(seed_pids)
        frontier = list(seed_pids)
        while frontier:
            pid = frontier.pop()
            for child_pid in children_by_pid.get(pid, set()):
                if child_pid not in pids:
                    pids.add(child_pid)
                    frontier.append(child_pid)
        return pids

    def process_parent_map(self) -> dict[int, int]:
        if sys.platform != "win32":
            return {}
        command = (
            "Get-CimInstance Win32_Process | "
            'ForEach-Object { "$($_.ProcessId) $($_.ParentProcessId)" }'
        )
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", command],
                check=True,
                capture_output=True,
                text=True,
                creationflags=CREATE_NO_WINDOW,
            )
        except Exception:
            return {}

        parent_by_pid: dict[int, int] = {}
        for line in result.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) != 2:
                continue
            try:
                pid = int(parts[0])
                parent_pid = int(parts[1])
            except ValueError:
                continue
            parent_by_pid[pid] = parent_pid
        return parent_by_pid

    def kill_process_tree(self, pid: int) -> None:
        if self.process and pid == self.process.pid and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
            )
            return

        try:
            subprocess.run(["kill", str(pid)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        except Exception:
            pass

    def remember_pid(self, pid: int) -> None:
        registry = load_pid_registry()
        registry[self.name] = pid
        save_pid_registry(registry)

    def forget_pid(self) -> None:
        registry = load_pid_registry()
        if self.name not in registry:
            return
        registry.pop(self.name, None)
        save_pid_registry(registry)

    def pids_from_registry(self) -> list[int]:
        pid = load_pid_registry().get(self.name)
        if pid is None:
            return []
        return [pid]

    @staticmethod
    def _parse_port(url: str) -> int | None:
        try:
            parsed = urlparse(url)
            return parsed.port
        except Exception:
            return None

    @staticmethod
    def _commandline_marker(name: str) -> str:
        if name == "Backend":
            return "multiplanner_api.main:app"
        return "vite --host 127.0.0.1 --port 5173"

    def health(self) -> str:
        try:
            with urlopen(self.url, timeout=1.5) as response:
                if 200 <= response.status < 400:
                    self.last_error = ""
                    return "running"
                self.last_error = f"HTTP {response.status}"
                return "problem"
        except URLError as exc:
            if self.is_process_running() or self.is_port_running():
                self.last_error = str(exc.reason)
                return "starting"
            self.last_error = "Not running"
            return "stopped"
        except Exception as exc:
            self.last_error = str(exc)
            return "problem"


class StatusWidget(tk.Tk):
    colors = {
        "running": "#16a34a",
        "starting": "#eab308",
        "stopping": "#f59e0b",
        "problem": "#f97316",
        "stopped": "#dc2626",
    }

    labels = {
        "running": "Running",
        "starting": "Starting",
        "stopping": "Stopping",
        "problem": "Problem",
        "stopped": "Stopped",
    }

    def __init__(self) -> None:
        super().__init__()
        self.title(WIDGET_WINDOW_TITLE)
        self.resizable(False, False)
        self.configure(bg="#f8fafc")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.services = build_services()
        self.rows: dict[str, dict[str, tk.Widget]] = {}
        self._refresh_in_progress = False
        self._refresh_pending = False
        self._action_in_progress = False
        self._stop_requested = False
        self._build_ui()
        self.after(1000, self.refresh_status)

    def _build_ui(self) -> None:
        frame = tk.Frame(self, bg="#f8fafc", padx=10, pady=8)
        frame.grid(row=0, column=0)
        self._build_title(frame)
        self._build_service_rows(frame)
        self._build_buttons(frame)
        self._build_message(frame)

    def _build_title(self, frame: tk.Frame) -> None:
        title = tk.Label(frame, text="MultiPlanner services", bg="#f8fafc", fg="#0f172a", font=("Segoe UI", 9, "bold"))
        title.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

    def _build_service_rows(self, frame: tk.Frame) -> None:
        for index, service in enumerate(self.services, start=1):
            led, dot = self._build_status_led(frame, index)
            name = self._build_service_name(frame, service, index)
            status = self._build_service_status(frame, index)
            self.rows[service.name] = {"led": led, "dot": dot, "status": status}

    def _build_status_led(self, frame: tk.Frame, index: int) -> tuple[tk.Canvas, int]:
        led = tk.Canvas(frame, width=12, height=12, bg="#f8fafc", highlightthickness=0)
        dot = led.create_oval(2, 2, 10, 10, fill=self.colors["stopped"], outline="")
        led.grid(row=index, column=0, sticky="w", padx=(0, 6), pady=2)
        return led, dot

    def _build_service_name(self, frame: tk.Frame, service: Service, index: int) -> tk.Label:
        name = tk.Label(frame, text=service.name, bg="#f8fafc", fg="#1e293b", font=("Segoe UI", 9))
        name.grid(row=index, column=1, sticky="w", padx=(0, 12), pady=2)
        return name

    def _build_service_status(self, frame: tk.Frame, index: int) -> tk.Label:
        status = tk.Label(frame, text="Stopped", bg="#f8fafc", fg="#475569", font=("Segoe UI", 9))
        status.grid(row=index, column=2, sticky="w", pady=2)
        return status

    def _build_buttons(self, frame: tk.Frame) -> None:
        buttons = tk.Frame(frame, bg="#f8fafc")
        buttons.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        tk.Button(buttons, text="Start", command=self.start_all, width=6).grid(row=0, column=0, padx=(0, 3))
        tk.Button(buttons, text="Stop", command=self.stop_all, width=6).grid(row=0, column=1, padx=3)
        tk.Button(buttons, text="Restart", command=self.restart_all, width=6).grid(row=0, column=2, padx=3)
        tk.Button(buttons, text="Open", command=lambda: webbrowser.open("http://127.0.0.1:5173/"), width=6).grid(row=0, column=3, padx=(3, 0))

    def _build_message(self, frame: tk.Frame) -> None:
        self.message = tk.Label(frame, text="Starting services...", bg="#f8fafc", fg="#64748b", font=("Segoe UI", 8), wraplength=200, justify="left")
        self.message.grid(row=5, column=0, columnspan=3, sticky="w", pady=(6, 0))

    def validate_environment(self) -> bool:
        missing = environment_issues()
        if missing:
            messagebox.showerror(
                "MultiPlanner setup missing",
                "Run scripts\\bootstrap_local.ps1 first.\n\nMissing:\n" + "\n".join(missing),
            )
            return False
        return True

    def start_all(self) -> None:
        if not self.validate_environment():
            return
        for service in self.services:
            service.display_state = None
        self._stop_requested = False
        self._run_background(self._start_services_worker, "Services are starting.")

    def stop_all(self) -> None:
        self._stop_requested = True
        for service in self.services:
            service.display_state = "stopping"
        self.message.configure(text="Stopping services...")
        threading.Thread(target=self._stop_services_worker_with_refresh, daemon=True).start()

    def restart_all(self) -> None:
        self._stop_requested = True
        self.message.configure(text="Services restarting.")
        threading.Thread(target=self._run_background_worker, args=(self._restart_services_worker,), daemon=True).start()

    def _run_background(self, worker, message: str) -> None:
        if self._action_in_progress:
            return
        self._action_in_progress = True
        self.message.configure(text=message)
        threading.Thread(target=self._run_background_worker, args=(worker,), daemon=True).start()

    def _run_background_worker(self, worker) -> None:
        try:
            worker()
        finally:
            self.after(0, self._finish_background_action)

    def _finish_background_action(self) -> None:
        self._action_in_progress = False
        self.refresh_status()

    def _start_services_worker(self) -> None:
        for service in self.services:
            if self._stop_requested:
                return
            try:
                service.start()
            except Exception as exc:
                service.last_error = str(exc)

    def _stop_services_worker(self) -> None:
        for service in self.services:
            service.stop()

    def _stop_services_worker_with_refresh(self) -> None:
        self._stop_services_worker()
        for service in self.services:
            service.display_state = None
        self.after(0, self.refresh_status)

    def _restart_services_worker(self) -> None:
        self._stop_services_worker()
        wait_for_services_to_stop(self.services, timeout=12.0)
        for service in self.services:
            service.display_state = None
        self._stop_requested = False
        self._start_services_worker()

    def refresh_status(self) -> None:
        if self._refresh_in_progress:
            self._refresh_pending = True
            return
        self._refresh_in_progress = True
        threading.Thread(target=self._refresh_status_worker, daemon=True).start()

    def _refresh_status_worker(self) -> None:
        snapshot = []
        for service in self.services:
            snapshot.append((service.name, service.effective_state(), service.last_error))
        self.after(0, lambda: self._apply_refresh_snapshot(snapshot))

    def _apply_refresh_snapshot(self, snapshot: list[tuple[str, str, str]]) -> None:
        problems = []
        states = []
        for service_name, state, last_error in snapshot:
            states.append(state)
            row = self.rows[service_name]
            row["led"].itemconfigure(row["dot"], fill=self.colors[state])
            row["status"].configure(text=self.labels[state])
            if state == "problem":
                problems.append(f"{service_name}: {last_error}")

        if problems:
            self.message.configure(text="; ".join(problems))
        elif any(state == "stopping" for state in states):
            stopping = ", ".join(service_name for service_name, state, _ in snapshot if state == "stopping")
            self.message.configure(text=f"{stopping} stopping...")
        elif any(state == "starting" for state in states):
            starting = ", ".join(service_name for service_name, state, _ in snapshot if state == "starting")
            self.message.configure(text=f"{starting} starting...")
        elif all(state == "running" for state in states):
            self.message.configure(text="Backend and frontend are running.")

        self._refresh_in_progress = False
        if self._refresh_pending:
            self._refresh_pending = False
            self.after(50, self.refresh_status)
        else:
            self.after(2500, self.refresh_status)

    def on_close(self) -> None:
        self._stop_requested = True
        self._stop_services_worker()
        self.destroy()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--auto-start", action="store_true")
    parser.add_argument("--start-services", action="store_true")
    parser.add_argument("--stop-services", action="store_true")
    parser.add_argument("--restart-services", action="store_true")
    args = parser.parse_args()

    if args.start_services:
        raise SystemExit(run_service_action("start"))
    if args.stop_services:
        raise SystemExit(run_service_action("stop"))
    if args.restart_services:
        raise SystemExit(run_service_action("restart"))

    if sys.platform == "win32":
        kernel32 = ctypes.windll.kernel32
        mutex = kernel32.CreateMutexW(None, False, WIDGET_MUTEX_NAME)
        already_running = kernel32.GetLastError() == 183
        if already_running:
            hwnd = ctypes.windll.user32.FindWindowW(None, WIDGET_WINDOW_TITLE)
            if hwnd:
                ctypes.windll.user32.ShowWindowAsync(hwnd, 9)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            sys.exit(0)
    else:
        mutex = None

    try:
        widget = StatusWidget()
        if args.auto_start:
            widget.after(250, widget.start_all)
        widget.mainloop()
    finally:
        if sys.platform == "win32" and mutex:
            ctypes.windll.kernel32.CloseHandle(mutex)
