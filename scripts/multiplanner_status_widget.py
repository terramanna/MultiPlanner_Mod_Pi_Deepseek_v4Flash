from __future__ import annotations

import argparse
import ctypes
import sys
import threading
import tkinter as tk
from tkinter import messagebox
import webbrowser

from service_manager import (
    Service,
    build_services,
    environment_issues,
    run_service_action,
    wait_for_services_to_stop,
)

WIDGET_WINDOW_TITLE = "MultiPlanner"
WIDGET_MUTEX_NAME = "Global\\MultiPlannerStatusWidget"


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
