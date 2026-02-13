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
echo "正在创建虚拟环境并安装依赖..."
uv sync
uv pip install -e .

# 创建 output 目录
mkdir -p output

# 检查 cookies.txt
if [ ! -f "cookies.txt" ]; then
    echo ""
    echo "[提示] 未找到 cookies.txt，阶段2需要浏览器 Cookie 才能运行。"
    echo "获取方法:"
    echo "  1. 在 Chrome 中访问 https://kns.cnki.net 的任意论文详情页"
    echo "  2. F12 打开开发者工具 -> Console -> 输入 document.cookie"
    echo "  3. 将输出内容保存到项目根目录的 cookies.txt 文件中"
fi

echo ""
echo "=== 初始化完成 ==="
echo "运行示例:"
echo "  uv run python -m cnki_crawler --phase1 --year 2024"
echo "  uv run python -m cnki_crawler --phase2 --cookies cookies.txt"
