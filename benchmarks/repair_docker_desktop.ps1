#requires -RunAsAdministrator
param(
    [int]$WaitSeconds = 90,
    [switch]$ConfigurePagefile
)

$ErrorActionPreference = 'Stop'
if ($ConfigurePagefile) {
    & (Join-Path $PSScriptRoot 'repair_pagefile.ps1') -Apply
}
Write-Host 'Resetting WSL and Docker Desktop engine...' -ForegroundColor Cyan
wsl.exe --shutdown
Set-Service -Name com.docker.service -StartupType Automatic -ErrorAction SilentlyContinue
Start-Service -Name com.docker.service -ErrorAction SilentlyContinue

$desktop = Join-Path ${env:ProgramFiles} 'Docker\Docker\Docker Desktop.exe'
if (Test-Path $desktop) {
    $running = Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue
    if (-not $running) { Start-Process -FilePath $desktop }
}

$deadline = (Get-Date).AddSeconds($WaitSeconds)
do {
    Start-Sleep -Seconds 3
    $probe = docker info 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host 'Docker engine is ready.' -ForegroundColor Green
        $probe | Select-String 'Server Version|Operating System|Docker Root Dir'
        exit 0
    }
} while ((Get-Date) -lt $deadline)

Write-Error ('Docker engine is still unavailable. Run this script from the same elevated interactive account that owns Docker Desktop. Last probe: ' + ($probe -join ' '))
exit 1
