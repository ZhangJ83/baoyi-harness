@echo off
setlocal
cd /d E:\project\agent\xiaopu
if not exist workspace\results mkdir workspace\results
echo identity=%USERNAME%> workspace\results\zzz_one_task_v2.log
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File benchmarks\run_authorized_matched.ps1 -TaskId hello-world -MaxTasks 1 -RunRoot workspace/results/official_zzz_one_task_v2 -MaxOutputTokens 1000 -MaxTotalTokens 6000 -MaxToolCalls 30 -MaxSteps 3 >> workspace\results\zzz_one_task_v2.log 2>&1
echo EXIT_CODE=%errorlevel%>> workspace\results\zzz_one_task_v2.log
