@echo off
cd /d E:\project\agent\xiaopu
(
 echo identity=%USERNAME%
 echo === matching processes ===
 powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File benchmarks\zzz_process_probe.ps1
 echo === stop stale project eval ===
 powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File benchmarks\zzz_stop_stale_eval.ps1
 echo === containers ===
 docker ps -a --format "{{.ID}}|{{.Names}}|{{.Status}}"
) > workspace\results\zzz_cleanup_eval.log 2>&1
