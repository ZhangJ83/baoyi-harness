@echo off
setlocal
cd /d E:\project\agent\xiaopu
if not exist workspace\results mkdir workspace\results
echo Launch identity: %USERNAME% > workspace\results\authorized_launch.log
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File benchmarks\run_authorized_matched.ps1 -IncludeCompetitors -IncludeOpenCode >> workspace\results\authorized_launch.log 2>&1
echo EXIT_CODE=%errorlevel%>> workspace\results\authorized_launch.log
echo.
echo Finished. Log: E:\project\agent\xiaopu\workspace\results\authorized_launch.log
pause
