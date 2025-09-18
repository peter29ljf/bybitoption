#!/bin/bash

# Bybit 期权交易应用启动脚本

echo "=== Bybit 期权交易应用 ==="
echo

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python3"
    exit 1
fi

# 检查并创建虚拟环境
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 检查依赖
if ! python -c "import requests, tabulate, colorama, click, dotenv" 2>/dev/null; then
    echo "正在安装依赖包..."
    pip install -r requirements.txt
fi

# 检查配置文件
if [ ! -f ".env" ]; then
    echo "警告: 未找到 .env 配置文件"
    echo "请复制 env_example.txt 为 .env 并配置您的 API 密钥"
    echo
fi

# 显示使用帮助
echo "使用方法:"
echo "  ./run.sh web                 # 启动Web应用"
echo "  ./run.sh --help             # 查看命令行帮助"
echo "  ./run.sh config-check       # 检查配置"
echo "  ./run.sh chain              # 查看期权链"
echo "  ./run.sh positions          # 查看持仓"
echo "  ./run.sh wallet             # 查看钱包"
echo "  ./run.sh summary            # 账户摘要"
echo

# 如果提供了参数，处理特殊命令
if [ $# -gt 0 ]; then
    if [ "$1" = "web" ]; then
        echo "正在启动Web应用..."
        echo "访问地址: http://localhost:5000"
        echo "按 Ctrl+C 停止服务"
        echo
        python app.py
    else
        python main.py "$@"
    fi
else
    # 交互式模式
    echo "请选择功能:"
    echo "1) 启动Web应用"
    echo "2) 检查配置"
    echo "3) 查看期权链"
    echo "4) 查看持仓"
    echo "5) 查看钱包"
    echo "6) 账户摘要"
    echo "0) 退出"
    echo
    
    while true; do
        read -p "请输入选项 (0-6): " choice
        case $choice in
            1)
                echo "正在启动Web应用..."
                echo "访问地址: http://localhost:5000"
                echo "按 Ctrl+C 停止服务"
                echo
                python app.py
                break
                ;;
            2)
                python main.py config-check
                break
                ;;
            3)
                python main.py chain
                break
                ;;
            4)
                python main.py positions
                break
                ;;
            5)
                python main.py wallet
                break
                ;;
            6)
                python main.py summary
                break
                ;;
            0)
                echo "再见!"
                exit 0
                ;;
            *)
                echo "无效选项，请输入 0-6"
                ;;
        esac
    done
fi
