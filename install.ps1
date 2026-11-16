# ============================================================
#  Easy Draw 一键全安装器  (install.ps1)
#  安装内容: Python 3.11 · ComfyUI · torch(CUDA) · IPAdapter 节点
#            NoobAI-XL 模型 · Easy Draw 应用 · 可选本地 LLM
#  不含: 你的个人 api_config.json (自动从 example 生成)
# ============================================================
param(
    [string]$InstallDir = "C:\AI",
    [string]$Proxy = "",
    [string]$PipMirror = "https://pypi.tuna.tsinghua.edu.cn/simple",
    [switch]$SkipModels,
    [switch]$SkipLLM,
    [switch]$SkipBuildExe,
    [switch]$UseOfficialHf,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$APP_REPO = "https://github.com/QianMing-lover/easy-draw.git"
$COMFY_REPO = "https://github.com/comfyanonymous/ComfyUI.git"
$IPADAPTER_NODE = "https://github.com/cubiq/ComfyUI_IPAdapter_plus.git"
$HF = if ($UseOfficialHf) { "https://huggingface.co" } else { "https://hf-mirror.com" }
$PY_VER = "3.11.9"
$PY_URL = "https://www.python.org/ftp/python/$PY_VER/python-$PY_VER-amd64.exe"
$TORCH_INDEX = "https://download.pytorch.org/whl/cu130"
$TORCH_PKG = "torch==2.12.1"

$COMFY = Join-Path $InstallDir "ComfyUI"
$VENV = Join-Path $COMFY "venv"
$VENVPY = Join-Path $VENV "Scripts\python.exe"
$APP = Join-Path $InstallDir "easy-ui"
$LLM_DIR = Join-Path $InstallDir "llama.cpp"

function Say($msg, $color = "White") { Write-Host $msg -ForegroundColor $color }
function Step($n, $msg) { Say "`n[$n/9] $msg" "Cyan" }
function Ok($msg) { Say "  [OK] $msg" "Green" }
function Warn($msg) { Say "  [!] $msg" "Yellow" }
function Die($msg, $hint = "") {
    Say "`n  [X] $msg" "Red"
    if ($hint) { Say "      提示: $hint" "Yellow" }
    exit 1
}
function Run($desc, [scriptblock]$block) {
    if ($DryRun) { Say "  (dry-run) $desc" "DarkGray"; return }
    & $block
    if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) { Die "$desc 失败 (exit $LASTEXITCODE)" }
}

Say "==============================================" "Magenta"
Say "   Easy Draw 一键全安装器" "Magenta"
Say "   本地 AI 生图工作台 · NoobAI-XL v-pred" "Magenta"
Say "==============================================" "Magenta"
Say "  安装目录: $InstallDir"
Say "  下载源  : $(if ($UseOfficialHf) {'HuggingFace 官方'} else {'hf-mirror 国内镜像'})"
Say "  预计体积: ~12GB (模型 9.9GB + 依赖 ~2GB)"
Say "  预计耗时: 30-90 分钟 (取决于网速)"
if ($DryRun) { Say "  *** DRY-RUN 模式: 只打印步骤不执行 ***" "Yellow" }

# ---------- 1. 环境检查 ----------
Step 1 "环境检查"
if (-not (Test-Path $InstallDir)) {
    Run "创建目录 $InstallDir" { New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null }
}
$drive = Split-Path -Qualifier $InstallDir
$free = [math]::Round((Get-PSDrive ($drive.TrimEnd(':'))).Free / 1GB, 1)
Say "  磁盘剩余: $free GB"
if ($free -lt 15) { Warn "剩余空间不足 15GB，模型下载可能失败" }

# 代理自动探测 (国内环境 github 直连可能不通)
if (-not $Proxy) {
    try {
        $t = Test-NetConnection -ComputerName "github.com" -Port 443 -WarningAction SilentlyContinue
        if (-not $t.TcpTestSucceeded) {
            foreach ($p in @(1088, 7890, 7897, 10809, 1080)) {
                $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
                if ($c) { $Proxy = "http://127.0.0.1:$p"; Warn "github 直连不通，自动使用本机代理 $Proxy"; break }
            }
        }
    } catch {}
}
if ($Proxy) {
    $env:HTTPS_PROXY = $Proxy; $env:HTTP_PROXY = $Proxy
    $env:NO_PROXY = "127.0.0.1,localhost"
    Say "  代理: $Proxy" "DarkYellow"
}

