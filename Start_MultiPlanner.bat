@echo off
setlocal

set "REPO_ROOT=%~dp0"
cd /d "%REPO_ROOT%"

if not exist ".venv\Scripts\python.exe" (
  echo Missing virtual environment: "%REPO_ROOT%\.venv"
  echo Run scripts\bootstrap_local.ps1 first.
  pause
  exit /b 1
)

if not exist "apps\web\node_modules" (
  echo Missing frontend dependencies in apps\web\node_modules
  echo Run scripts\bootstrap_local.ps1 first.
  pause
  exit /b 1
)

echo Starting MultiPlanner backend...
start "MultiPlanner API" cmd /k "cd /d "%REPO_ROOT%apps\api" && "%REPO_ROOT%.venv\Scripts\python.exe" -m uvicorn multiplanner_api.main:app --host 127.0.0.1 --port 8000 --reload"

echo Starting MultiPlanner frontend...
start "MultiPlanner Web" cmd /k "cd /d "%REPO_ROOT%apps\web" && npm run dev"

echo Waiting for backend...
powershell -NoProfile -Command ^
  "$deadline=(Get-Date).AddSeconds(25); while((Get-Date) -lt $deadline){ try { $r=Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/healthz' -TimeoutSec 2; if($r.StatusCode -eq 200){ exit 0 } } catch {} Start-Sleep -Milliseconds 800 }; exit 1"

echo Waiting for frontend...
powershell -NoProfile -Command ^
  "$deadline=(Get-Date).AddSeconds(25); while((Get-Date) -lt $deadline){ try { $r=Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:5173' -TimeoutSec 2; if($r.StatusCode -eq 200){ exit 0 } } catch {} Start-Sleep -Milliseconds 800 }; exit 1"

echo Opening browser...
start "" http://127.0.0.1:5173/

echo MultiPlanner launch sequence started.
exit /b 0
