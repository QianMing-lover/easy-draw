@echo off
rem Easy Draw one-click installer wrapper
chcp 65001 >nul
title Easy Draw Installer
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
echo.
echo Done. Press any key to close.
pause >nul
