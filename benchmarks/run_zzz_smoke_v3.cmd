@echo off
setlocal
cd /d E:\project\agent\xiaopu
if not exist workspace\results mkdir workspace\results
echo identity=%USERNAME%> workspace\results\zzz_smoke_v3.log
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File benchmarks\run_authorized_matched.ps1 -RunRoot workspace/results/official_zzz_smoke_v3 -MaxOutputTokens 3000 -MaxTotalTokens 24000 -MaxToolCalls 80 -MaxSteps 5 >> workspace\results\zzz_smoke_v3.log 2>&1
echo EXIT_CODE=%errorlevel%>> workspace\results\zzz_smoke_v3.log
