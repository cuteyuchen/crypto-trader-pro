# API 参考文档

## 概述

Crypto Trader Pro 提供完整的 REST API，用于程序化控制和集成。

**基础信息：**
- 根路径：`http://localhost:5000`（默认）
- 认证：HTTP Basic Auth（默认 admin/admin123）
- 响应格式：JSON

---

## 认证配置

### HTTP Basic Auth

所有 API（`/static/` 除外）需要 Basic Auth。

**默认凭证：**
- 用户名：`admin`
- 密码：`admin123`

### 环境变量自定义

```bash
# .env 文件或 Docker 环境变量
DASHBOARD_USER=admin
DASHBOARD_PASS=your_secure_password
```

重启服务后生效。

---

## API 端点列表

### 系统状态

#### GET `/api/status`

获取系统运行状态。

**响应：**

```json
{
  "mode": "local",
  "running": true,
  "strategy": "MA5_MA20_Cross",
  "exchange": "okx",
  "symbol": "BTC/USDT"
}
```

**字段说明：**
- `mode`：运行模式（`local`/`testnet`/`live`）
- `running`：机器人是否正在运行
- `strategy`：当前策略名称
- `exchange`：配置的交易所
- `symbol`：当前交易对

#### GET `/health`

健康检查端点，用于负载均衡器或监控。

**响应：**

```json
{
  "status": "ok"
}
```

---

### 账户与持仓

#### GET `/api/balance`

获取账户余额（仅支持 USDT 查询，其他币种需扩展）。

**响应：**

```json
{
  "USDT": 10000.0
}
```

**示例：**

```bash
curl -u admin:admin123 http://localhost:5000/api/balance
```

#### GET `/api/positions`

获取当前持仓列表（本地模拟或交易所实盘）。

**响应：**

```json
[
  {
    "id": 1,
    "symbol": "BTC/USDT",
    "side": "long",
    "quantity": 0.039682,
    "entry_price": 50320.50,
    "current_price": 51000.00,
    "unrealized_pnl": 27.14,
    "created_at": "2025-03-05T10:15:00"
  }
]
```

**字段说明：**
- `id`：持仓 ID（数据库自增）
- `side`：方向（目前只支持 `long`）
- `entry_price`：入场均价
- `current_price`：当前市场价格（从 K 线缓存获取）
- `unrealized_pnl`：未实现盈亏（基于 `current_price` 计算）

---

### 交易执行

#### POST `/api/order`

手动下单（仅 local 模式可用）。

**请求体：**

```json
{
  "symbol": "BTC/USDT",
  "side": "buy",           // "buy" 或 "sell"
  "quantity": 0.01,
  "type": "market",        // "market" 或 "limit"
  "price": 50000.0         // limit 单必填，market 单可选（不填则用市价）
}
```

**响应（success）：**

```json
{
  "success": true,
  "order_id": "local_1700000000.123456",
  "filled_quantity": 0.01,
  "avg_price": 50012.34,
  "fee": 0.05,
  "pnl": 0.0
}
```

**响应（failure）：**

```json
{
  "success": false,
  "error": "USDT 余额不足"
}
```

**错误码：**
- 400：请求参数错误
- 403：非 local 模式禁止手动下单
- 500：执行异常

**示例：**

```bash
curl -X POST http://localhost:5000/api/order \
  -u admin:admin123 \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTC/USDT","side":"buy","quantity":0.01,"type":"market"}'
```

#### GET `/api/trades`

获取最近的交易记录（包括买入和卖出）。

**查询参数：**
- `?limit=20`：返回数量（默认 20，最大 100）

**响应：**

```json
[
  {
    "id": 15,
    "executed_at": "2025-03-05T10:30:00",
    "symbol": "BTC/USDT",
    "side": "sell",
    "quantity": 0.039682,
    "price": 51000.00,
    "fee": 0.204,
    "pnl": 27.14
  },
  ...
]
```

**说明：**
- 本地模式：从 SQLite `trades` 表查询
- 实盘模式：从 CCXT `fetch_my_trades` 获取

---

### Trader 控制

#### POST `/api/trader/control`

控制自动交易引擎。

**请求体：**

```json
{
  "action": "stop"        // "start" | "stop" | "pause" | "resume" | "force_sell"
}
```

