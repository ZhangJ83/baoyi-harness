@echo off
cd /d E:\project\agent\xiaopu
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File benchmarks\zzz_pagefile_probe.ps1 > workspace\results\zzz_pagefile_probe.log 2>&1
