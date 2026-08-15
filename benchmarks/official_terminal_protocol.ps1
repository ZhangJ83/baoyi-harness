param(
    [string]$TaskId = 'hello-world',
    [string]$RunId = 'xiaopu_official_terminal_pilot',
    [string]$Out = 'workspace/results/official_tb_xiaopu',
    [int]$MaxTasks = 3,
    [switch]$AllowExpandedSlice
)

$ErrorActionPreference = 'Stop'
$project = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$tb = Join-Path $project '..\official_refs\terminal-bench'
$uv = Join-Path $env:USERPROFILE '.local\bin\uv.exe'
if(-not (Test-Path $uv)){ throw "uv.exe not found at $uv" }
if([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
    $secure = Read-Host 'Enter DeepSeek API Key (hidden)' -AsSecureString
    $key = [System.Net.NetworkCredential]::new('', $secure).Password
    if([string]::IsNullOrWhiteSpace($key)){ throw 'API key cannot be empty' }
    $env:OPENAI_API_KEY = $key
} else {
    Write-Output 'Using OPENAI_API_KEY already present in this session; it will not be printed or persisted.'
}
$env:OPENAI_BASE_URL = 'https://api.deepseek.com'
$env:OPENAI_API_BASE = 'https://api.deepseek.com'
$env:OPENAI_MODEL = 'deepseek-v4-flash'
$env:PYTHONPATH = $project
$env:UV_CACHE_DIR = Join-Path $project '..\uv-cache'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$taskIds = @($TaskId -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
if($taskIds.Count -gt $MaxTasks -and -not $AllowExpandedSlice) {
  throw "Refusing $($taskIds.Count) model-backed tasks; default cap is $MaxTasks. Use -AllowExpandedSlice only with an explicit cost/token budget."
}
$args = @('run','--directory',$tb,'--offline','tb','runs','create',
  '--dataset-path',(Join-Path $tb 'original-tasks'),'--n-concurrent','1',
  '--agent-import-path','agent.terminal_bench_adapter:XiaopuTerminalAgent',
  '--model','openai/deepseek-v4-flash','--agent-kwarg','api_base=https://api.deepseek.com',
  '--agent-kwarg','temperature=0.0','--no-rebuild','--no-cleanup','--no-upload-results',
  '--output-path',(Join-Path $project $Out),'--run-id',$RunId)
foreach($id in $taskIds) { $args += @('--task-id',$id) }
& $uv $args
exit $LASTEXITCODE
