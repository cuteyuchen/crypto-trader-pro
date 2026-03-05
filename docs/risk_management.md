# 止损止盈配置详解

## 1. 概述

止损（Stop Loss）和止盈（Take Profit）是风险管理的核心工具：
- **止损**：当价格达到预设的亏损阈值时自动平仓，防止大额亏损
- **止盈**：当价格达到预设的盈利阈值时自动平仓，锁定利润

Crypto Trader Pro 支持在策略配置中直接设置止损止盈百分比，系统会自动计算触发价并执行。

---

## 2. 策略配置中的止损止盈

### 2.1 配置字段

在策略 JSON 文件中添加以下字段：

```json
{
  "name": "MA5_MA20_Cross",
  "type": "ma_cross",
  "symbol": "BTC/USDT",
  "timeframe": "1m",
  "params": {
    "fast_period": 5,
    "slow_period": 20
  },
  "position_size": 0.2,           // 仓位大小（占可用余额的比例）
  "stop_loss_pct": 0.05,          // 止损百分比（5%）
  "take_profit_pct": 0.10         // 止盈百分比（10%）
}
```

**字段说明：**

| 字段名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `position_size` | float | 1.0 | 每次买入使用的资金比例（0-1），0.2 表示 20% |
| `stop_loss_pct` | float | null | 止损百分比，0.05 表示 -5% |
| `take_profit_pct` | float | null | 止盈百分比，0.10 表示 +10% |

**注意：**
- `stop_loss_pct` 和 `take_profit_pct` 是可选的，可以只设置其中一个
- 设置为 `null` 或不包含该字段表示不使用

### 2.2 价格计算

系统在买入成交后自动计算止损价和止盈价：

**公式：**
- 止损触发价 = 入场价 × (1 - stop_loss_pct)
- 止盈触发价 = 入场价 × (1 + take_profit_pct)

**示例：**
```python
入场价 = $50,000
止损 = 5% → 止损价 = 50000 × 0.95 = $47,500
止盈 = 10% → 止盈价 = 50000 × 1.10 = $55,000
```

---

## 3. 订单执行流程

### 3.1 执行优先级

每根 K 线更新时，系统按以下顺序处理：

1. **止损/止盈检查**（最高优先级）
   - 如果当前价格达到止损价或止盈价，立即触发平仓
   - 平仓使用市价单

2. **策略信号处理**
   - 如果未触发止损止盈，则检查策略信号
   - 有买入信号且仓位未满 → 开仓
   - 有卖出信号且持有仓位 → 主动平仓

3. **风控检查**
   - 下单前检查是否超过最大持仓数、每日交易次数限制等

### 3.2 订单类型映射

| 场景 | 订单类型 | 本地模式 | 实盘模式 |
|------|---------|---------|----------|
| 策略买入 | MARKET | ✅ | ✅ |
| 策略卖出 | MARKET | ✅ | ✅ |
| 止损触发 | 市价平仓 | 条件检查后市价 | 交易所 STOP_LOSS 订单 |
| 止盈触发 | 市价平仓 | 条件检查后市价 | 交易所 TAKE_PROFIT 订单 |

---

## 4. 代码实现细节

### 4.1 Trader 中的止损止盈检查

`src/trader.py` 中的 `_check_stop_conditions()` 方法：

```python
async def _check_stop_conditions(self, price: float):
    for trade in self.open_trades:
        if trade.stop_loss_price is None and trade.take_profit_price is None:
            continue

        stop_loss_triggered = trade.stop_loss_price is not None and price <= trade.stop_loss_price
        take_profit_triggered = trade.take_profit_price is not None and price >= trade.take_profit_price

        if stop_loss_triggered:
            await self._execute_sell(trade, price, "止损触发")
        elif take_profit_triggered:
            await self._execute_sell(trade, price, "止盈触发")
```

**触发时机：** 每次价格更新（通过 `_check_signals()` 每秒调用）

### 4.2 Trade 对象

```python
class Trade:
    def __init__(self, trade_id, symbol, side, quantity, entry_price, strategy,
                 stop_loss_price=None, take_profit_price=None):
        self.id = trade_id
        self.symbol = symbol
        self.side = side  # 'long' 或 'short'
        self.quantity = quantity
        self.entry_price = entry_price
        self.current_price = entry_price
        self.pnl = 0.0
        self.strategy = strategy
        self.opened_at = datetime.now()
        self.closed_at = None
        self.status = "open"
        self.stop_loss_price = stop_loss_price
        self.take_profit_price = take_profit_price
```