**参数说明：**
- `stop`：停止循环（不可重启，需重启服务）
- `pause`：暂停自动交易，保留持仓，仍在监控止损止盈
- `resume`：恢复自动交易
- `force_sell`：强制平仓所有持仓（需额外参数）

**force_sell 示例：**

```json
{
  "action": "force_sell",
  "symbol": "BTC/USDT",    // 可选，不填则平仓所有品种
  "quantity": null         // 可选，null 表示平仓全部
}
```

**响应：**

```json
{
  "success": true,
  "message": "自动交易已暂停"
}
```

**示例：**

```bash
curl -X POST http://localhost:5000/api/trader/control \
  -u admin:admin123 \
  -H "Content-Type: application/json" \
  -d '{"action": "pause"}'
```

#### GET `/api/trader/status`

获取 Trader 运行状态。

**响应：**

```json
{
  "running": true,
  "auto_trade": true,
  "open_trades_count": 1,
  "closed_trades_count": 15,
  "total_pnl": 234.56,
  "win_rate": 55.0,
  "max_open_trades": 3
}
```

#### GET `/api/trader/stats`

获取详细统计信息（同 `/api/trader/status`，未来可能扩展更多指标）。

---

### 策略管理

#### GET `/api/strategies`

列出 `config/strategies/` 目录下所有可用的策略配置文件。

**响应：**

```json
[
  {
    "name": "MA5_MA20_Cross",
    "type": "ma_cross",
    "file": "ma_cross.json",
    "config": {
      "name": "MA5_MA20_Cross",
      "type": "ma_cross",
      "symbol": "BTC/USDT",
      "timeframe": "1m",
      "params": {"fast_period": 5, "slow_period": 20},
      "position_size": 0.2,
      "stop_loss_pct": 0.05,
      "take_profit_pct": 0.10
    }
  },
  ...
]
```

#### POST `/api/strategy/reload`

热重载策略配置（从文件重新加载，无需重启）。

**响应：**

```json
{
  "success": true,
  "message": "策略已重载: MA5_MA20_Cross"
}
```

**注意：**
- 此操作会重新加载 `modes.json` 中指定的策略文件
- StrategyEngine 会重新初始化，缓存清空

#### POST `/api/strategy/config`

更新策略配置文件中的参数，并自动重载。

**请求体：**

```json
{
  "file": "ma_cross.json",
  "config": {
    "params": {
      "fast_period": 10,
      "slow_period": 30
    }
  }
}
```

**合并逻辑：**
- 如果 `config` 中的 key 存在于原配置的 `params` 嵌套对象中，则更新 `params` 内字段
- 否则直接更新顶层字段

**响应：**

```json
{
  "success": true,
  "message": "策略配置已更新并重载"
}
```

**示例：**

```bash
# 修改 MA 交叉策略的 fast_period 为 10
curl -X POST http://localhost:5000/api/strategy/config \
  -u admin:admin123 \
  -H "Content-Type: application/json" \
  -d '{"file":"ma_cross.json","config":{"params":{"fast_period":10}}}'
```

---

### 系统配置

#### GET `/api/config`

获取 `config/modes.json` 的当前内容。

**响应：**

```json
{
  "mode": "local",
  "exchange": "okx",
  "initial_balance": 10000,
  "symbols": ["BTC/USDT"],
  "strategy": "ma_cross",
  "update_interval_ms": 1000,
  "dashboard_enabled": true,
  "notifications_enabled": true
}
```

#### POST `/api/config`

更新 `config/modes.json`（需要重启或调用 `/api/strategy/reload` 生效）。

**请求体：**（同 GET 响应格式）

```json
{
  "mode": "local",
  "strategy": "rsi",
  "notifications_enabled": false
}
```

**响应：**

```json
{
  "success": true,
  "message": "配置已保存，请重启或调用重载"
}
```

---

### 回测

#### POST `/api/backtest`

运行策略回测，返回详细指标和权益曲线。

**请求体：**

```json
{
  "strategy": "ma_cross",     // 策略文件名（不含.json）
  "days": 30,                 // 回测天数（1-90）
  "initial_balance": 10000    // 初始资金（默认 10000）
}
```

**响应：**

