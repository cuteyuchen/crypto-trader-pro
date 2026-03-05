# Crypto Trader Pro 🦀

> 基于 OpenClaw 自改进理念的 Pro 级加密货币自动交易系统

## ✨ 特性

- ✅ **双模式模拟交易**：本地模拟 + 币安 Testnet（可无缝切换到 Live）
- ✅ **实时 WebSocket 价格**：低延迟，多交易所支持
- ✅ **中文友好**：所有日志、错误提示、文档均为中文
- ✅ **一键部署**：Docker + docker-compose，30 秒启动
- ✅ **策略热更新**：修改 JSON 配置无需重启
- ✅ **内置策略**：MA5/MA20 交叉、RSI、布林带（持续增加）
- ✅ **风控完备**：仓位限制、止损熔断、每日限额
- ✅ **Web 看板**：实时持仓、盈亏、交易记录
- ✅ **QQ/Telegram 通知**：开仓/平仓/报警实时推送
- ✅ **自改进学习**：记录策略表现，持续优化参数

---

## 🚀 快速开始

### 1. 克隆项目（蟹老板创建仓库后 pull 下来）

```bash
cd ~/.openclaw/workspace/PROJECTS
git clone <你的仓库URL> crypto-trader-pro
cd crypto-trader-pro
cp .env.example .env  # 编辑 .env 填入配置
```

### 2. 配置

编辑 `config/modes.json`：

```json
{
  "mode": "local",         // local | testnet | live
  "exchange": "binance",   // 数据源交易所：binance | okx (仅影响 WS 行情)
  "initial_balance": 10000,
  "symbols": ["BTC/USDT"]
}
```

编辑 `.env` 文件（testnet/live 模式需填写 API Key）：

```bash
# Binance Testnet/Live
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_secret_here
BINANCE_TESTNET=true   # testnet 模式设为 true，live 设为 false

# OKX Testnet/Live
OKX_API_KEY=your_api_key_here
OKX_API_SECRET=your_secret_here
OKX_PASSPHRASE=your_passphrase   # OKX 需要
OKX_TESTNET=true

# 代理配置（如需要）
# HTTP_PROXY=http://127.0.0.1:7890
# HTTPS_PROXY=http://127.0.0.1:7890
# ALL_PROXY=http://127.0.0.1:7890
```

### 策略配置

编辑 `config/modes.json` 选择策略：

```json
{
  "strategy": "ma_cross"   // ma_cross | rsi
}
```

**MA 交叉策略** (`config/strategies/ma_cross.json`)：
```json
{
  "name": "MA5_MA20_Cross",
  "symbol": "BTC/USDT",
  "timeframe": "1m",
  "type": "ma_cross",
  "params": {
    "fast_period": 5,
    "slow_period": 20
  },
  "position_size": 0.2,
  "stop_loss_pct": 0.05,
  "take_profit_pct": 0.10
}
```

**RSI 策略** (`config/strategies/rsi.json`)：
```json
{
  "name": "RSI_14_70_30",
  "symbol": "BTC/USDT",
  "timeframe": "1m",
  "type": "rsi",
  "rsi_period": 14,
  "oversold": 30,
  "overbought": 70,
  "position_size": 0.2
}
```

### 3. 启动（Docker）

```bash
docker-compose up -d
```

查看日志：
```bash
docker logs -f crypto-trader-pro
```

### 4. 访问看板

打开浏览器：http://localhost:5000

看板特点：
- **响应式设计**：支持电脑、平板、手机访问（自动适配小屏幕）
- **实时数据**：每 5 秒自动刷新
- **显示内容**：
  - 运行状态（模式、策略状态、K线数量）
  - 账户余额（USDT）
  - 今日盈亏
  - 当前持仓（交易对、方向、数量、入场价、当前价、未实现盈亏）
  - 最近交易记录（时间、方向、数量、价格、手续费、盈亏）
  - 余额走势图（基于最近交易）

> 💡 **移动端访问**：界面已针对小屏幕优化，直接手机浏览器输入 `http://你的IP:5000` 即可访问（确保容器端口映射正确）。

