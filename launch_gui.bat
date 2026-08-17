@echo off
chcp 65001 >nul
title 小朴 Agent GUI 启动器
cd /d "%~dp0"
echo ========================================================
echo   正在彻底重启小朴 Xiaopu Agent (Web GUI)...
echo ========================================================
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8765 ^| findstr LISTENING') do (
    echo 正在终止旧版进程 PID: %%a ...
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul
echo 正在启动最新服务...
start "" "E:\080000software\080900_Miniconda\miniconda3\pythonw.exe" -m agent.gui --workspace "E:\project\agent\xiaopu\workspace"
echo 启动完成！已在独立窗口打开小朴 Agent。
timeout /t 2 /nobreak >nul
exit