$gitOk = $false
try { git --version | Out-Null; $gitOk = $true } catch {}
if (-not $gitOk) {
    Warn "未检测到 Git，尝试静默安装 Git for Windows..."
    if (-not $DryRun) {
        $gi = Join-Path $env:TEMP "git-setup.exe"
        try {
            $rel = Invoke-RestMethod "https://api.github.com/repos/git-for-windows/git/releases/latest" -TimeoutSec 30
            $asset = $rel.assets | Where-Object { $_.name -like "Git-*-64-bit.exe" } | Select-Object -First 1
            curl.exe -sL -o $gi $asset.browser_download_url
            Start-Process $gi -ArgumentList "/VERYSILENT /NORESTART /NOCANCEL" -Wait
            $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
            git --version | Out-Null
            Ok "Git 安装完成"
        } catch { Die "Git 安装失败" "手动安装: https://git-scm.com/download/win" }
    }
}
Ok "Git: $(try { (git --version) } catch { 'dry-run' })"

# ---------- 2. Python 3.11 ----------
Step 2 "Python $PY_VER"
$pyExe = ""
try {
    $v = & py -3.11 -c "import sys; print(sys.version.split()[0])" 2>$null
    if ($v -like "3.11*") { $pyExe = "py -3.11" }
} catch {}
if (-not $pyExe) {
    try {
        $v = & python -c "import sys; print(sys.version.split()[0])" 2>$null
        if ($v -like "3.11*") { $pyExe = "python" }
    } catch {}
}
if (-not $pyExe) {
    Say "  未找到 Python 3.11，下载安装中 (约 25MB)..."
    if (-not $DryRun) {
        $pi = Join-Path $env:TEMP "python-$PY_VER-amd64.exe"
        curl.exe -sL --retry 3 -o $pi $PY_URL
        Start-Process $pi -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0" -Wait
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
        try { & py -3.11 -c "print(1)" | Out-Null; $pyExe = "py -3.11" } catch { Die "Python 安装后仍不可用" "重开终端后重试，或手动安装 https://www.python.org/ftp/python/$PY_VER/python-$PY_VER-amd64.exe" }
        Ok "Python $PY_VER 安装完成"
    }
} else { Ok "Python 3.11 已存在" }

# ---------- 3. ComfyUI ----------
Step 3 "ComfyUI 引擎"
if (Test-Path (Join-Path $COMFY "main.py")) {
    Ok "ComfyUI 已存在，跳过克隆"
} else {
    Run "克隆 ComfyUI (浅克隆)" { git clone --depth 1 $COMFY_REPO $COMFY }
    Ok "ComfyUI 克隆完成"
}

# ---------- 4. venv + torch + 依赖 ----------
Step 4 "Python 虚拟环境与依赖 (torch CUDA 版较大, 耐心等)"
if (-not (Test-Path $VENVPY)) {
    if ($DryRun) { Say "  (dry-run) 创建 venv" "DarkGray" }
    else {
        if ($pyExe -eq "py -3.11") { & py -3.11 -m venv $VENV } else { & python -m venv $VENV }
        if (-not (Test-Path $VENVPY)) { Die "venv 创建失败" }
        Ok "venv 创建完成"
    }
} else { Ok "venv 已存在" }

if (-not $DryRun) {
    Say "  升级 pip (镜像: $PipMirror)"
    & $VENVPY -m pip install --upgrade pip -i $PipMirror -q
    Say "  安装 torch $TORCH_PKG (CUDA 13.0, 约 3GB, 最慢的一步)..."
    & $VENVPY -m pip install $TORCH_PKG torchvision --index-url $TORCH_INDEX
    if ($LASTEXITCODE -ne 0) { Die "torch 安装失败" "检查网络/代理；显卡驱动需支持 CUDA 12.8+" }
    Say "  安装 ComfyUI 依赖..."
    & $VENVPY -m pip install -r (Join-Path $COMFY "requirements.txt") -i $PipMirror -q
    if ($LASTEXITCODE -ne 0) { Die "ComfyUI 依赖安装失败" }
    Ok "依赖安装完成"
}

# ---------- 5. IPAdapter 自定义节点 ----------
Step 5 "IPAdapter 自定义节点 (角色参考模式)"
$ipnode = Join-Path $COMFY "custom_nodes\ComfyUI_IPAdapter_plus"
$cnDir = Join-Path $COMFY "custom_nodes"
if (Test-Path $ipnode) { Ok "IPAdapter 节点已存在" }
else {
    if (-not (Test-Path $cnDir)) { New-Item -ItemType Directory -Force $cnDir | Out-Null }
    Run "克隆 ComfyUI_IPAdapter_plus" { git clone --depth 1 $IPADAPTER_NODE $ipnode }
    Ok "IPAdapter 节点就绪"
}

