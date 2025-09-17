# Bybit 期权交易应用使用指南

## 快速开始

### 1. 进入项目目录
```bash
cd /root/option
```

### 2. 运行应用
```bash
# 使用启动脚本（推荐）
./run.sh

# 或直接运行（需要先激活虚拟环境）
source venv/bin/activate
python main.py --help
```

### 3. 配置 API 密钥（可选）
```bash
# 复制示例配置
cp env_example.txt .env

# 编辑配置文件，填入您的API密钥
nano .env
```

## 主要功能演示

### 1. 检查系统配置
```bash
./run.sh config-check
```

### 2. 查看 BTC 期权链
```bash
# 查看完整期权链
./run.sh chain

# 查看 ETH 期权链
./run.sh chain -b ETH

# 查看特定执行价格范围
./run.sh chain --strike-min 40000 --strike-max 50000

# 只查看平值期权
./run.sh chain --atm-only
```

### 3. 查看可用到期日
```bash
./run.sh expiries
./run.sh expiries -b ETH
```

### 4. 查看持仓（需要API密钥）
```bash
./run.sh positions
```

### 5. 查看钱包（需要API密钥）
```bash
./run.sh wallet
```

### 6. 账户摘要（需要API密钥）
```bash
./run.sh summary
```

## 交互模式

运行 `./run.sh` 不带参数会进入交互模式：

```bash
./run.sh
```

然后选择相应的功能选项。

## 文件结构

```
/root/option/
├── main.py              # 主应用程序
├── bybit_api.py         # Bybit API 客户端
├── option_chain.py      # 期权链查询模块
├── positions.py         # 持仓查询模块
├── config.py            # 配置文件
├── requirements.txt     # Python依赖
├── run.sh              # 启动脚本
├── env_example.txt     # 环境变量示例
├── README.md           # 详细文档
├── USAGE.md            # 使用指南
└── venv/               # Python虚拟环境
```

## API 功能对照

| 功能 | 需要API密钥 | 说明 |
|------|------------|------|
| 期权链查询 | ❌ | 公开市场数据 |
| 期权价格 | ❌ | 公开市场数据 |
| 到期日查询 | ❌ | 公开合约信息 |
| 持仓查询 | ✅ | 需要账户权限 |
| 钱包余额 | ✅ | 需要账户权限 |
| 账户摘要 | ✅ | 需要账户权限 |

## 输出示例

### 期权链显示
- 按到期日分组
- 看涨/看跌期权分别显示
- 包含执行价、买卖价、成交量、持仓量、希腊字母等
- 使用颜色区分盈亏状态

### 持仓显示
- 合约信息和持仓方向
- 平均成本价和当前市价
- 未实现盈亏和收益率
- 总计统计

## 注意事项

1. **网络要求**: 需要稳定的互联网连接访问 Bybit API
2. **API限制**: 请遵守 API 调用频率限制
3. **测试环境**: 默认使用测试网，可通过配置切换到生产环境
4. **数据延迟**: 市场数据可能有轻微延迟

## 故障排除

### 常见问题

1. **ModuleNotFoundError**: 运行 `./run.sh` 自动安装依赖
2. **网络超时**: 检查网络连接或调整 `REQUEST_TIMEOUT` 配置
3. **API错误**: 检查API密钥和权限设置

### 调试模式

如需调试，可以在相关函数中添加 `print` 语句查看API返回的原始数据。
