@echo off
setlocal

set "REPO_ROOT=%~dp0"
set "PYTHON=%REPO_ROOT%.venv\Scripts\python.exe"
set "PYTHONW=%REPO_ROOT%.venv\Scripts\pythonw.exe"
set "NODE=%REPO_ROOT%.venv\tools\node\node.exe"
set "WEB_ROOT=%REPO_ROOT%apps\web"

cd /d "%REPO_ROOT%"

if not exist "%PYTHON%" (
  echo Missing virtual environment: "%REPO_ROOT%\.venv"
  echo Run scripts\bootstrap_local.ps1 first.
  pause
  exit /b 1
)

if not exist "%NODE%" (
  echo Missing project-local Node runtime: "%NODE%"
  echo Run scripts\bootstrap_local.ps1 first.
  pause
  exit /b 1
)

if not exist "%WEB_ROOT%\node_modules" (
  echo Missing frontend dependencies in apps\web\node_modules
  echo Run scripts\bootstrap_local.ps1 first.
  pause
  exit /b 1
)

start "" "%PYTHONW%" "%REPO_ROOT%scripts\multiplanner_status_widget.py" --auto-start
exit /b 0
