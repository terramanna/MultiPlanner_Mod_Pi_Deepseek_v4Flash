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

call "%PYTHONW%" "%REPO_ROOT%scripts\multiplanner_status_widget.py" --restart-services
if errorlevel 1 exit /b %ERRORLEVEL%

timeout.exe /t 2 /nobreak >nul
call "%REPO_ROOT%Start_MultiPlanner.bat"
exit /b 0