---

## 📊 运行效果（本地模拟）

启动后你会看到：

```
INFO - 连接到 Binance WS: wss://stream.binance.com:9443/ws/btcusdt@kline_1m
INFO - Binance WS 已连接
INFO - 收到价格: BTCUSDT = $50320.50
INFO - [状态] USDT余额: $10000.00, 未实现盈亏: $0.00, 持仓数: 0
...
INFO - 策略信号: {'action': 'buy', 'reason': 'MA金叉'}
INFO - 买入成功: 数量 0.039682, 均价 $50320.50
INFO - 通知已记录: open_position - 开仓买入
INFO - [状态] USDT余额: $8000.00, 未实现盈亏: $0.00, 持仓数: 1
...
INFO - 策略信号: {'action': 'sell', 'reason': 'MA死叉'}
INFO - 卖出成功: 数量 0.039682, 盈亏 $123.45
INFO - 通知已记录: close_position - 平仓卖出
INFO - [状态] USDT余额: $8123.45, 未实现盈亏: $0.00, 持仓数: 0
```

---

## 🔧 Phase 2 高级功能详解

### 📈 回测使用详解

#### 1.1 CCXT 历史数据获取

系统内置了 `CCXTBacktestEngine`，可以从 Binance、OKX 等交易所获取真实历史数据。

**基本用法（Python）：**

```python
from src.backtest.ccxt_backtest import CCXTBacktestEngine
from datetime import datetime

# 创建回测引擎
engine = CCXTBacktestEngine(cache_dir="data/historical")

# 下载 2024 年 1 月 1 日到 12 月 31 日的 1 小时 K 线
df = engine.fetch_historical_data(
    exchange='binance',
    symbol='BTC/USDT',
    start_time=datetime(2024, 1, 1),
    end_time=datetime(2024, 12, 31),
    timeframe='1h',
    use_cache=True  # 自动缓存，避免重复下载
)

print(f"获取到 {len(df)} 条数据")
print(df.head())
```

**数据缓存：**
- 数据自动缓存到 `data/historical/` 目录（pickle 格式）
- 缓存文件名基于 exchange、symbol、时间范围生成 MD5 哈希
- 再次回测时自动读取缓存，速度极快
- 可通过 `engine.clear_cache(older_than_days=7)` 清理旧缓存

**支持的交易所：**
- Binance（推荐，数据质量高）
- OKX（备用，部分网络环境更稳定）

**支持的周期：**
- 分钟：`1m`, `5m`, `15m`, `30m`
- 小时：`1h`, `4h`, `1d`
- 天：`1d`

#### 1.2 回测执行与指标解读

**运行回测（Web 界面）：**
1. 访问 http://localhost:5000
2. 进入「回测」页面
3. 选择策略（如 `ma_cross`）
4. 设置回测天数（如 30 天）和初始资金
5. 点击「开始回测」

**回测结果指标：**

| 指标 | 说明 | 参考值 |
|------|------|--------|
| **总收益率** | 回测期间的总盈亏百分比 | >10% 良好 |
| **年化收益率** | 按 365 天年化的收益率 | >20% 优秀 |
| **最大回撤** | 从峰值到谷底的最大跌幅 | <20% 可接受，<10% 优秀 |
| **Sharpe 比率** | 风险调整后收益（越高越好） | >1 良好，>2 优秀 |
| **胜率** | 盈利交易的比例 | >50% 良好 |
| **盈亏比** | 平均盈利 / 平均亏损 | >1.5 良好 |
| **交易频率** | 平均每天交易次数 | 根据策略而定 |
| **平均持仓时间** | 平均每笔持仓天数 | 取决于策略周期 |

**API 调用示例：**

```bash
curl -X POST http://localhost:5000/api/backtest \
  -H "Content-Type: application/json" \
  -u admin:admin123 \
  -d '{
    "strategy": "ma_cross",
    "days": 30,
    "initial_balance": 10000
  }'
```

