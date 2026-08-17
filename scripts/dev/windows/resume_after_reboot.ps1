param([switch]$RunSmoke)
$ErrorActionPreference = 'Stop'
$probeError = $null
try {
    $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
    $freeGb = [math]::Round(([double]$os.FreeVirtualMemory / 1MB), 2)
    $pagefiles = @(Get-CimInstance Win32_PageFileUsage -ErrorAction SilentlyContinue)
} catch {
    $probeError = $_.Exception.Message
    $freeGb = $null
    $pagefiles = @()
}
$ready = ($freeGb -ge 2 -and $pagefiles.Count -gt 0)
$report = [ordered]@{
    identity = (whoami)
    free_virtual_memory_gb = $freeGb
    active_pagefile_count = $pagefiles.Count
    ready = $ready
    probe_error = $probeError
}
$out = Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..')).Path 'workspace/results/post_reboot_readiness.json'
New-Item -ItemType Directory -Force (Split-Path $out) | Out-Null
$report | ConvertTo-Json | Set-Content -LiteralPath $out -Encoding utf8
$report | ConvertTo-Json
if (-not $ready) {
    Write-Output 'Pagefile is not ready or the probe lacked permission; no provider call was made.'
    exit 2
}
if ($RunSmoke) {
    & (Join-Path $PSScriptRoot 'run_authorized_matched.ps1') -TaskId hello-world -MaxTasks 1 -RunRoot workspace/results/official_post_reboot_smoke -MaxOutputTokens 1000 -MaxTotalTokens 6000 -MaxToolCalls 30 -MaxSteps 3
    exit $LASTEXITCODE
}
