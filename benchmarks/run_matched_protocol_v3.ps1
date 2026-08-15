param(
    [switch]$DryRun,
    [switch]$Smoke,
    [switch]$AcknowledgeNonScoredSmoke,
    [string]$RunRoot = 'workspace/results/official_matched_v3',
    [string]$RunTag = '',
    [string]$TerminalBenchRoot = ''
)

$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$protocolPath = Join-Path $project 'benchmarks/matched_protocol_v3.json'
$smokeValidationPath = Join-Path $project 'workspace/results/matched_v3_live_smoke_validation.json'
$protocol = Get-Content -LiteralPath $protocolPath -Raw | ConvertFrom-Json
$manifestPath = (Resolve-Path (Join-Path $project $protocol.benchmark.task_manifest)).Path
$taskManifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$tbRoot = if ([string]::IsNullOrWhiteSpace($TerminalBenchRoot)) {
    (Resolve-Path (Join-Path $project '..\official_refs\terminal-bench')).Path
} else { (Resolve-Path $TerminalBenchRoot).Path }
$tbExe = Join-Path $tbRoot '.venv\Scripts\tb.exe'
$dataset = Join-Path $tbRoot 'original-tasks'
if (-not (Test-Path -LiteralPath $tbExe)) { throw "Terminal-Bench executable missing: $tbExe" }
if (-not (Test-Path -LiteralPath $dataset)) { throw "Terminal-Bench dataset missing: $dataset" }

$smokeValidation = if (Test-Path -LiteralPath $smokeValidationPath) {
    Get-Content -LiteralPath $smokeValidationPath -Raw | ConvertFrom-Json
} else { $null }
if (-not $DryRun -and -not $Smoke -and ($null -eq $smokeValidation -or $smokeValidation.smoke_valid -ne $true)) {
    throw 'Confirmatory run refused: no valid non-scored three-system live-smoke report. Run -Smoke -AcknowledgeNonScoredSmoke first.'
}
if ($Smoke -and -not $DryRun -and -not $AcknowledgeNonScoredSmoke) {
    throw 'Smoke runs are discardable and non-scored. Re-run with -Smoke -AcknowledgeNonScoredSmoke.'
}

$credential = if ($env:DEEPSEEK_API_KEY) { $env:DEEPSEEK_API_KEY } elseif ($env:OPENAI_API_KEY) { $env:OPENAI_API_KEY } else { $null }
if (-not $DryRun -and [string]::IsNullOrWhiteSpace($credential)) {
    throw 'No provider credential in the current process. Set DEEPSEEK_API_KEY or OPENAI_API_KEY; this script never prompts, prints, or persists it.'
}
if (-not $DryRun) {
    $dockerServer = docker info --format '{{.ServerVersion}}' 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'Docker Engine is unavailable to this process; stop before spending provider tokens.' }
    foreach ($image in @(
        'ghcr.io/laude-institute/t-bench/python-3-13:20250620',
        'ghcr.io/laude-institute/t-bench/ubuntu-24-04:20250624'
    )) {
        docker image inspect $image *> $null
        if ($LASTEXITCODE -ne 0) { throw "Pinned official image is not cached: $image" }
    }
}
if ($credential) {
    $env:DEEPSEEK_API_KEY = $credential
    $env:OPENAI_API_KEY = $credential
    $env:ANTHROPIC_API_KEY = $credential
}
$env:PYTHONPATH = $project
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