响应示例：

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
  "equity_curve": [...],
  "trades": [...]
}
```

**指标解读建议：**
- **最大回撤 > 20%**：风险较高，建议减小仓位或优化参数
- **Sharpe < 1**：收益不足以覆盖波动，策略可能无效
- **胜率 < 40%**：信号质量低，考虑切换策略或调整参数
- **交易频率过低**：数据周期可能太大，尝试缩小 timeframe

#### 1.3 回测数据可视化

回测结果包含 `equity_curve`（权益曲线）和 `trades`（交易明细），可用于绘制：
- 资金曲线图（含交易点位标记）
- 回撤图（Drawdown chart）
- 盈亏分布直方图

---

### 🛡️ 止损止盈配置

#### 2.1 策略配置中的止损止盈

在策略 JSON 配置文件中设置：

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
  "position_size": 0.2,           // 仓位大小（占余额的 20%）
  "stop_loss_pct": 0.05,          // 止损：5%
  "take_profit_pct": 0.10         // 止盈：10%
}
```

**计算方式：**
- 止损价 = 入场价 × (1 - stop_loss_pct)
- 止盈价 = 入场价 × (1 + take_profit_pct)

**示例：**
- 入场价 $50,000，止损 5%，止损价 = $47,500
- 止盈 10%，止盈价 = $55,000

#### 2.2 订单执行优先级

系统按以下顺序处理：
1. **止损/止盈触发**（最高优先级）— 价格到达止损/止盈价时自动平仓
2. **策略信号** — 常规买入/卖出信号
3. **风控检查** — 仓位、交易次数、熔断等

#### 2.3 订单类型支持

| 订单类型 | 本地模拟 (local) | 测试网 (testnet) | 实盘 (live) |
|---------|-----------------|------------------|-------------|
| 市价单 (MARKET) | ✅ | ✅ | ✅ |
| 限价单 (LIMIT) | ✅（挂单） | ✅ | ✅ |
| 止损单 (STOP_LOSS) | ✅（触发条件检查） | ✅ | ✅ |
| 止盈单 (TAKE_PROFIT) | ✅（触发条件检查） | ✅ | ✅ |

**注意：**
- 本地模拟模式下，止损止盈为**条件检查**（每根K线检查价格）
- 实盘模式下，止损止盈订单会提交到交易所，由交易所触发
- 支持的交易所：Binance、OKX（STOP_LOSS 和 TAKE_PROFIT 需确认交易所支持）

#### 2.4 动态止损（移动止损）

目前暂不支持移动止损（基于最高价调整止损价），这是 Phase 3 的功能。

**手动实现示例：**
```python
# 在策略中添加逻辑
if price > highest_since_entry:
    highest_since_entry = price
    new_stop = highest_since_entry * 0.98  # 2% 回落止损
    # 调用 executor 取消旧止损单，创建新止损单
```

---

### 📱 Telegram 通知配置

#### 3.1 通知架构

通知系统采用**文件队列**设计：
```
策略引擎 → Trader → NotificationManager → data/notifications.jsonl → 主 AI 会话（HEARTBEAT）→ QQ/Telegram
```

目前系统默认写入通知文件，由主 AI 会话的 HEARTBEAT 机制读取并发送到 QQ。Telegram 通知需要额外配置。

#### 3.2 配置 Telegram Bot

1. 创建 Telegram Bot：
   - 向 @BotFather 发送 `/newbot`
   - 命名机器人，获取 **Bot Token**
   - 例如：`1234567890:ABCdefGHIjkLmnopQRStuVWXyz1234567890`

2. 获取 Chat ID：
   - 向你的机器人发送一条消息
   - 访问：`https://api.telegram.org/bot<你的Token>/getUpdates`
   - 找到 `"chat":{"id":123456789,...}` 中的 `id`
   - 或者向机器人发送 `/start` 后查看更新

3. 配置环境变量（`.env` 文件）：

```bash
# Telegram 通知（可选）
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjkLmnopQRStuVWXyz1234567890
TELEGRAM_CHAT_ID=123456789
```

#### 3.3 通知事件类型

系统支持以下事件类型（由 `NotificationManager.send()` 发送）：

