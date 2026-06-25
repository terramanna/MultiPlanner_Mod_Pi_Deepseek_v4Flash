@echo off
setlocal

set "REPO_ROOT=%~dp0"
set "PYTHONW=%REPO_ROOT%.venv\Scripts\pythonw.exe"
set "WEB_ROOT=%REPO_ROOT%apps\web"

if not exist "%PYTHONW%" (
  echo Missing virtual environment: "%REPO_ROOT%\.venv"
  echo Run scripts\bootstrap_local.ps1 first.
  exit /b 1
)

if not exist "%WEB_ROOT%\node_modules" (
  echo Missing frontend dependencies in apps\web\node_modules
  echo Run scripts\bootstrap_local.ps1 first.
  exit /b 1
)

start "" "%PYTHONW%" "%REPO_ROOT%scripts\multiplanner_status_widget.py"
exit /b 0
