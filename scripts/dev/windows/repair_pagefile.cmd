@echo off
cd /d E:\project\agent\xiaopu
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File benchmarks\repair_pagefile.ps1 -Apply
pause