$tasks = @($taskManifest.task_ids)
if ($tasks.Count -ne [int]$protocol.benchmark.n_tasks) { throw 'Frozen task-count mismatch.' }
foreach ($task in $tasks) {
    if (-not (Test-Path -LiteralPath (Join-Path $dataset $task))) { throw "Frozen task missing from dataset: $task" }
}
if ($Smoke) { $tasks = @($tasks[0]) }
$stamp = if ([string]::IsNullOrWhiteSpace($RunTag)) { Get-Date -Format 'yyyyMMdd_HHmmss' } else { $RunTag }
$outputRoot = Join-Path $project $RunRoot
$protocolSha = (Get-FileHash -LiteralPath $protocolPath -Algorithm SHA256).Hash.ToLowerInvariant()
$taskSha = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
$benchmarkHead = (git -C $tbRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve Terminal-Bench commit.' }
if (-not $benchmarkHead.StartsWith([string]$protocol.benchmark.commit)) {
    throw "Terminal-Bench commit mismatch: expected $($protocol.benchmark.commit), observed $benchmarkHead"
}

$systems = @(
    @{ name='xiaopu'; import='agent.terminal_bench_adapter:XiaopuTerminalAgent'; model='openai/deepseek-v4-flash'; version='' },
    @{ name='claude_code'; import='agent.budgeted_installed_agents:BudgetedClaudeCodeAgent'; model='anthropic/deepseek-v4-flash'; version='2.1.224' },
    @{ name='codex'; import='agent.budgeted_installed_agents:BudgetedCodexAgent'; model='openai/deepseek-v4-flash'; version='0.146.1' }
)
$resultPaths = @{}

foreach ($system in $systems) {
    $runId = "$($system.name)_$stamp"
    $systemRoot = Join-Path $outputRoot $system.name
    $runDir = Join-Path $systemRoot $runId
    $resultPaths[$system.name] = Join-Path $runDir 'results.json'
    New-Item -ItemType Directory -Force -Path $runDir | Out-Null
    $runManifest = [ordered]@{
        schema = 'matched-run-manifest-v3'
        system = $system.name
        model = $protocol.shared_model
        protocol_sha256 = $protocolSha
        task_manifest_sha256 = $taskSha
        benchmark_commit = $protocol.benchmark.commit
        observed_benchmark_head = $benchmarkHead
        task_ids = $tasks
        non_scored_smoke = [bool]$Smoke
    }
    $runManifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $runDir 'run_manifest_v3.json') -Encoding utf8
    $args = @('run','--dataset-path',$dataset,'--output-path',$systemRoot,'--run-id',$runId,
        '--n-concurrent','1','--n-attempts','1','--global-agent-timeout-sec','180',
        '--no-rebuild','--no-cleanup','--no-upload-results','--model',$system.model,
        '--agent-import-path',$system.import,
        '--agent-kwarg','max_cumulative_output_tokens=4500',
        '--agent-kwarg','max_agent_wall_seconds=180')
    if ($system.name -eq 'xiaopu') {
        $args += @('--agent-kwarg','budget_protocol=v3','--agent-kwarg','api_base=https://api.deepseek.com',
            '--agent-kwarg','temperature=0.0','--agent-kwarg','max_tool_calls=60','--agent-kwarg','max_steps=50')
    } else {
        $args += @('--agent-kwarg','max_covered_local_tool_calls=60','--agent-kwarg',("version=" + $system.version))
    }
    foreach ($task in $tasks) { $args += @('--task-id',$task) }
    if ($DryRun) {
        Write-Output ("DRY-RUN {0}: {1} {2}" -f $system.name, $tbExe, ($args -join ' '))
        continue
    }
    & $tbExe @args
    if ($LASTEXITCODE -ne 0) { throw "$($system.name) exited with code $LASTEXITCODE" }
}

if (-not $DryRun -and $Smoke) {
    $python = Join-Path $tbRoot '.venv\Scripts\python.exe'
    & $python -m benchmarks.validate_v3_live_smoke `
        --xiaopu $resultPaths.xiaopu --claude-code $resultPaths.claude_code --codex $resultPaths.codex `
        --protocol $protocolPath --out $smokeValidationPath
    if ($LASTEXITCODE -ne 0) { throw 'Live smoke ran but failed the transport/hook validation gate.' }
}
if (-not $DryRun -and -not $Smoke) {
    $python = Join-Path $tbRoot '.venv\Scripts\python.exe'
    & $python -m benchmarks.verify_budget_parity_v3 `
        --xiaopu $resultPaths.xiaopu --claude-code $resultPaths.claude_code --codex $resultPaths.codex `
        --protocol $protocolPath --tasks $manifestPath --out (Join-Path $outputRoot 'budget_parity_v3.json')
    if ($LASTEXITCODE -ne 0) { throw 'Completed trials failed the v3 budget-parity gate.' }
}
$mode = if ($DryRun) { 'dry-run' } elseif ($Smoke) { 'non-scored smoke' } else { 'confirmatory run' }
Write-Output ("v3 {0} prepared under {1}" -f $mode, $outputRoot)
