# CNKI Metadata Crawler - Windows 环境初始化脚本
# 用法: powershell -ExecutionPolicy Bypass -File setup.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "=== CNKI Metadata Crawler 环境初始化 ===" -ForegroundColor Cyan

# 检查 uv 是否已安装
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "未检测到 uv，正在安装..." -ForegroundColor Yellow
    irm https://astral.sh/uv/install.ps1 | iex
    # 刷新 PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Host "uv 安装失败，请手动安装: https://docs.astral.sh/uv/getting-started/installation/" -ForegroundColor Red
        exit 1
    }
}
Write-Host "uv 版本: $(uv --version)" -ForegroundColor Green

# 创建虚拟环境并安装依赖
Write-Host "正在创建虚拟环境并安装依赖..." -ForegroundColor Yellow
uv sync

# 创建 output 目录
if (-not (Test-Path "output")) {
    New-Item -ItemType Directory -Path "output" | Out-Null
}

# 检查 cookies.txt
if (-not (Test-Path "cookies.txt")) {
    Write-Host ""
    Write-Host "[提示] 未找到 cookies.txt，阶段2需要浏览器 Cookie 才能运行。" -ForegroundColor Yellow
    Write-Host "获取方法:" -ForegroundColor Yellow
    Write-Host "  1. 在 Chrome 中访问 https://kns.cnki.net 的任意论文详情页" -ForegroundColor White
    Write-Host "  2. F12 打开开发者工具 -> Console -> 输入 document.cookie" -ForegroundColor White
    Write-Host "  3. 将输出内容保存到项目根目录的 cookies.txt 文件中" -ForegroundColor White
}

Write-Host ""
Write-Host "=== 初始化完成 ===" -ForegroundColor Cyan
Write-Host "运行示例:" -ForegroundColor Green
Write-Host "  uv run python -m cnki_crawler --phase1 --year 2024" -ForegroundColor White
Write-Host "  uv run python -m cnki_crawler --phase2 --cookies cookies.txt" -ForegroundColor White
