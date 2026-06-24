@echo off
setlocal

call :kill_port 5173 "frontend"
call :kill_port 8000 "backend"

echo MultiPlanner stop sequence finished.
exit /b 0

:kill_port
set "PORT=%~1"
set "LABEL=%~2"
set "PID="

for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":%PORT%" ^| findstr "LISTENING"') do (
  set "PID=%%P"
  goto :kill_found
)

echo No %LABEL% listener found on port %PORT%.
exit /b 0

:kill_found
echo Stopping %LABEL% on port %PORT% ^(PID %PID%^)^...
taskkill /PID %PID% /T /F >nul 2>&1
if errorlevel 1 (
  echo Failed to stop PID %PID% on port %PORT%.
) else (
  echo Stopped %LABEL% on port %PORT%.
)
exit /b 0
