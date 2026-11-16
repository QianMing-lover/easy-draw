@echo off
powershell -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'python.exe' -and $_.CommandLine -match 'ComfyUI.*main\.py|app[.]py') -or $_.Name -eq 'llama-server.exe' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host ('stopped: ' + $_.Name) }"
echo EasyDraw services (Qwen + ComfyUI + UI) have been stopped.
pause
