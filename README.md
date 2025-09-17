# Bybit 期权交易应用

这是一个基于 Bybit API 的期权交易应用程序，支持查看期权链、持仓信息和钱包余额。

## 功能特性

- 📊 **期权链查询**: 查看完整的期权链数据，包括价格、成交量、希腊字母等
- 💼 **持仓管理**: 查看当前期权持仓和盈亏情况
- 💰 **钱包信息**: 查看账户余额和各币种分布
- 🎯 **灵活筛选**: 支持按到期日、执行价格范围等条件筛选
- 🌈 **彩色显示**: 使用颜色区分盈亏状态，提升视觉体验

## 安装和配置

### 1. 安装依赖

```bash
cd /root/option
pip install -r requirements.txt
```

### 2. 配置 API 密钥

创建 `.env` 文件：

```bash
cp env_example.txt .env
```

编辑 `.env` 文件，填入您的 Bybit API 密钥：

```env
BYBIT_API_KEY=your_api_key_here
BYBIT_API_SECRET=your_api_secret_here
BYBIT_TESTNET=true
```

**注意**: 
- 在 [Bybit 官网](https://www.bybit.com) 申请 API 密钥
- 建议先在测试网环境测试（BYBIT_TESTNET=true）
- 生产环境请设置 BYBIT_TESTNET=false

### 3. 权限配置

给主程序添加执行权限：

```bash
chmod +x main.py
```

## 使用方法

### 基本命令

```bash
# 查看帮助
python main.py --help

# 检查配置
python main.py config-check
```

### 期权链查询

```bash
# 查看 BTC 期权链
python main.py chain

# 查看 ETH 期权链
python main.py chain -b ETH

# 查看指定执行价格范围的期权
python main.py chain --strike-min 40000 --strike-max 50000

# 只查看平值期权
python main.py chain --atm-only

# 查看可用的到期日
python main.py expiries
```

### 持仓查询

```bash
# 查看所有期权持仓
python main.py positions

# 查看指定合约的持仓
python main.py positions -s BTC-29DEC23-42000-C
```

### 钱包信息

```bash
# 查看钱包余额
python main.py wallet

# 查看账户摘要
python main.py summary
```

## 命令详细说明

### chain - 期权链查询

**选项**:
- `-b, --base-coin`: 基础币种 (BTC/ETH)，默认 BTC
- `-e, --expiry`: 过滤特定到期日 (YYYY-MM-DD)
- `--strike-min`: 最小执行价格
- `--strike-max`: 最大执行价格
- `--atm-only`: 只显示平值期权

**示例**:
```bash
# 查看 BTC 12月29日到期的期权
python main.py chain -e 2023-12-29

# 查看执行价格在 40000-50000 之间的 BTC 期权
python main.py chain --strike-min 40000 --strike-max 50000
```

### positions - 持仓查询

**选项**:
- `-s, --symbol`: 指定合约符号

**显示信息**:
- 合约名称
- 持仓方向 (Buy/Sell)
- 持仓数量
- 平均成本价
- 当前标记价格
- 未实现盈亏
- 收益率百分比
- 杠杆倍数

### wallet - 钱包信息

**显示信息**:
- 总权益
- 钱包余额
- 可用余额
- 保证金使用情况
- 各币种余额分布
- 未实现盈亏

## 数据说明

### 期权链数据包含

- **基础信息**: 合约符号、执行价格、期权类型、到期时间
- **价格数据**: 买价、卖价、标记价格、最新成交价
- **成交数据**: 24小时成交量、持仓量
- **希腊字母**: Delta, Gamma, Theta, Vega
- **隐含波动率**: 以百分比显示

### 颜色标识

- 🟢 **绿色**: 盈利状态
- 🔴 **红色**: 亏损状态
- 🔵 **蓝色**: 标题和重要信息
- 🟡 **黄色**: 警告信息

## 注意事项

1. **API 限制**: 请遵守 Bybit API 的调用频率限制
2. **网络连接**: 确保网络连接稳定，程序会自动重试失败的请求
3. **数据延迟**: 市场数据可能有轻微延迟
4. **风险提示**: 期权交易具有高风险，请谨慎操作

## 故障排除

### 常见问题

**Q: 提示 "API 密钥未设置"**
A: 请检查 `.env` 文件是否存在且配置正确

**Q: 获取数据失败**
A: 检查网络连接和 API 密钥权限

**Q: 显示 "没有找到期权数据"**
A: 可能是指定的币种或时间范围没有可用的期权合约

### 调试模式

如需调试，可以在代码中添加打印语句查看 API 返回的原始数据。

## 扩展功能

您可以基于现有框架添加更多功能：

- 期权交易下单
- 风险指标计算
- 数据导出功能
- 实时价格监控
- 邮件/短信提醒

## 许可证

本项目仅供学习和研究使用。使用时请遵守相关法律法规和交易所规则。
