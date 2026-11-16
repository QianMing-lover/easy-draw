@echo off
chcp 65001 >nul
title Easy Draw 桌面版
echo ============================================
echo   Easy Draw 桌面版（exe 原生窗口）
echo   ComfyUI / 本地LLM 未运行时会自动后台启动
echo ============================================
rem --- 服务未启动则静默后台拉起（路径引号问题在 ps1 内处理）---
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\AI\easy-ui\StartServices.ps1"
rem --- 打开打包好的原生窗口 ---
start "" "C:\AI\easy-ui\EasyDraw.exe"
exit
