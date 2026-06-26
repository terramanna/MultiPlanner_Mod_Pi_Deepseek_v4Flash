from __future__ import annotations

from collections import defaultdict
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parent.parent
API_ROOT = REPO_ROOT / "apps" / "api"
WEB_ROOT = REPO_ROOT / "apps" / "web"
VENV_PYTHON = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
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
                ["netstat", "-ano", "-p", "tcp"],
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
            subprocess.run(
                ["kill", str(pid)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
            )
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
