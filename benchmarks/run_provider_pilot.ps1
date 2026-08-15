param(
    [ValidateSet("terminal_bench", "swe_bench_verified", "pptbench")]
    [string]$Suite = "swe_bench_verified",
    [int]$Limit = 1,
    [int]$MaxTokens = 8000,
    [string]$Out = "workspace/results/provider_pilot_latest.json"
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

if ([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
    $secure = Read-Host "Enter DeepSeek API Key (hidden)" -AsSecureString
    $env:OPENAI_API_KEY = [System.Net.NetworkCredential]::new("", $secure).Password
} else {
    Write-Output "Using OPENAI_API_KEY already present in this session; it will not be printed or persisted."
}
$env:OPENAI_BASE_URL = "https://api.deepseek.com"
$env:OPENAI_MODEL = "deepseek-v4-flash"
$env:API_RETRIES = "0"
$env:OPENAI_MAX_TOKENS = "800"

python benchmarks/run_mini.py `
    --suite $Suite `
    --limit $Limit `
    --max-steps 10 `
    --max-tool-calls 30 `
    --workspace workspace/provider_pilot `
    --out $Out `
    --max-total-tokens $MaxTokens