| 事件类型 | 标题 | 内容示例 | 触发时机 |
|---------|------|----------|----------|
| `open_position` | 开仓买入 | BTC/USDT 买入 0.01 @ $50000 | 买入成交后 |
| `close_position` | 平仓卖出 | 盈亏 +$123.45 | 卖出成交后（含止损止盈） |
| `error` | 系统错误 | 订单执行失败: ... | 异常发生 |
| `daily_summary` | 每日报告 | 账户余额、今日盈亏 | 每日 00:00 后首次运行 |

#### 3.4 手动发送 Telegram 通知

```python
from src.notifier import NotificationManager

notifier = NotificationManager("data")
notifier.send(
    event_type="open_position",
    title="开仓买入",
    content="BTC/USDT 买入 0.01 @ $50000",
    data={
        "symbol": "BTC/USDT",
        "price": 50000,
        "quantity": 0.01
    }
)
```

#### 3.5 主 AI 会话集成 Telegram

主 AI 会话（HEARTBEAT）需要增强以支持 Telegram。建议修改 `notification_dispatcher.py`：

```python
import os
import requests

class TelegramNotifier:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"

    def send(self, content):
        url = f"{self.base_url}/sendMessage"
        data = {
            "chat_id": self.chat_id,
            "text": content,
            "parse_mode": "HTML"
        }
        try:
            requests.post(url, data=data, timeout=10)
        except Exception as e:
            print(f"Telegram 发送失败: {e}")

# 在 HEARTBEAT 中
notifier = NotificationManager("data")
telegram = TelegramNotifier(
    os.getenv("TELEGRAM_BOT_TOKEN"),
    os.getenv("TELEGRAM_CHAT_ID")
)

def dispatch():
    pending = notifier.get_pending(last_check)
    for n in pending:
        # 格式化消息
        msg = f"📢 {n['title']}\n\n{n['content']}"
        # 发送到 QQ（已有）
        # ...
        # 发送到 Telegram
        if telegram:
            telegram.send(msg)
```

---

### 🔍 参数网格搜索教程

#### 4.1 什么是参数网格搜索？

网格搜索（Grid Search）是一种自动化的参数优化方法：
- 定义参数范围（如 RSI 周期：10-20，步长 2）
- 运行多次回测，遍历所有参数组合
- 根据指标（如 Sharpe、总收益）排序，找到最佳参数

#### 4.2 使用 ParameterOptimizer（已集成）

系统已内置 `ParameterOptimizer` 类，提供**参数建议**功能（基于近期表现分析）。

**示例：**

```python
from src.learning.performance_analyzer import ParameterOptimizer, PerformanceAnalyzer

analyzer = PerformanceAnalyzer("data/simulation.db")
optimizer = ParameterOptimizer(analyzer)

# 分析 RSI 策略近期表现
strategy_name = "RSI_14_70_30"
config = {
    "type": "rsi",
    "rsi_period": 14,
    "oversold": 30,
    "overbought": 70
}

suggestion = optimizer.suggest_improvements(strategy_name, config)
print("近期表现:", suggestion['performance'])
print("改进建议:", suggestion['suggestions'])
print("推荐新配置:", suggestion['new_config'])
```

**输出示例：**
```
近期表现: {
  'strategy': 'RSI_14_70_30',
  'period_days': 7,
  'total_trades': 15,
  'win_rate': 33.3,
  'avg_pnl': -5.23,
  'total_pnl': -78.45,
  'sharpe': -0.45,
  'max_drawdown': 120.5
}
改进建议: ['RSI 胜率偏低，扩大超买超卖阈值至 25/75']
推荐新配置: {
  'type': 'rsi',
  'rsi_period': 14,
  'oversold': 25,
  'overbought': 75
}
```

#### 4.3 完整网格搜索（需扩展）

当前 `ParameterOptimizer` 仅提供**规则化建议**，如需完整的网格搜索（遍历超参数空间），需要扩展。

**实现方案：**

1. 定义参数网格：

```python
param_grid = {
    "rsi_period": [10, 14, 20],
    "oversold": [25, 30, 35],
    "overbought": [65, 70, 75]
}
```

