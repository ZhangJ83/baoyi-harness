param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$cs = Get-CimInstance Win32_ComputerSystem
$os = Get-CimInstance Win32_OperatingSystem
Write-Output "Identity: $(whoami)"
Write-Output "AutomaticManagedPagefile: $($cs.AutomaticManagedPagefile)"
Write-Output ("FreeVirtualMemoryGB: {0:N2}" -f ([double]$os.FreeVirtualMemory / 1MB))
if (-not $Apply) {
    Write-Output 'Dry run only. Re-run with -Apply to enable Windows-managed pagefile.'
    exit 0
}
if (-not $cs.AutomaticManagedPagefile) {
    Set-CimInstance -InputObject $cs -Property @{ AutomaticManagedPagefile = $true } | Out-Null
    Write-Output 'AutomaticManagedPagefile enabled. Windows may require a restart before the new commit limit is visible.'
} else {
    Write-Output 'AutomaticManagedPagefile was already enabled.'
}
$statusPath = Join-Path (Resolve-Path (Join-Path $PSScriptRoot '..')).Path 'workspace/pagefile_status.json'
$status = [ordered]@{
    automatic_managed_pagefile = $true
    configured_at_utc = [DateTime]::UtcNow.ToString('o')
    reboot_required_for_verification = $true
    note = 'Re-run zzz_pagefile_probe.ps1 after Windows restart.'
}
New-Item -ItemType Directory -Force (Split-Path $statusPath) | Out-Null
$status | ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding utf8
Write-Output "Non-secret status written to $statusPath"
