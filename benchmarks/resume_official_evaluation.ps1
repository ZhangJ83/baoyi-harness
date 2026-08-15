param(
    [string[]]$TaskId = @('hello-world', 'fix-permissions', 'extract-safely'),
    [string]$RunId = ('xiaopu_official_' + (Get-Date -Format 'yyyyMMdd_HHmmss')),
    [string]$Out = 'workspace/results/official_tb_xiaopu',
    [switch]$RunSweSmoke,
    [int]$MaxTasks = 3,
    [switch]$AllowExpandedSlice
)

$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $project
$env:HF_HOME = Join-Path $project 'workspace/hf_cache'
$env:HF_DATASETS_CACHE = Join-Path $env:HF_HOME 'datasets'
$env:HF_HUB_CACHE = Join-Path $env:HF_HOME 'hub'

$dockerProbe = docker info --format '{{.ServerVersion}}' 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Docker engine unavailable. Run repair_docker_desktop.ps1 as the Docker Desktop owner, then retry. Probe: $dockerProbe"
}
$args = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
    (Join-Path $PSScriptRoot 'official_terminal_protocol.ps1'))
$args += @('-TaskId', ($TaskId -join ','), '-RunId', $RunId, '-Out', $Out, '-MaxTasks', $MaxTasks)
if($AllowExpandedSlice) { $args += '-AllowExpandedSlice' }
& powershell.exe @args
if ($LASTEXITCODE -ne 0) { throw "Official Terminal-Bench runner exited with code $LASTEXITCODE" }

if ($RunSweSmoke) {
    & python benchmarks/official_swe_readiness.py --out workspace/results/official_swe_verified/resume_readiness.json
    if ($LASTEXITCODE -ne 0) { throw "SWE-bench readiness exited with code $LASTEXITCODE" }
    Write-Output 'SWE-bench metadata readiness completed; official container scoring remains a separate evaluator step.'
}
Write-Output 'Official evaluation continuation completed.'
