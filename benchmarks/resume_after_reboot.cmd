@echo off
cd /d E:\project\agent\xiaopu
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File benchmarks\resume_after_reboot.ps1 -RunSmoke
