param(
    [string[]]$TaskId = @('hello-world', 'fix-permissions', 'extract-safely'),
    [string]$RunRoot = 'workspace/results/official_matched',
    [switch]$IncludeCompetitors,
    [switch]$IncludeOpenCode,
    [switch]$Rebuild,
    [switch]$KeepContainers,
    [int]$MaxTasks = 3,
    [switch]$AllowExpandedSlice,
    [int]$MaxTotalTokens = 12000,
    [int]$MaxOutputTokens = 1500,
    [int]$MaxToolCalls = 60,
    [int]$MaxSteps = 3,
    [double]$MinFreeVirtualMemoryGB = 2.0,
    [string]$DatasetRoot = ''
)

$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$tb = if ([string]::IsNullOrWhiteSpace($DatasetRoot)) {
    Join-Path $project '..\official_refs\terminal-bench'
} else {
    (Resolve-Path $DatasetRoot).Path
}
$freeVirtualGB = $null
try {
    $os = Get-CimInstance Win32_OperatingSystem -ErrorAction Stop
    $freeVirtualGB = [math]::Round(([double]$os.FreeVirtualMemory / 1MB), 2)
} catch {
    Write-Warning "Unable to query host virtual memory; continuing with Docker preflight. $($_.Exception.Message)"
}
if ($null -ne $freeVirtualGB -and $freeVirtualGB -lt $MinFreeVirtualMemoryGB) {
    throw "Infrastructure preflight failed: free virtual memory is ${freeVirtualGB} GB, below ${MinFreeVirtualMemoryGB} GB. Stop stale benchmark processes or increase the Windows page file before spending provider tokens."
}
$dockerProbe = docker info --format '{{.ServerVersion}}' 2>&1
if ($LASTEXITCODE -ne 0) {
    $identity = (whoami 2>$null)
    throw "Docker engine unavailable for account '$identity'. Run benchmarks/repair_docker_desktop.ps1 from the same elevated interactive account that owns Docker Desktop, then retry. Probe: $dockerProbe"
}
$uv = Join-Path $env:USERPROFILE '.local\bin\uv.exe'
$tbExecutable = $env:TB_EXECUTABLE
if (-not (Test-Path $uv) -and [string]::IsNullOrWhiteSpace($tbExecutable)) { throw "uv.exe not found at $uv" }
if (-not (Test-Path (Join-Path $tb 'original-tasks'))) { throw "official Terminal-Bench checkout is missing" }

# This runner deliberately shares task IDs, attempts, concurrency, temperature,
# cleanup, and scorer settings. It never writes or prints credentials.
$env:PYTHONPATH = $project
$env:UV_CACHE_DIR = Join-Path $project '..\uv-cache'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$env:OPENAI_BASE_URL = 'https://api.deepseek.com'
$env:OPENAI_MODEL = 'deepseek-v4-flash'
$env:ANTHROPIC_API_KEY = $env:OPENAI_API_KEY
$env:ANTHROPIC_BASE_URL = 'https://api.deepseek.com/anthropic'
$env:ANTHROPIC_MODEL = 'deepseek-v4-flash'
$env:DEEPSEEK_API_KEY = $env:OPENAI_API_KEY
$taskIds = @($TaskId | ForEach-Object { $_ -split ',' } | ForEach-Object { $_.Trim() } | Where-Object { $_ })
if ($taskIds.Count -gt $MaxTasks -and -not $AllowExpandedSlice) {
    throw "Refusing $($taskIds.Count) model-backed tasks; default cap is $MaxTasks. Use -AllowExpandedSlice only with an explicit cost/token budget."
}
foreach ($id in $taskIds) {
    if (-not (Test-Path (Join-Path (Join-Path $tb 'original-tasks') $id))) {
        throw "Unknown official Terminal-Bench task id: $id"
    }
}
$taskArgs = @()
foreach ($id in $taskIds) { $taskArgs += @('--task-id', $id) }

function Invoke-TbSystem([string]$Name, [string]$AgentArgs, [string]$Model) {
    $out = Join-Path $project $RunRoot
    $tbExe = if (-not [string]::IsNullOrWhiteSpace($env:TB_EXECUTABLE)) { $env:TB_EXECUTABLE } else { $null }
    $args = if ($tbExe -and (Test-Path $tbExe)) {
        @('runs', 'create', '--dataset-path', (Join-Path $tb 'original-tasks'), '--n-concurrent', '1')
    } else {
        @('run', '--directory', $tb, '--offline', 'tb', 'runs', 'create', '--dataset-path', (Join-Path $tb 'original-tasks'), '--n-concurrent', '1')
    }
    $args += @(
        '--n-attempts', '1', '--no-upload-results',
        '--output-path', $out, '--run-id', $Name, '--model', $Model)
    if (-not $Rebuild) { $args += '--no-rebuild' }
    if ($KeepContainers) { $args += '--no-cleanup' }
    if ($AgentArgs -eq 'xiaopu') {
        $args += @('--agent-import-path', 'agent.terminal_bench_adapter:XiaopuTerminalAgent',
            '--agent-kwarg', 'api_base=https://api.deepseek.com', '--agent-kwarg', 'temperature=0.0',
            '--agent-kwarg', "max_total_tokens=$MaxTotalTokens", '--agent-kwarg', "max_output_tokens=$MaxOutputTokens",
            '--agent-kwarg', "max_tool_calls=$MaxToolCalls", '--agent-kwarg', "max_steps=$MaxSteps")
    } elseif ($AgentArgs -eq 'opencode') {
        $args += @('--agent', $AgentArgs)
    } else {
        $args += @('--agent', $AgentArgs)
    }
    $args += $taskArgs
    Write-Output "Running $Name with the fixed matched protocol..."
    if ($tbExe -and (Test-Path $tbExe)) {
        Push-Location $tb
        try { & $tbExe $args } finally { Pop-Location }
    } else {
        & $uv $args
    }
    if ($LASTEXITCODE -ne 0) { throw "$Name exited with code $LASTEXITCODE" }
}

if ([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
    throw 'Set OPENAI_API_KEY in the current session before running; this script does not prompt or persist keys.'
}
Invoke-TbSystem 'xiaopu' 'xiaopu' 'openai/deepseek-v4-flash'

if ($IncludeCompetitors) {
    if ([string]::IsNullOrWhiteSpace($env:ANTHROPIC_API_KEY)) {
        throw 'IncludeCompetitors requires ANTHROPIC_API_KEY for the official Claude Code agent.'
    }
    if ([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
        throw 'IncludeCompetitors requires OPENAI_API_KEY for the official Codex agent.'
    }
    Invoke-TbSystem 'claude_code' 'claude-code' 'anthropic/deepseek-v4-flash'
    Invoke-TbSystem 'codex' 'codex' 'openai/deepseek-v4-flash'
}

if ($IncludeOpenCode) {
    Invoke-TbSystem 'opencode' 'opencode' 'deepseek/deepseek-v4-flash'
}

Write-Output "Matched runs written under $(Join-Path $project $RunRoot)."