2. 遍历所有组合：

```python
from src.backtest.engine import BacktestEngine
from src.backtest.metrics import BacktestMetrics

results = []
for period in param_grid['rsi_period']:
    for oversold in param_grid['oversold']:
        for overbought in param_grid['overbought']:
            # 构建策略配置
            strategy_cfg = {
                "type": "rsi",
                "rsi_period": period,
                "oversold": oversold,
                "overbought": overbought
            }
            # 运行回测
            engine = BacktestEngine(strategy_cfg, initial_balance=10000)
            result = engine.run(days=30)
            metrics = BacktestMetrics.calculate(result['equity_curve'], result['trades'])
            results.append({
                'params': strategy_cfg,
                'total_return': metrics['total_return_pct'],
                'sharpe': metrics['sharpe_ratio'],
                'max_dd': metrics['max_drawdown_pct']
            })
```

3. 排序最佳参数：

```python
sorted_results = sorted(results, key=lambda x: x['sharpe'], reverse=True)
best = sorted_results[0]
print(f"最佳参数: {best['params']}, Sharpe: {best['sharpe']}, 收益: {best['total_return']}%")
```

#### 4.4 网格搜索界面（Web）

目前后端 API 已支持回测，前端可扩展「参数优化」页面：
- 选择策略类型
- 设置参数范围（开始、结束、步长）
- 提交批量回测任务（异步）
- 展示结果表格（按 Sharpe/收益排序）
- 一键应用最佳参数到配置文件

---

### 🚀 多策略部署示例

#### 5.1 多策略支持架构

系统已内置多策略支持，通过 `StrategyEngine` 管理单一活跃策略。当前架构：
- 数据流统一进入 `StrategyEngine`
- 策略配置从 `config/strategies/*.json` 文件加载
- 通过 `/api/strategy/reload` 热重载切换策略

#### 5.2 创建新策略

**步骤 1：创建策略配置文件**

在 `config/strategies/` 目录创建 JSON 文件，如 `my_custom.json`：

```json
{
  "name": "MyCustom_RSI_25_75",
  "type": "rsi",
  "symbol": "BTC/USDT",
  "timeframe": "1m",
  "rsi_period": 14,
  "oversold": 25,
  "overbought": 75,
  "position_size": 0.2,
  "stop_loss_pct": 0.05,
  "take_profit_pct": 0.10
}
```

**步骤 2：切换策略（无需重启）**

用 Web 界面或 API 修改 `modes.json` 中的 `strategy` 字段，然后调用重载：

```bash
# 通过 API 重载
curl -X POST http://localhost:5000/api/strategy/reload \
  -u admin:admin123
```

或访问「策略」页面，直接选择策略文件并点击「重载」。

**步骤 3：验证策略运行**

检查日志：
```
INFO - 策略已重载: MyCustom_RSI_25_75
INFO - 策略信号: {'action': 'buy', 'reason': 'RSI 超卖'}
```

#### 5.3 多策略并行（Phase 3）

当前仅支持**单一策略**运行。Phase 3 计划：
- 多策略并发（每策略独立资金池）
- 策略间互不影响
- 统一风控+独立统计

设计思路：
```
Trader
├── StrategyWorker 1  → 策略 A（资金池 $5000）
├── StrategyWorker 2  → 策略 B（资金池 $5000）
└── Global RiskManager（全局风控）
```

---

### 📡 API 参考（完整列表）

所有 API 均需 HTTP Basic Auth（默认 admin/admin123），可通过环境变量 `DASHBOARD_USER` 和 `DASHBOARD_PASS` 修改。

#### 系统状态

| 方法 | 路径 | 说明 | 返回 |
|------|------|------|------|
| GET | `/api/status` | 系统运行状态 | `{mode, running, strategy, exchange, symbol}` |
| GET | `/health` | 健康检查 | `{status: 'ok'}` |

#### 账户与持仓

| 方法 | 路径 | 说明 | 返回 |
|------|------|------|------|
| GET | `/api/balance` | 账户余额（USDT） | `{'USDT': 10000.0}` |
| GET | `/api/positions` | 当前持仓列表 | [{symbol, side, quantity, entry_price, current_price, unrealized_pnl}] |

