Write-Output "=== identity ==="
whoami
Write-Output "=== computer system ==="
Get-CimInstance Win32_ComputerSystem | Select-Object AutomaticManagedPagefile,TotalPhysicalMemory
Write-Output "=== pagefile settings ==="
Get-CimInstance Win32_PageFileSetting | Select-Object Name,InitialSize,MaximumSize
Write-Output "=== pagefile usage ==="
Get-CimInstance Win32_PageFileUsage | Select-Object Name,AllocatedBaseSize,CurrentUsage,PeakUsage
Write-Output "=== virtual memory ==="
Get-CimInstance Win32_OperatingSystem | Select-Object LastBootUpTime,FreeVirtualMemory,TotalVirtualMemorySize
