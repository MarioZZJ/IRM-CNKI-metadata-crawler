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

Write-Host ""
Write-Host "=== 初始化完成 ===" -ForegroundColor Cyan
Write-Host "运行示例:" -ForegroundColor Green
Write-Host "  uv run python -m cnki_crawler --year 2025" -ForegroundColor White
Write-Host "  uv run python -m cnki_crawler --year 2025 --port 9222" -ForegroundColor White
