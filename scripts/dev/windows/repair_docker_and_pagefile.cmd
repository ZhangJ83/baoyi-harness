@echo off
setlocal
net session >nul 2>&1
if not "%errorlevel%"=="0" (
  echo Requesting administrator privileges...
  powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs -Wait"
  exit /b %errorlevel%
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0repair_docker_desktop.ps1" -ConfigurePagefile
if errorlevel 1 (
  echo Combined Docker/pagefile repair failed.
  powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0diagnose_docker_desktop.ps1"
  exit /b 1
)
echo Combined repair finished. Restart Windows before running the benchmark.
pause
