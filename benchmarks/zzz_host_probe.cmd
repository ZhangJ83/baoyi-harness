@echo off
cd /d E:\project\agent\xiaopu
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File benchmarks\zzz_host_probe.ps1 > workspace\results\zzz_host_probe_latest.log 2>&1
