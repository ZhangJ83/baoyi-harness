$procs = Get-CimInstance Win32_Process | Where-Object {
  $_.CommandLine -and
  (
    $_.CommandLine -match 'official_authorized_matched' -or
    $_.CommandLine -match 'run_authorized_matched\.ps1\s+-IncludeCompetitors\s+-IncludeOpenCode'
  ) -and
  $_.CommandLine -notmatch 'zzz_stop_stale_eval|zzz_process_probe'
}
$ids = @($procs | ForEach-Object { [int]$_.ProcessId })
foreach ($id in $ids) {
  try { & taskkill.exe /PID $id /T /F | Out-Null } catch {}
}
$staleContainers = @(
  'hello-world-1-of-1-opencode',
  'extract-safely-1-of-1-opencode',
  'fix-permissions-1-of-1-opencode'
)
foreach ($container in $staleContainers) {
  $exists = & docker.exe ps -a --quiet --filter "name=^/$container$" 2>$null
  if ($exists) { & docker.exe rm -f $container 2>$null | Out-Null }
}
Write-Output ("stopped=" + ($ids -join ','))
