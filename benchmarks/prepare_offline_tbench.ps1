param([string]$OutRoot='workspace/results/offline_tbench_tasks')
$ErrorActionPreference='Stop'
$source=(Resolve-Path '..\official_refs\terminal-bench\original-tasks').Path
if(Test-Path $OutRoot){Remove-Item -LiteralPath $OutRoot -Recurse -Force}
New-Item -ItemType Directory -Force $OutRoot | Out-Null
$taskRoot=Join-Path $OutRoot 'original-tasks'
New-Item -ItemType Directory -Force $taskRoot | Out-Null
foreach($task in @('hello-world','fix-permissions')){
  $dst=Join-Path $taskRoot $task
  Copy-Item -LiteralPath (Join-Path $source $task) -Destination $dst -Recurse
  $docker=Join-Path $dst 'Dockerfile'
  $text=Get-Content $docker -Raw
  $text=$text -replace 'ghcr.io/laude-institute/t-bench/python-3-13:20250620','xiaopu-tbench-offline:python'
  $text=$text -replace 'ghcr.io/laude-institute/t-bench/ubuntu-24-04:20250624','xiaopu-tbench-offline:ubuntu'
  Set-Content -LiteralPath $docker -Value $text -Encoding UTF8
}
Write-Output (Resolve-Path $OutRoot).Path