# ---------- 6. 模型下载 ----------
Step 6 "模型下载 (合计约 9.9GB, 支持断点续传)"
$models = @(
    @{ dir = "checkpoints"; name = "NoobAI-XL-Vpred-v1.0.safetensors";
       url = "$HF/Laxhar/noobai-XL-Vpred-1.0/resolve/main/NoobAI-XL-Vpred-v1.0.safetensors";
       min = 6.0GB; desc = "NoobAI-XL 底模 6.6GB" },
    @{ dir = "ipadapter"; name = "ip-adapter-plus_sdxl_vit-h.safetensors";
       url = "$HF/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors";
       min = 700MB; desc = "IPAdapter Plus 808MB" },
    @{ dir = "clip_vision"; name = "clip_vision_h_vith.safetensors";
       url = "$HF/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors";
       min = 2.0GB; desc = "CLIP Vision ViT-H 2.5GB" }
)
if ($SkipModels) { Warn "已跳过模型下载 (-SkipModels)" }
else {
    foreach ($m in $models) {
        $ddir = Join-Path $COMFY ("models\" + $m.dir)
        if (-not (Test-Path $ddir)) { New-Item -ItemType Directory -Force $ddir | Out-Null }
        $dst = Join-Path $ddir $m.name
        if ((Test-Path $dst) -and ((Get-Item $dst).Length -gt $m.min)) {
            Ok "$($m.desc) 已存在"
            continue
        }
        Say "  下载 $($m.desc)..."
        if ($DryRun) { Say "  (dry-run) curl $($m.url)" "DarkGray"; continue }
        & curl.exe -L -C - --retry 3 --retry-delay 5 -o $dst $m.url
        if ($LASTEXITCODE -ne 0) { Die "$($m.name) 下载失败" "重跑本安装器会自动断点续传" }
        if ((Get-Item $dst).Length -lt $m.min) { Die "$($m.name) 文件不完整" "重跑即可续传" }
        Ok "$($m.desc) 完成"
    }
}

# ---------- 7. Easy Draw 应用 ----------
Step 7 "Easy Draw 应用"
if (Test-Path (Join-Path $APP "easydraw.py")) {
    Ok "应用已存在，执行 git pull 更新"
    if (-not $DryRun) { Push-Location $APP; git pull --ff-only 2>$null; Pop-Location }
} else {
    Run "克隆 easy-draw 仓库" { git clone --depth 1 $APP_REPO $APP }
    Ok "应用克隆完成"
}
# api_config.json: 从 example 生成 (不含任何个人 API)
$cfg = Join-Path $APP "api_config.json"
if (-not (Test-Path $cfg) -and -not $DryRun) {
    Copy-Item (Join-Path $APP "api_config.example.json") $cfg
    Ok "已生成 api_config.json (本机配置，可自行编辑)"
}

# ---------- 8. 可选: 本地 LLM ----------
Step 8 "本地 LLM (自然语言转换, 可选)"
if ($SkipLLM) { Warn "已跳过本地 LLM (-SkipLLM)，词典离线转换仍可用" }
else {
    $llamaExe = Join-Path $LLM_DIR "llama-server.exe"
    if (Test-Path $llamaExe) { Ok "llama-server 已存在" }
    elseif (-not $DryRun) {
        try {
            Say "  查询 llama.cpp 最新 CUDA 包..."
            $rel = Invoke-RestMethod "https://api.github.com/repos/ggml-org/llama.cpp/releases/latest" -TimeoutSec 30
            $asset = $rel.assets | Where-Object { $_.name -like "*win-cuda*x64.zip" -and $_.name -notlike "cudart*" } | Select-Object -First 1
            if (-not $asset) { $asset = $rel.assets | Where-Object { $_.name -like "*win-cuda*x64.zip" } | Select-Object -First 1 }
            if ($asset) {
                $zip = Join-Path $env:TEMP "llama-win.zip"
                Say "  下载 $($asset.name) ..."
                curl.exe -sL --retry 2 -o $zip $asset.browser_download_url
                New-Item -ItemType Directory -Force $LLM_DIR | Out-Null
                Expand-Archive $zip -DestinationPath $LLM_DIR -Force
                # 发布包可能多一层目录，找到 llama-server.exe 上移
                $found = Get-ChildItem $LLM_DIR -Recurse -Filter "llama-server.exe" | Select-Object -First 1
                if ($found -and $found.DirectoryName -ne $LLM_DIR) {
                    Get-ChildItem $found.DirectoryName | Move-Item -Destination $LLM_DIR -Force
                }
                Ok "llama.cpp 就绪"
            } else { Warn "未找到 CUDA 发行包，可用 CPU 版或手动安装" }
        } catch { Warn "llama.cpp 下载失败（可稍后手动装，不影响出图）" }
    }

    # GGUF 模型 (尽力而为)
    $gguf = Get-ChildItem $LLM_DIR -Filter "*.gguf" -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $gguf -and -not $DryRun) {
        try {
            Say "  搜索 Qwen3.5-9B-abliterated GGUF ..."
            $q = Invoke-RestMethod "$HF/api/models?search=Qwen3.5-9B-abliterated-GGUF&limit=10" -TimeoutSec 30
            $repo = ($q | Select-Object -First 1).id
            if ($repo) {
                $files = (Invoke-RestMethod "$HF/api/models/$repo" -TimeoutSec 30).siblings.rfilename
                $pick = $files | Where-Object { $_ -like "*Q4_K_M.gguf" } | Select-Object -First 1
                if ($pick) {
                    Say "  下载 $repo / $pick (约 5GB)..."
                    $dst = Join-Path $LLM_DIR (Split-Path $pick -Leaf)
                    curl.exe -L -C - --retry 3 -o $dst "$HF/$repo/resolve/main/$pick"
                    Ok "GGUF 模型就绪"
                }
            }
        } catch { Warn "GGUF 自动下载未成功，可手动放入 $LLM_DIR\*.gguf" }
    }
    # 把模型路径写进 api_config.json
    $gguf2 = Get-ChildItem $LLM_DIR -Filter "*.gguf" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($gguf2 -and (Test-Path $cfg)) {
        $j = Get-Content $cfg -Raw | ConvertFrom-Json
        $j.model = $gguf2.FullName
        $j | ConvertTo-Json -Depth 4 | Set-Content $cfg -Encoding UTF8
        Ok "api_config.json 已指向本地模型"
    }
}

