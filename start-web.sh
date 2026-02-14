#!/bin/bash

# nanobot Web 启动脚本
# 自动激活虚拟环境并启动 web 服务

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 虚拟环境路径
VENV_PATH="$SCRIPT_DIR/.venv"

# 检查虚拟环境是否存在
if [ ! -d "$VENV_PATH" ]; then
    echo "错误: 虚拟环境不存在: $VENV_PATH"
    echo "请先创建虚拟环境: python3 -m venv .venv"
    exit 1
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source "$VENV_PATH/bin/activate"

# 检查 nanobot 是否已安装
if ! command -v nanobot &> /dev/null; then
    echo "错误: nanobot 未安装，正在安装..."
    pip install -e "$SCRIPT_DIR"
fi

# 检查配置文件是否存在
CONFIG_FILE="$HOME/.nanobot/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "配置文件不存在，正在初始化..."
    nanobot onboard
fi

# 显示状态
echo ""
echo "========== nanobot 状态 =========="
nanobot status
echo "=================================="
echo ""

# 检查 MCP 配置
if [ -f "$CONFIG_FILE" ]; then
    if grep -q '"mcp"' "$CONFIG_FILE" 2>/dev/null || grep -q '"minimax"' "$CONFIG_FILE" 2>/dev/null; then
        echo "✓ MCP 配置已启用"
    fi
fi

# 启动 web 服务（默认端口 18790）
PORT="${1:-18790}"
HOST="${2:-0.0.0.0}"

echo "启动 web 服务 on http://$HOST:$PORT"
echo "按 Ctrl+C 停止"
echo ""

nanobot web --port "$PORT" --host "$HOST"
