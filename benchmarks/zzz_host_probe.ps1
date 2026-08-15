$os = Get-CimInstance Win32_OperatingSystem
[pscustomobject]@{
  Identity = (whoami)
  FreeVirtualMemoryGB = [math]::Round(([double]$os.FreeVirtualMemory / 1MB), 2)
  TotalVirtualMemoryGB = [math]::Round(([double]$os.TotalVirtualMemorySize / 1MB), 2)
  DockerServer = (& docker.exe info --format '{{.ServerVersion}}' 2>&1)
}
