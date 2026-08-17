@echo off
setlocal
net session >nul 2>&1
if not "%errorlevel%"=="0" (
  echo Requesting administrator privileges...
  powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs -Wait"
  exit /b %errorlevel%
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0repair_docker_desktop.ps1"
if errorlevel 1 (
  echo Docker repair failed. Keep this administrator window open and inspect the error above.
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0diagnose_docker_desktop.ps1"
  exit /b 1
)
echo Docker repair finished. Running final engine probe...
docker info --format "Server={{.ServerVersion}} OS={{.OperatingSystem}}"
if errorlevel 1 (
  echo The elevated repair completed, but this shell still cannot access Docker.
  echo Reopen the terminal under the same Windows account that owns Docker Desktop.
  exit /b 1
)
