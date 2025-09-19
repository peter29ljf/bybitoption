# 期权价格监控API

一个基于WebSocket的期权实时价格监控系统，当期权价格达到目标价格时通过webhook发送通知。

## 功能特性

- ✅ 实时监控期权价格（基于Bybit WebSocket）
- ✅ 支持多个期权合约同时监控
- ✅ 支持BTC现货价格触发，与期权监控共存
- ✅ 价格达到目标时自动发送webhook通知
- ✅ 任务超时自动清理
- ✅ 支持Redis和内存存储
- ✅ RESTful API接口
- ✅ 健康检查端点
- ✅ 完整的错误处理和日志记录

## 快速开始

### 1. 安装依赖

```bash
cd price_monitor
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件设置你的配置
```

### 3. 启动服务

```bash
python run.py
```

服务将在 `http://localhost:8888` 启动。

## API接口

### 创建监控任务

```http
POST /api/monitor/create
Content-Type: application/json

{
    "task_id": "unique_task_id_123",
    "option_symbol": "BTC-17JAN25-100000-C",
    "target_price": 5000.0,
    "webhook_url": "https://your-webhook-endpoint.com/callback",
    "timeout_hours": 24,
    "strategy_id": "strategy-1",
    "level_id": "level-1",
    "monitor_type": "ENTRY",
    "monitor_instrument": "option",
    "monitor_symbol": "BTC-17JAN25-100000-C-USDT",
    "metadata": {
        "side": "buy",
        "quantity": "1"
    }
}
```

### 查询任务状态

```http
GET /api/monitor/{task_id}
```

### 删除监控任务

```http
DELETE /api/monitor/{task_id}
```

### 获取所有活跃任务

```http
GET /api/monitor/tasks
```

### 健康检查

```http
GET /health
```

## 期权合约符号格式

期权合约符号格式：`{BASE_COIN}-{EXPIRY}-{STRIKE}-{TYPE}`

- `BASE_COIN`: 基础币种（BTC 或 ETH）
- `EXPIRY`: 到期日期（如 17JAN25）
- `STRIKE`: 执行价格（如 100000）
- `TYPE`: 期权类型（C=看涨，P=看跌）

示例：
- `BTC-17JAN25-100000-C` - BTC看涨期权，2025年1月17日到期，执行价格100000
- `ETH-10FEB25-4000-P` - ETH看跌期权，2025年2月10日到期，执行价格4000

## Webhook通知格式

当价格穿越目标价格时（上穿或下穿），系统会向指定的webhook URL发送POST请求：

```json
{
    "task_id": "unique_task_id_123",
    "option_symbol": "BTC-17JAN25-100000-C",
    "target_price": 5000.0,
    "triggered_price": 5000.5,
    "previous_price": 4999.8,
    "trigger_direction": "up_cross",
    "triggered_at": "2025-01-17T10:30:00.000Z",
    "strategy_id": "strategy-1",
    "level_id": "level-1",
    "monitor_type": "ENTRY",
    "metadata": {
        "side": "buy",
        "quantity": "1"
    }
}
```

**字段说明:**
- `trigger_direction`: 触发方向
  - `up_cross`: 价格从下方上穿目标价格
  - `down_cross`: 价格从上方下穿目标价格

## 配置说明

| 环境变量 | 默认值 | 说明 |
|---------|-------|------|
| MONITOR_HOST | 0.0.0.0 | 服务监听地址 |
| MONITOR_PORT | 8888 | 服务端口 |
| MONITOR_DEBUG | true | 调试模式 |
| BYBIT_TESTNET | true | 是否使用测试网 |
| MAX_MONITOR_TASKS | 100 | 最大监控任务数 |
| TASK_TIMEOUT_HOURS | 24 | 任务超时时间（小时） |
| USE_REDIS | false | 是否使用Redis存储 |
| REDIS_URL | redis://localhost:6379/0 | Redis连接URL |
| LOG_LEVEL | INFO | 日志级别 |
| LOG_FILE | price_monitor.log | 日志文件 |
| SPOT_POLL_INTERVAL | 1.5 | 现货价格轮询间隔（秒） |

## 存储选项

### 内存存储（默认）
- 适合开发和小规模使用
- 服务重启后数据会丢失

### Redis存储
- 适合生产环境
- 数据持久化，支持服务重启
- 设置 `USE_REDIS=true` 启用

## 监控原理

1. **WebSocket连接**: 服务启动时连接到Bybit WebSocket
2. **订阅价格**: 根据活跃任务动态订阅期权价格数据
3. **价格检查**: 实时接收价格更新并检查是否穿越目标价格
4. **穿越检测**: 监控价格上穿和下穿目标价格的行为
   - **上穿**: 之前价格 < 目标价格 ≤ 当前价格
   - **下穿**: 之前价格 > 目标价格 ≥ 当前价格
5. **触发通知**: 价格穿越目标时发送webhook并更新任务状态（每个任务只触发一次）
6. **任务清理**: 定期清理过期任务

## 日志

服务会记录详细的操作日志，包括：
- 任务创建/删除
- 价格更新
- WebSocket连接状态
- Webhook发送结果
- 错误信息

## 错误处理

- 自动重连WebSocket
- Webhook发送失败重试
- 完整的异常捕获和日志记录
- API错误响应标准化

## 性能考虑

- 单个服务实例建议监控任务不超过1000个
- WebSocket连接异常时自动重连
- 使用异步编程提高并发性能
- 定期清理过期任务释放资源

## 注意事项

1. 确保webhook URL可访问且响应正常
2. 合理设置任务超时时间
3. 生产环境建议使用Redis存储
4. 监控服务日志以及时发现问题
5. 期权合约符号必须在Bybit交易所存在
当需要基于BTC现货价格触发时，只需将 `monitor_instrument` 设置为 `spot`，并把 `monitor_symbol` 指定为 `BTCUSDT`（目前仅支持该现货符号），其余字段保持不变。
