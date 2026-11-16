# Easy Draw 服务启动器: ComfyUI(8188) + 本地LLM(8080), 已运行则跳过
function Test-Port([int]$p) {
    try { $t = New-Object Net.Sockets.TcpClient; $t.Connect('127.0.0.1', $p); $t.Close(); $true }
    catch { $false }
}
if (-not (Test-Port 8188)) {
    Start-Process -FilePath 'C:\AI\ComfyUI\venv\Scripts\python.exe' `
        -ArgumentList 'main.py', '--disable-auto-launch' `
        -WorkingDirectory 'C:\AI\ComfyUI' -WindowStyle Hidden
    Write-Host '[启动] ComfyUI 后台启动中（约20-40秒就绪）'
} else {
    Write-Host '[跳过] ComfyUI 已在运行'
}
if (-not (Test-Port 8080)) {
    $exe = 'C:\Users\ZE XUAN\llama.cpp\llama-server.exe'
    if (Test-Path $exe) {
        # 路径含空格: 参数内需自带双引号
        Start-Process -FilePath $exe `
            -ArgumentList '-m', '"C:\Users\ZE XUAN\models\Qwen3.5-9B-abliterated-Q4_K_M.gguf"',
                          '--host', '127.0.0.1', '--port', '8080', '-ngl', '20', '-c', '4096' `
            -WindowStyle Hidden
        Write-Host '[启动] 本地LLM 后台启动中'
    } else {
        Write-Host '[跳过] 未找到 llama-server.exe'
    }
} else {
    Write-Host '[跳过] 本地LLM 已在运行'
}
