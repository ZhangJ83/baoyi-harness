# Resume after Windows restart

The provider and Docker setup are already configured for the `zzz` account.
After Windows restarts, run the following from an elevated PowerShell window:

```powershell
cd E:\project\agent\xiaopu
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File benchmarks\zzz_pagefile_probe.ps1
cmd /d /c benchmarks\run_zzz_one_task_v2.cmd
```

The first command must show a non-empty pagefile usage and more than 2 GB of
free virtual memory.  The second command runs one official `hello-world`
trial with a 6k total-token cap and writes the budget ledger.  It is a chain
verification smoke, not benchmark evidence for competitor superiority.
