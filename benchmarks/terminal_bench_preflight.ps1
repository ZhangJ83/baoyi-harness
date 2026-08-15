param([string]$Out='workspace/results/terminal_bench_preflight.json')
$ErrorActionPreference='Continue'
$images=@(
  'ghcr.io/laude-institute/t-bench/python-3-13:20250620',
  'ghcr.io/laude-institute/t-bench/ubuntu-24-04:20250624'
)
$rows=@()
foreach($image in $images){
  $found = [bool](docker image inspect $image 2>$null)
  $rows += [pscustomobject]@{image=$image; cached=$found}
}
$dockerOk = $false
$server = $null
$probe = docker info --format '{{.ServerVersion}}' 2>&1
if($LASTEXITCODE -eq 0){$dockerOk=$true;$server=($probe|Out-String).Trim()}
$result=[pscustomobject]@{
  kind='terminal_bench_preflight'
  docker_ready=$dockerOk
  docker_server=$server
  official_images=$rows
  runnable_without_pull=($dockerOk -and (@($rows|Where-Object {-not $_.cached}).Count -eq 0))
  next_action=if(-not $dockerOk){'start Docker Engine'}elseif(@($rows|Where-Object {-not $_.cached}).Count -gt 0){'pull or import official images'}else{'run authorized slice'}
}
$parent=Split-Path -Parent $Out
if($parent){New-Item -ItemType Directory -Force $parent | Out-Null}
$result | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $Out
$result | ConvertTo-Json -Depth 5
