$items = Get-CimInstance Win32_Process
$items | Where-Object { $_.Name -in @('python.exe','powershell.exe','cmd.exe') -and $_.CommandLine -match 'xiaopu|terminal_bench|run_authorized' } |
  Select-Object ProcessId,ParentProcessId,Name,CommandLine |
  Format-List
