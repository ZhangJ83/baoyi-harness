param(
    [string[]]$TaskId = @('hello-world', 'fix-permissions', 'extract-safely'),
    [string]$RunRoot = 'workspace/results/official_authorized_matched',
    [switch]$IncludeCompetitors,
    [switch]$IncludeOpenCode,
    [switch]$Rebuild,
    [switch]$KeepContainers,
    [switch]$AllowExpandedSlice,
    [switch]$ApproveProviderSpend,
    [int]$MaxTasks = 3,
    [int]$MaxTotalTokens = 12000,
    [int]$MaxOutputTokens = 1500,
    [int]$MaxToolCalls = 60,
    [int]$MaxSteps = 3,
    [double]$MinFreeVirtualMemoryGB = 2.0
)

$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $project

# Prevent accidental concurrent benchmark launches.  A crashed Terminal-Bench
# run can leave tb.exe and compose containers alive; starting another run in
# that state commonly exhausts the Windows page file and obscures the real
# agent result.  We only inspect command lines and never terminate anything.
try {
    $selfPid = $PID
    $active = Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
        $_.ProcessId -ne $selfPid -and
        $_.Name -in @('powershell.exe', 'python.exe') -and
        $_.CommandLine -match 'run_authorized_matched\.ps1|run_official_matched\.ps1|official_authorized_matched' -and
        $_.CommandLine -notmatch 'Get-CimInstance'
    }
    if (@($active).Count -gt 0) {
        $ids = (@($active | Select-Object -ExpandProperty ProcessId) -join ',')
        throw "Another Xiaopu/official evaluation appears active (PIDs: $ids). Let it finish or explicitly clean it before starting a new run."
    }
} catch [System.UnauthorizedAccessException] {
    # Restricted non-admin shells may not query command lines; continue with
    # the Docker preflight below rather than failing for an observability check.
}

$dockerProbe = docker info --format '{{.ServerVersion}}' 2>&1
if ($LASTEXITCODE -ne 0) {
    $identity = (whoami 2>$null)
    throw "Docker engine unavailable for account '$identity'. Run benchmarks/repair_docker_desktop.ps1 from the same elevated interactive account that owns Docker Desktop, then retry. Probe: $dockerProbe"
}

$taskIds = @($TaskId | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
if ($taskIds.Count -gt $MaxTasks -and -not $AllowExpandedSlice) {
    throw "Expanded slice requires -AllowExpandedSlice. Requested $($taskIds.Count) tasks, cap is $MaxTasks."
}
if ($taskIds.Count -gt $MaxTasks -and -not $ApproveProviderSpend) {
    throw 'Expanded provider execution requires explicit -ApproveProviderSpend and a token cap.'
}
if ($MaxTotalTokens -le 0 -or $MaxOutputTokens -le 0 -or $MaxToolCalls -le 0 -or $MaxSteps -le 0) {
    throw 'All token/tool/step caps must be positive.'
}

# One hidden prompt only when the process has no key. The key is held in this
# process and passed to provider adapters; it is never written to the project.
if ([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
    $secure = Read-Host 'Enter DeepSeek API Key (hidden)' -AsSecureString
    $env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new('', $secure).Password
}
if ([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) { throw 'API key cannot be empty.' }

$env:OPENAI_BASE_URL = 'https://api.deepseek.com'
$env:OPENAI_MODEL = 'deepseek-v4-flash'
$env:ANTHROPIC_API_KEY = $env:OPENAI_API_KEY
$env:ANTHROPIC_BASE_URL = 'https://api.deepseek.com/anthropic'
$env:ANTHROPIC_MODEL = 'deepseek-v4-flash'
$env:DEEPSEEK_API_KEY = $env:OPENAI_API_KEY
$env:API_RETRIES = '0'

$args = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
    (Join-Path $PSScriptRoot 'run_official_matched.ps1'),
    '-TaskId', ($taskIds -join ','), '-RunRoot', $RunRoot,
    '-MaxTasks', $MaxTasks, '-MaxTotalTokens', $MaxTotalTokens,
    '-MaxOutputTokens', $MaxOutputTokens, '-MaxToolCalls', $MaxToolCalls,
    '-MaxSteps', $MaxSteps, '-MinFreeVirtualMemoryGB', $MinFreeVirtualMemoryGB)
if ($IncludeCompetitors) { $args += '-IncludeCompetitors' }
if ($IncludeOpenCode) { $args += '-IncludeOpenCode' }
if ($Rebuild) { $args += '-Rebuild' }
if ($KeepContainers) { $args += '-KeepContainers' }
if ($AllowExpandedSlice) { $args += '-AllowExpandedSlice' }

& powershell.exe @args
if ($LASTEXITCODE -ne 0) { throw "Authorized matched evaluation exited with code $LASTEXITCODE" }
Write-Output "Authorized matched evaluation completed. Model: deepseek-v4-flash; results: $RunRoot"
