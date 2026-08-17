$ErrorActionPreference = 'Continue'
$identity = whoami 2>$null
$contexts = docker context ls 2>&1 | Out-String
$probe = docker info --format '{{.ServerVersion}}' 2>&1
$probeOk = ($LASTEXITCODE -eq 0)
$processes = @(Get-Process -Name 'Docker Desktop','com.docker.backend' -ErrorAction SilentlyContinue)
$service = Get-Service -Name com.docker.service -ErrorAction SilentlyContinue
$dockerUsers = @()
$dockerUsersError = $null
try {
    $dockerUsers = @(Get-LocalGroupMember -Group 'docker-users' -ErrorAction Stop | Select-Object -ExpandProperty Name)
} catch {
    $dockerUsersError = $_.Exception.Message
}
$currentAccount = $identity
$sameAccount = $dockerUsers -contains $currentAccount
$os = Get-CimInstance Win32_OperatingSystem -ErrorAction SilentlyContinue
$computer = Get-CimInstance Win32_ComputerSystem -ErrorAction SilentlyContinue
$freeVirtualMemoryGb = if ($os) { [math]::Round(([double]$os.FreeVirtualMemory / 1MB), 2) } else { $null }
$automaticManagedPagefile = if ($computer) { [bool]$computer.AutomaticManagedPagefile } else { $null }
$pagefiles = @(Get-CimInstance Win32_PageFileUsage -ErrorAction SilentlyContinue)
$report = [ordered]@{
    identity = $identity
    docker_info_ok = $probeOk
    docker_probe = ($probe | Out-String).Trim()
    contexts = $contexts.Trim()
    docker_process_count = $processes.Count
    service_status = if ($service) { [string]$service.Status } else { $null }
    docker_users = $dockerUsers
    docker_users_probe_error = $dockerUsersError
    current_account_in_docker_users = $sameAccount
    free_virtual_memory_gb = $freeVirtualMemoryGb
    automatic_managed_pagefile = $automaticManagedPagefile
    active_pagefile_count = $pagefiles.Count
    virtual_memory_ready = ($null -ne $freeVirtualMemoryGb -and $freeVirtualMemoryGb -ge 2 -and $pagefiles.Count -gt 0)
    remediation = "Run repair_docker_desktop.ps1 as Administrator from the same interactive Windows account that owns Docker Desktop (currently the docker-users member is typically the zzz account), then reopen the terminal under that account."
}
$report | ConvertTo-Json -Depth 4
