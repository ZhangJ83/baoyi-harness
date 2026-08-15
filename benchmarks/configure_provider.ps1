param(
    [switch]$Clear
)

$ErrorActionPreference = "Stop"

if ($Clear) {
    [Environment]::SetEnvironmentVariable("OPENAI_API_KEY", $null, "User")
    [Environment]::SetEnvironmentVariable("OPENAI_BASE_URL", $null, "User")
    [Environment]::SetEnvironmentVariable("OPENAI_MODEL", $null, "User")
    Write-Output "Provider configuration cleared from the current Windows user profile."
    exit 0
}

$secure = Read-Host "Enter DeepSeek API Key (hidden)" -AsSecureString
$key = [System.Net.NetworkCredential]::new("", $secure).Password
if ([string]::IsNullOrWhiteSpace($key)) { throw "API Key cannot be empty." }

[Environment]::SetEnvironmentVariable("OPENAI_API_KEY", $key, "User")
[Environment]::SetEnvironmentVariable("OPENAI_BASE_URL", "https://api.deepseek.com", "User")
[Environment]::SetEnvironmentVariable("OPENAI_MODEL", "deepseek-v4-flash", "User")

$env:OPENAI_API_KEY = $key
$env:OPENAI_BASE_URL = "https://api.deepseek.com"
$env:OPENAI_MODEL = "deepseek-v4-flash"

# Non-secret confirmation marker. The key itself is never written to the
# project; this only proves which interactive account configured the provider.
$status = [ordered]@{
    configured = $true
    identity = (whoami 2>$null)
    base_url = $env:OPENAI_BASE_URL
    model = $env:OPENAI_MODEL
    key_present = $true
    configured_at_utc = (Get-Date).ToUniversalTime().ToString('o')
}
$statusPath = Join-Path (Split-Path $PSScriptRoot -Parent) 'workspace/provider_status.json'
$status | ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding utf8

Write-Output "Provider configured for future PowerShell sessions. The key was not printed or saved in the project."
Write-Output ("Configuration marker written for identity: " + $status.identity)
Write-Output "Open a new terminal before running the pilot. To remove it later:"
Write-Output "powershell -ExecutionPolicy Bypass -File benchmarks/configure_provider.ps1 -Clear"