### 4.3 买入时设置止损止盈

```python
# 在 Trader._execute_buy() 中
entry_price = result.get('avg_price', price)
stop_loss_pct = strategy_config.get('stop_loss_pct')
take_profit_pct = strategy_config.get('take_profit_pct')

stop_loss_price = None
take_profit_price = None

if stop_loss_pct is not None:
    stop_loss_price = entry_price * (1 - stop_loss_pct)
if take_profit_pct is not None:
    take_profit_price = entry_price * (1 + take_profit_pct)

trade = Trade(
    trade_id=result.get('order_id'),
    symbol=symbol,
    side='long',
    quantity=result.get('filled_quantity', quantity),
    entry_price=entry_price,
    strategy=order['strategy'],
    stop_loss_price=stop_loss_price,
    take_profit_price=take_profit_price
)
```

---

## 5. 订单类型支持

### 5.1 本地模拟模式（local）

`src/engine/executor.py` 中的 `_execute_stop_loss_local()` 和 `_execute_take_profit_local()`：

```python
async def _execute_stop_loss_local(self, symbol, side, quantity, stop_price, strategy, current_price):
    # 立即检查是否已触发
    if current_price <= stop_price:
        # 触发，执行市价卖出
        return await self._execute_market_local(symbol, "sell", quantity, current_price, strategy)
    else:
        # 未触发，返回 pending 状态（实际只是模拟返回）
        return {
            "success": True,
            "order_id": f"stop_loss_pending_{datetime.now().timestamp()}",
            "status": "pending",
            "message": "止损单已设定，等待触发"
        }
```

**说明：**
- 本地模式下，止损止盈只是条件检查，不会在交易所挂单
- 每次价格更新时，Trader 会检查触发条件并执行平仓

### 5.2 实盘模式（testnet/live）

`src/exchange/ccxt_exchange.py` 中的 `create_stop_loss_order()` 和 `create_take_profit_order()`：

```python
async def create_stop_loss_order(self, symbol, side, amount, stop_price, limit_price=None):
    # 使用 CCXT 的通用方法或交易所特定方法
    if hasattr(exchange, 'create_stop_loss_order'):
        order = await exchange.create_stop_loss_order(symbol, side, amount, stop_price, {'limitPrice': limit_price} if limit_price else {})
    elif exchange.has.get('createStopLossOrder'):
        order = await exchange.create_order(symbol, 'stop_loss', side, amount, None, {'stopPrice': stop_price, 'price': limit_price})
    else:
        # 回退：Binance 使用 STOP_LOSS_LIMIT 或 STOP_LOSS
        order_type = 'STOP_LOSS_LIMIT' if limit_price else 'STOP_LOSS'
        params = {'stopPrice': stop_price}
        if limit_price:
            params['price'] = limit_price
        order = await exchange.create_order(symbol, order_type, side, amount, None, params)
```

**支持的交易所：**
- **Binance**：`STOP_LOSS`（市价止损）或 `STOP_LOSS_LIMIT`（限价止损）
- **OKX**：`stop_order` 类型，支持 `stop_price` 参数

---

## 6. 使用示例

### 6.1 基础场景：同时设置止损止盈

```json
{
  "name": "MA_Crossover_With_SL_TP",
  "type": "ma_cross",
  "symbol": "BTC/USDT",
  "timeframe": "5m",
  "params": {
    "fast_period": 10,
    "slow_period": 30
  },
  "position_size": 0.1,
  "stop_loss_pct": 0.03,
  "take_profit_pct": 0.06
}
```
**效果：**
- 每次买入使用 10% 资金
- 价格下跌 3% 触发止损 → 自动卖出
- 价格上涨 6% 触发止盈 → 自动卖出
- 盈亏比 = 6% / 3% = 2:1

### 6.2 只设置止损（趋势跟踪）

```json
{
  "name": "RSI_Trend_Follow",
  "type": "rsi",
  "rsi_period": 14,
  "oversold": 30,
  "overbought": 70,
  "position_size": 0.2,
  "stop_loss_pct": 0.05
}
```
**说明：**
- RSI 超卖买入，不设止盈，让利润奔跑
- 仅当价格回落 5% 时止损
- 适合趋势较强的市场

