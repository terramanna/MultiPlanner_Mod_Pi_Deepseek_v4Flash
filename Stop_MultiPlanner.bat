@echo off
setlocal

set "REPO_ROOT=%~dp0"
set "PYTHON=%REPO_ROOT%.venv\Scripts\python.exe"
set "PYTHONW=%REPO_ROOT%.venv\Scripts\pythonw.exe"

if not exist "%PYTHONW%" (
  echo Missing virtual environment: "%REPO_ROOT%\.venv"
  echo Run scripts\bootstrap_local.ps1 first.
  exit /b 1
)

call "%PYTHONW%" "%REPO_ROOT%scripts\multiplanner_status_widget.py" --stop-services
echo MultiPlanner stop sequence finished.
exit /b %ERRORLEVEL%