#### 交易

| 方法 | 路径 | 说明 | 请求体 | 返回 |
|------|------|------|--------|------|
| POST | `/api/order` | 手动下单（仅 local） | `{symbol, side, quantity, type, price}` | `{success, order_id, filled, avg_price, fee, pnl}` |
| GET | `/api/trades` | 最近交易记录 | `?limit=20` | 交易对象数组 |
| GET | `/api/trades/active` | 活跃订单（Trader） | - | 订单列表 |
| GET | `/api/trades/history` | 历史订单 | `?limit=100` | 订单列表 |
| POST | `/api/trader/control` | 控制 Trader | `{action: start\|stop\|pause\|resume\|force_sell}` | `{success}` |

#### 策略管理

| 方法 | 路径 | 说明 | 请求体 | 返回 |
|------|------|------|--------|------|
| GET | `/api/strategies` | 列出所有策略配置 | - | 策略列表 [{name, type, file, config}] |
| POST | `/api/strategy/reload` | 热重载策略配置 | - | `{success}` |
| POST | `/api/strategy/config` | 更新策略参数并重载 | `{file, config}` | `{success}` |
| GET | `/api/trader/status` | Trader 状态 | - | `{running, auto_trade, open_trades_count, total_pnl, win_rate}` |
| GET | `/api/trader/stats` | Trader 统计信息 | - | 详细统计 |
| GET|POST | `/api/trader/config` | 获取/更新运行时配置 | `{auto_trade, max_open_trades, stake_amount}` | `{success}` |

#### 回测

| 方法 | 路径 | 说明 | 请求体 | 返回 |
|------|------|------|--------|------|
| POST | `/api/backtest` | 运行回测（详细指标） | `{strategy, days, initial_balance}` | 回测结果含 metrics |

**回测响应字段：**

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
  "equity_curve": [...],
  "trades": [...],
  "metrics": { ... }  // 同层级，重复便于前端
}
```

#### 配置

| 方法 | 路径 | 说明 | 请求体 | 返回 |
|------|------|------|--------|------|
| GET | `/api/config` | 获取 modes 配置 | - | `{mode, exchange, strategy, ...}` |
| POST | `/api/config` | 更新 modes 配置 | 同 GET 返回格式 | `{success}` |

**注意：** 修改配置后需重启服务或调用 `/api/strategy/reload` 生效。

#### 日志

| 方法 | 路径 | 说明 | 返回 |
|------|------|------|------|
| GET | `/api/logs` | 获取最近 100 行日志 | 文本 |
| GET | `/api/logs/stream` | SSE 实时日志流 | text/event-stream |

---

## 🛠️ 开发进度

- [x] 项目骨架
- [x] WebSocket Binance 客户端
- [x] WebSocket OKX 客户端（推荐使用）
- [x] 本地模拟数据库（持仓/余额/交易）
- [x] 策略引擎 + MA 交叉策略
- [x] 策略引擎 + RSI 策略
- [x] 策略引擎 + 布林带策略
- [x] 策略引擎 + MACD 策略
- [x] 订单执行器（local 模式）
- [x] 订单执行器（testnet/live 模式）✅ CCXT 集成
- [x] 风控管理器
- [x] Docker 部署
- [x] Web 看板（Flask + Chart.js）✅ 移动端适配
- [x] QQ Bot 通知集成 ✅ 通过 HEARTBEAT 自动分发
- [x] 多策略支持（配置切换）
- [x] 自改进学习集成（性能分析 + 参数建议）
- [x] **CCXT 历史数据回测** ✅（真实交易所数据）
- [x] **详细回测指标** ✅（Sharpe、胜率、盈亏比等）
- [x] **止损止盈支持** ✅（市价/限价/止损/止盈）
- [x] **参数优化建议** ✅（基于近期表现）

✅ **Phase 2 核心功能全部完成！**

预计完成时间：0.5 天（已全部完成）

---

## 🔍 技术栈