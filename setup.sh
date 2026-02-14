#!/usr/bin/env bash
# CNKI Metadata Crawler - Linux/macOS 环境初始化脚本
# 用法: bash setup.sh

set -euo pipefail

echo "=== CNKI Metadata Crawler 环境初始化 ==="

# 检查 uv 是否已安装
if ! command -v uv &> /dev/null; then
    echo "未检测到 uv，正在安装..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    if ! command -v uv &> /dev/null; then
        echo "uv 安装失败，请手动安装: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi
fi
echo "uv 版本: $(uv --version)"

# 创建虚拟环境并安装依赖
# 强制使用项目本地 .venv，避免 UV_PROJECT_ENVIRONMENT 指向 Conda 等外部环境导致冲突
echo "正在创建虚拟环境并安装依赖..."
UV_PROJECT_ENVIRONMENT=.venv uv sync

# 创建 output 目录
mkdir -p output

echo ""
echo "=== 初始化完成 ==="
echo "运行示例:"
echo "  uv run python -m cnki_crawler --year 2025"
echo "  uv run python -m cnki_crawler --year 2025 --port 9222"
