param(
    [string]$BaseTemp = "workspace/pytest-tmp"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

python -m compileall -q agent benchmarks
python -m pytest -q --basetemp $BaseTemp

Write-Output "Offline regression passed. No provider calls were made."