### 6.3 只设置止盈（快速获利了结）

```json
{
  "name": "Scalping_Bollinger",
  "type": "bollinger",
  "bb_period": 20,
  "bb_std": 2.0,
  "position_size": 0.3,
  "take_profit_pct": 0.02
}
```
**说明：**
- 布林带突破买入，2% 利润即止盈
- 不设止损，依赖策略本身判断卖出信号
- 适合高频/剥头皮策略

---

## 7. 风控联动

### 7.1 与 RiskManager 的关系

止损止盈是**策略层面的风控**，与 `RiskManager`（全局风控）协同工作：

| 风控层级 | 触发条件 | 动作 |
|---------|---------|------|
| 止损/止盈 | 价格达到阈值 | 自动平仓 |
| 风控检查 | 下单时检查 | 拒绝订单（不执行） |
| 熔断 | 连续亏损或日亏损超限 | 暂停交易（设置 cooldown_until） |

### 7.2 风控配置文件（config/risk.json）

```json
{
  "max_position_size_pct": 0.5,
  "max_daily_loss_pct": 0.1,
  "max_trades_per_day": 100,
  "cooldown_period_sec": 300,
  "max_slippage_pct": 0.001,
  "emergency_stop_enabled": true
}
```

**说明：**
- `max_position_size_pct`：单笔订单最大仓位比例（风控检查）
- `max_daily_loss_pct`：日内累计亏损达到此比例触发熔断（暂停交易）
- 止损止盈在单笔交易层面保护，风控在全局层面保护

---

## 8. 常见问题

### Q1: 止损止盈不触发？

**检查点：**
1. 确保策略配置包含 `stop_loss_pct` 或 `take_profit_pct`
2. 验证字段为浮点数（如 `0.05`），不是字符串 `"5%"`
3. 查看日志：`INFO - 买入成功: ... 止损价: xxx, 止盈价: xxx`
4. 确认价格确实达到了触发价（检查策略输出的价格是否实时）

### Q2: 止损止盈在实盘未生效？

**可能原因：**
1. 交易所不支持 STOP_LOSS/TAKE_PROFIT 订单（某些小交易所）
2. CCXT 封装中使用了错误的方法
3. 订单参数错误（如价格格式）

**调试：**
- 在 `.env` 开启 DEBUG 日志：`LOG_LEVEL=DEBUG`
- 查看 `create_stop_loss_order` 的日志输出
- 使用交易所 API 直接查询订单状态

### Q3: 多个持仓如何止损？

当前系统每笔交易独立设置止损止盈价。
- 如果同时持有多个仓位（如连续买入），每笔都有独立的止损止盈
- 任何一个触发都会只平仓对应的那一笔（通过 `trade.id` 识别）

**场景：**
- 买入 0.1 BTC @ $50,000（止损 $47,500）
- 再次买入 0.1 BTC @ $48,000（止损 $45,600）
- 价格跌到 $47,000 时，第一笔触发止损，第二笔仍持仓

### Q4: 止损止盈可以动态调整吗？

目前暂不支持动态调整（如移动止损）。如需动态止损：

**自定义实现：**
1. 在策略类中维护 `highest_price` 变量
2. 在 `on_kline(new_price)` 中更新最高价
3. 如果 `new_price > highest_price`，更新止损价为 `highest_price * 0.98`
4. 调用 `executor.cancel_order(old_stop_order_id)` 和 `create_stop_loss_order(new_stop_price)`

---

## 9. 最佳实践

1. **合理设置比例**
   - 止损不宜过小（如 1% 容易被噪声触发）
   - 止损不宜过大（如 20% 风险过高）
   - 建议：2% - 10%

2. **盈亏比至少 1.5:1**
   - 如果止损 5%，止盈建议至少 7.5%
   - 这样即使胜率 40% 也能盈利

3. **结合策略信号**
   - 止损止盈是底线，不替代策略的主动平仓信号
   - 策略可以提前平仓（如趋势反转信号）

4. **实盘前充分测试**
   - 在 local 和 testnet 上验证止损止盈的触发及时性
   - 观察极端行情（如快速下跌）是否正常触发

---

## 参考

- 策略配置文件示例：`config/strategies/ma_cross.json`
- 执行器代码：`src/engine/executor.py`
- 交易引擎：`src/trader.py`
- CCXT 封装：`src/exchange/ccxt_exchange.py`
