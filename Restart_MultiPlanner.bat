@echo off
setlocal

cd /d "%~dp0"

call ".\Stop_MultiPlanner.bat"
timeout.exe /t 2 /nobreak >nul
call ".\Start_MultiPlanner.bat"

exit /b 0
