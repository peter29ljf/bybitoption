# Bybit 期权工具集

一个集命令行与 Web 界面于一体的 Bybit 期权交易助手。项目提供期权链查询、持仓/钱包洞察、策略配置、AI 辅助分析以及可选的价格监控子服务。

## 功能亮点
- **命令行工具**: 通过 `main.py` 快速查询期权链、持仓、钱包、订单历史以及情景分析。
- **Web 控制台**: 友好的页面交互，支持期权搜索、关注列表、策略管理、AI 辅助解读和运行时配置管理。
- **策略与设置管理**: 持久化 API 凭据、策略、交易纪录，支持 webhook 回调。
- **本地缓存**: 自动缓存期权链数据与关注列表，减少重复请求。
- **可选价格监控服务**: `price_monitor/` 提供 FastAPI + WebSocket 的实时价格触发器（独立安装依赖即可运行）。

## 环境准备
- Python 3.10 及以上版本
- pip 与 virtualenv（推荐）

## 安装步骤
```bash
# 克隆项目
git clone <your-repo-url>
cd bybitoption

# 创建并激活虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 准备环境变量
cp env_example.txt .env
# 编辑 .env，填入 BYBIT_API_KEY / BYBIT_API_SECRET / BYBIT_TESTNET
```

> **提示**: 运行时会自动在 `cache/` 与 `data/` 目录写入缓存文件，这两个目录已默认忽略，不会出现在仓库中。

## 命令行用法
在虚拟环境中执行：
```bash
python main.py config-check         # 查看当前配置
python main.py chain -b BTC         # 查询 BTC 期权链
python main.py positions            # 查看持仓
python main.py wallet               # 查看钱包余额
python main.py orders --limit 20    # 最近订单
python main.py scenario -s BTC-31OCT25-110000-C-USDT -t 110000
```

常用选项：
- `--testnet` 使用测试网
- `--expiry` 过滤到期日（YYYY-MM-DD）
- `--strike-min/--strike-max` 限定执行价范围
- `buy`/`sell` 子命令在提交订单前会给出确认提示

若喜欢交互式脚本，可运行 `./run.sh`，根据提示选择功能；`./run.sh web` 会直接启动网页端。

## Web 应用
```bash
source venv/bin/activate
python app.py
# 或 ./run.sh web
```
默认监听 `http://localhost:8080`。首次打开需在“设置”页录入 API Key 与是否使用测试网；设置会自动持久化到 `settings_manager/data/settings.json`。

主要模块：
- **期权搜索**: 支持按目标价格、到期日、方向筛选并缓存结果
- **关注列表**: 将感兴趣的合约加入 watchlist，随时刷新
- **策略中心**: 管理多层策略、Webhook、交易记录
- **AI 助手**: 可配置第三方模型接口（默认占位配置，可自行扩展）

## 价格监控服务（可选）
`price_monitor/` 目录提供独立的 FastAPI 服务，用于实时监控期权价格并触发 Webhook。需要单独安装依赖：
```bash
cd price_monitor
pip install -r requirements.txt
python run.py
```
更详细的接口说明参见 `price_monitor/README.md`。

## 目录总览
```
bybitoption/
├── app.py                # Flask Web 应用入口
├── main.py               # CLI 主程序
├── bybit_api.py          # Bybit REST 接口封装
├── option_chain.py       # 期权链处理逻辑
├── positions.py          # 持仓与钱包处理
├── trading.py            # 下单与订单交互
├── data_cache.py         # 期权链缓存管理
├── ai_assistant.py       # AI 助手模块
├── strategy_manager/     # 策略、Webhook 与存储逻辑
├── settings_manager/     # 运行时设置管理与持久化
├── templates/ & static/  # Web 前端资源
├── price_monitor/        # 可选的价格监控服务
├── run.sh                # 便捷启动脚本
├── env_example.txt       # 环境变量示例
└── requirements.txt      # 依赖列表
```

## 常见问题
- **缓存/关注列表在哪里？** 运行时会写入 `cache/` 与 `data/`，若需要重置可直接删除目录内容。
- **为何提示缺少 API Key？** 请确认 `.env` 或设置页面已经填入有效的 Bybit API Key/Secret，并根据需要选择测试网或实盘。
- **如何部署价格监控服务？** 参考 `price_monitor/README.md`，该服务可与主应用分开部署。

## 许可证
项目遵循 `LICENSE` 所列条款，仅供学习与研究使用，实盘交易请谨慎操作。