# ---------- 9. 打包 exe + 自检 + 快捷方式 ----------
Step 9 "打包桌面版 / 自检 / 快捷方式"
if ($SkipBuildExe) { Warn "已跳过 exe 打包 (-SkipBuildExe)，可用 EasyDrawDesktop.bat 启动" }
elseif (-not $DryRun) {
    try {
        & $VENVPY -m pip install pyinstaller -i $PipMirror -q
        Push-Location $APP
        & $VENVPY -m PyInstaller --noconfirm --onefile --noconsole --name EasyDraw `
            --icon icon.ico --add-data "tags_data.json;." --add-data "danbooru.csv;." `
            --add-data "api_config.json;." easydraw.py --distpath . --workpath build *> $null
        Pop-Location
        if (Test-Path (Join-Path $APP "EasyDraw.exe")) { Ok "EasyDraw.exe 打包完成" }
        else { Warn "打包未成功，可用 EasyDrawDesktop.bat 启动" }
    } catch { Warn "打包异常: $($_.Exception.Message)" }
}
if (-not $DryRun -and (Test-Path $VENVPY)) {
    Say "  运行自检..."
    & $VENVPY (Join-Path $APP "easydraw.py") --selftest 2>&1 | Select-Object -Last 1
}
# 桌面快捷方式
if (-not $DryRun) {
    $target = if (Test-Path (Join-Path $APP "EasyDraw.exe")) { Join-Path $APP "EasyDraw.exe" } else { Join-Path $APP "EasyDrawDesktop.bat" }
    try {
        $ws = New-Object -ComObject WScript.Shell
        $lnk = $ws.CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "Easy Draw.lnk"))
        $lnk.TargetPath = $target
        $lnk.WorkingDirectory = $APP
        $lnk.IconLocation = (Join-Path $APP "icon.ico")
        $lnk.Save()
        Ok "桌面快捷方式已创建"
    } catch { Warn "快捷方式创建失败（不影响使用）" }
}

Say "`n==============================================" "Green"
Say "   安装完成" "Green"
Say "==============================================" "Green"
Say "  应用目录: $APP"
Say "  启动方式: 桌面「Easy Draw」图标 或 $APP\EasyDrawDesktop.bat"
Say "  首次出图: 先运行 StartEasyDraw.bat 启动 ComfyUI，再打开应用"
Say "  个人 API: 如需在线转换，编辑 $APP\api_config.json"
Say "  增删词库: 应用内「编辑词库」（桌面版标签库右上角）"
