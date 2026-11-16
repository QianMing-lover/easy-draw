# EasyDraw 一键启动: Qwen 本地大模型 + ComfyUI 后端 + 网页UI + 自动开浏览器
$comfyDir  = "C:\AI\ComfyUI"
$uiDir     = "C:\AI\easy-ui"
$py        = "$comfyDir\venv\Scripts\python.exe"
$qwenExe   = "C:\Users\ZE XUAN\llama.cpp\llama-server.exe"
$qwenModel = "C:\Users\ZE XUAN\models\Qwen3.5-9B-abliterated-Q4_K_M.gguf"

function Test-Port([int]$p) {
    (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) -ne $null
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Easy Draw 启动程序 (全栈三件套)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ---- 1. Qwen 本地大模型 (8080, 供提示词转换) ----
if (Test-Port 8080) {
    Write-Host "[OK] Qwen 转换模型已在运行，跳过" -ForegroundColor Green
} elseif (Test-Path $qwenExe) {
    Write-Host "[..] 启动 Qwen 本地大模型 (9B, 部分层进显卡, 余量给生图)"
    Start-Process -FilePath $qwenExe `
        -ArgumentList "-m", "`"$qwenModel`"", "--host", "127.0.0.1", "--port", "8080", "-ngl", "20", "-c", "4096" `
        -WorkingDirectory (Split-Path $qwenExe) -WindowStyle Minimized
} else {
    Write-Host "[跳过] 未找到 llama-server.exe，转换功能将使用云端 API" -ForegroundColor Yellow
}

# ---- 2. ComfyUI (8188, 出图后端) ----
if (Test-Port 8188) {
    Write-Host "[OK] ComfyUI 后端已在运行，跳过" -ForegroundColor Green
} elseif (Test-Path $py) {
    Write-Host "[..] 启动 ComfyUI 后端"
    Start-Process -FilePath $py -ArgumentList "main.py","--disable-auto-launch" `
        -WorkingDirectory $comfyDir -WindowStyle Minimized
} else {
    Write-Host "[错误] 找不到 venv：$py" -ForegroundColor Red
    exit 1
}

# ---- 3. 网页UI (8190) ----
if (Test-Port 8190) {
    Write-Host "[OK] 网页UI已在运行，跳过" -ForegroundColor Green
} else {
    Write-Host "[..] 启动网页UI服务"
    Start-Process -FilePath $py -ArgumentList "app.py" `
        -WorkingDirectory $uiDir -WindowStyle Minimized
}

# ---- 等待就绪 ----
Write-Host "[..] 等待服务就绪（Qwen 加载 5GB 模型 + ComfyUI 初始化 CUDA，约 30-90 秒）..."
$okQ = $false; $okA = $false; $okB = $false
foreach ($i in 1..120) {
    if (-not $okQ -and (Test-Port 8080)) { $okQ = $true; Write-Host "  [OK] Qwen 转换模型就绪" -ForegroundColor Green }
    if (-not $okA -and (Test-Port 8188)) { $okA = $true; Write-Host "  [OK] ComfyUI 后端就绪" -ForegroundColor Green }
    if (-not $okB -and (Test-Port 8190)) { $okB = $true; Write-Host "  [OK] 网页UI就绪" -ForegroundColor Green }
    if ($okA -and $okB) { break }
    Start-Sleep -Seconds 1
}

if ($okB) {
    if ($okQ) { Write-Host "  提示词转换模式: 本地 Qwen（离线可用）" } else { Write-Host "  提示词转换模式: 暂用云端 API（Qwen 仍在加载，首次约 2-4 分钟，之后自动可用）" }
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  正在打开浏览器..." -ForegroundColor Green
    Start-Process "http://127.0.0.1:8190"
    Write-Host "  画图地址: http://127.0.0.1:8190"
    Write-Host "  本窗口可以关闭（服务在后台最小化运行）"
    Write-Host "========================================" -ForegroundColor Cyan
} else {
    Write-Host "[错误] 120 秒内 UI 未就绪。查看任务栏最小化窗口的报错信息" -ForegroundColor Red
    if (-not $okB) { exit 1 }
}