```json
{
  "strategy": "MA5_MA20_Cross",
  "initial_balance": 10000,
  "final_balance": 11234.56,
  "total_pnl": 1234.56,
  "total_return_pct": 12.35,
  "annual_return_pct": 150.42,
  "max_drawdown_pct": 8.23,
  "sharpe_ratio": 1.45,
  "win_rate_pct": 55.0,
  "profit_loss_ratio": 1.67,
  "total_trades": 42,
  "trades_per_day": 1.4,
  "avg_holding_days": 2.3,
  "equity_curve": [
    {"time": "2024-01-01T00:00:00", "equity": 10000},
    {"time": "2024-01-01T01:00:00", "equity": 10010},
    ...
  ],
  "trades": [
    {"time": "2024-01-01T10:30:00", "side": "buy", "quantity": 0.02, "price": 45000, "pnl": 0},
    {"time": "2024-01-01T12:00:00", "side": "sell", "quantity": 0.02, "price": 45500, "pnl": 10.0},
    ...
  ]
}
```

**字段说明：**
- `equity_curve`：每根 K 线的总资产（可用于绘制资金曲线）
- `trades`：所有成交记录（买入和卖出都包含）
- `metrics`：已合并到顶层，重复字段保持向下兼容

**示例：**

```bash
curl -X POST http://localhost:5000/api/backtest \
  -u admin:admin123 \
  -H "Content-Type: application/json" \
  -d '{"strategy":"rsi","days":30,"initial_balance":10000}' \
  -o result.json
```

---

### 日志

#### GET `/api/logs`

获取日志文件的最后 100 行。

**响应：**

```json
{
  "logs": "2025-03-05 10:15:00 - INFO - 策略信号: {...}\n2025-03-05 10:16:00 - INFO - 买入成功..."
}
```

#### GET `/api/logs/stream`

Server-Sent Events（SSE）实时日志流。

**响应格式：**
```
data: 2025-03-05 10:15:00 - INFO - ...
data: 2025-03-05 10:15:05 - INFO - ...
...
```

**前端使用示例：**

```javascript
const eventSource = new EventSource('/api/logs/stream');
eventSource.onmessage = (e) => {
  console.log(e.data); // 添加日志到页面
};
```

---

## 响应状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误（如缺少字段、类型错误） |
| 401 | 未认证（未提供或错误的 Basic Auth） |
| 403 | 禁止（如非 local 模式尝试手动下单） |
| 404 | 资源不存在（如策略文件不存在） |
| 500 | 服务器内部错误（异常堆栈在响应中） |

---

## 错误响应格式

```json
{
  "success": false,
  "error": "订单执行失败: Insufficient balance"
}
```

或直接返回：

```json
{
  "error": "策略文件不存在: foo.json"
}
```

---

## 使用示例（Python）

```python
import requests
from requests.auth import HTTPBasicAuth

base_url = "http://localhost:5000"
auth = HTTPBasicAuth("admin", "admin123")

# 1. 获取状态
resp = requests.get(f"{base_url}/api/status", auth=auth)
print(resp.json())

# 2. 运行回测
payload = {"strategy": "rsi", "days": 30}
resp = requests.post(f"{base_url}/api/backtest", json=payload, auth=auth)
result = resp.json()
print(f"总收益率: {result['total_return_pct']}%")

# 3. 切换策略
requests.post(f"{base_url}/api/strategy/config", json={
    "file": "ma_cross.json",
    "config": {"params": {"fast_period": 10}}
}, auth=auth)

# 4. 重载
requests.post(f"{base_url}/api/strategy/reload", auth=auth)

# 5. 暂停交易
requests.post(f"{base_url}/api/trader/control", json={"action": "pause"}, auth=auth)
```

---

## 限流与安全

- 无内置限流，建议生产环境加 Nginx 限流
- 敏感 API（如 `/api/order`）建议仅允许本地访问或通过 VPN
- 配置文件中的 `mode: live` 时，谨慎开放 API 给外网

---

## 版本兼容性

API 可能会随版本演进而变化，重要变更会在 CHANGELOG 中说明。

**当前版本：** v1.0（2025-03-05）

---

## 参考

- Dashboard 后端：`src/dashboard/app.py`
- Trader 控制：`src/trader.py`
- 订单执行：`src/engine/executor.py`
