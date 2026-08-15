param([string]$Out='workspace/results/provider_preflight.json')
$ErrorActionPreference='Continue'
$openai = -not [string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)
$deepseek = -not [string]::IsNullOrWhiteSpace($env:DEEPSEEK_API_KEY)
$server = docker info --format '{{.ServerVersion}}' 2>$null
$dockerReady = ($LASTEXITCODE -eq 0)
$images = @(
  'ghcr.io/laude-institute/t-bench/python-3-13:20250620',
  'ghcr.io/laude-institute/t-bench/ubuntu-24-04:20250624'
)
$imageRows = @($images | ForEach-Object {
  [pscustomobject]@{image=$_; cached=[bool](docker image inspect $_ 2>$null)}
})
$cached = (@($imageRows | Where-Object {$_.cached}).Count -eq $images.Count)
$ready = (($openai -or $deepseek) -and $dockerReady -and $cached)
$next = if(-not ($openai -or $deepseek)) {'inject authorized provider credential in current process'}
  elseif(-not $dockerReady) {'start Docker Engine with the benchmark account'}
  elseif(-not $cached) {'pull/import pinned official images'}
  else {'run the authorized matched slice'}
$result = [pscustomobject]@{
  kind='provider_preflight_v1'; provider_credential_present=($openai -or $deepseek)
  docker_ready=$dockerReady; docker_server=($server | Out-String).Trim()
  official_images=$imageRows; runnable_without_pull=($dockerReady -and $cached)
  ready=$ready; next_action=$next
}
$parent=Split-Path -Parent $Out; if($parent){New-Item -ItemType Directory -Force $parent | Out-Null}
$result | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 $Out
$result | ConvertTo-Json -Depth 6
