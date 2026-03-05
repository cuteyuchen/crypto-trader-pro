# 多策略部署指南

## 1. 策略架构概述

Crypto Trader Pro 当前采用**单策略引擎**架构：

```
┌──────────────┐
│   策略配置     │ ← config/strategies/*.json
│  (mode.json) │ ← config/modes.json 指定 strategy 字段
└──────────────┘
       ↓
┌──────────────┐
│ StrategyEngine │ ← 加载并运行当前活跃策略
│ .check_signal()│ ← 每秒钟被 Trader 调用
└──────────────┘
       ↓
┌──────────────┐
│    Trader     │ ← 自动交易循环（监控信号、执行订单）
│              │ ← 维护 open_trades/closed_trades
└──────────────┘
```

**关键特性：**
- **热重载**：修改策略配置后，调用 `/api/strategy/reload` 无需重启
- **多策略文件**：`config/strategies/` 可存放多个 `.json` 策略文件
- **运行时切换**：通过 Web 或 API 选择使用哪个策略

---

## 2. 创建新策略

### 2.1 策略配置文件结构

所有策略使用 JSON 格式，通用字段：

| 字段 | 必需 | 类型 | 说明 |
|------|------|------|------|
| `name` | ✅ | string | 策略名称（显示用） |
| `type` | ✅ | string | 策略类型，对应 `src/engine/strategies/` 中的类名 |
| `symbol` | ✅ | string | 交易对（如 `BTC/USDT`） |
| `timeframe` | ✅ | string | K 线周期（如 `1m`, `5m`, `1h`） |
| `position_size` | ❌ | float | 仓位比例（0-1），默认 1.0 |
| `stop_loss_pct` | ❌ | float | 止损百分比（如 0.05） |
| `take_profit_pct` | ❌ | float | 止盈百分比（如 0.10） |

**策略特有字段**：根据 `type` 不同而变化

**示例 - MA 交叉策略：**
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
  "position_size": 0.2,
  "stop_loss_pct": 0.05,
  "take_profit_pct": 0.10
}
```

**示例 - RSI 策略：**
```json
{
  "name": "RSI_14_70_30",
  "type": "rsi",
  "symbol": "BTC/USDT",
  "timeframe": "1m",
  "rsi_period": 14,
  "oversold": 30,
  "overbought": 70,
  "position_size": 0.2,
  "stop_loss_pct": 0.05,
  "take_profit_pct": 0.10
}
```

### 2.2 策略类型（type）映射

每个 `type` 对应一个策略类文件：

| type 值 | 文件路径 | 类名 |
|---------|----------|------|
| `ma_cross` | `src/engine/strategies/ma_cross.py` | `MACrossStrategy` |
| `rsi` | `src/engine/strategies/rsi_strategy.py` | `RSIStrategy` |
| `bollinger` | `src/engine/strategies/bollinger_bands.py` | `BollingerStrategy` |
| `macd` | `src/engine/strategies/macd.py` | `MACDStrategy` |

**自定义策略：**
1. 在 `src/engine/strategies/` 创建新文件（如 `my_strategy.py`）
2. 实现 `on_kline()` 方法，返回信号字典
3. 在策略配置中设置 `type` 为 `"my_strategy"`（文件名去掉 `.py`）

---

## 3. 策略切换（热重载）

### 3.1 修改 modes.json

编辑 `config/modes.json`，修改 `strategy` 字段为策略文件名（不含 `.json` 后缀）：

```json
{
  "mode": "local",
  "exchange": "okx",
  "initial_balance": 10000,
  "symbols": ["BTC/USDT"],
  "strategy": "ma_cross"   ← 改成 "bollinger" 或其他策略文件名
}
```

### 3.2 调用热重载 API

```bash
curl -X POST http://localhost:5000/api/strategy/reload \
  -u admin:admin123
```

**日志输出：**
```
INFO - 策略已重载: Bollinger_Bands_20_2
INFO - 策略信号: {'action': 'buy', 'reason': '价格突破上轨'}
```

### 3.3 Web 界面切换

访问 http://localhost:5000 → 「策略」页面：
- 查看所有策略列表
- 点击策略卡片查看详情
- 点击「重载」按钮即可切换

---

## 4. 多策略并行（Phase 3 规划）

当前系统仅支持单一策略运行。Phase 3 计划实现多策略并发。

### 4.1 设计目标

```
┌─────────────┐
│ Trader      │ ← 全局风控（总持仓限制、日亏损限额）
├─────────────┤
│ Worker 1    │ → 策略 A（资金池 $5000）
│   StrategyEngine
│   OrderExecutor（独立子账户）
│   RiskManager（独立限额）
├─────────────┤
│ Worker 2    │ → 策略 B（资金池 $5000）...
└─────────────┘
```

**资金分配方案：**
- 方案 1：总资金等分（如 $10000 分给 2 个策略，各 $5000）
- 方案 2：按配置文件设置 `stake_amount` 独立分配
- 方案 3：动态比例（根据近期表现调整）

### 4.2 配置扩展

新增多策略配置 `config/multi_strategies.json`：

```json
{
  "enabled": true,
  "strategies": [
    {
      "file": "ma_cross.json",
      "allocated_balance": 5000,
      "max_open_trades": 2,
      "auto_trade": true
    },
    {
      "file": "rsi.json",
      "allocated_balance": 5000,
      "max_open_trades": 3,
      "auto_trade": true
    }
  ],
  "global_risk": {
    "max_daily_loss_pct": 0.1
  }
}
```

### 4.3 代码调整

- `Trader` 改为 `StrategyWorker`，每个 worker 独立运行
- `main.py` 启动多个 worker 线程
- 每个 worker 拥有独立的 `SimulationDB` 或独立的 API 子账户

---

## 5. 策略对比与性能统计

### 5.1 查看各策略表现

`PerformanceAnalyzer.compare_strategies()` 可对比多个策略：

```python
from src.learning.performance_analyzer import PerformanceAnalyzer

analyzer = PerformanceAnalyzer("data/simulation.db")
strategies = ["MA5_MA20_Cross", "RSI_14_70_30", "Bollinger_Bands_20_2"]

comparison = analyzer.compare_strategies(strategies, days=7)

for s in comparison:
    print(f"{s['strategy']}: 交易 {s['total_trades']} 笔, 胜率 {s['win_rate']}%, 盈亏 ${s['total_pnl']:.2f}")
```

### 5.2 使用数据库查看

如果需要跨策略统计，可直接查询数据库 `trades` 表：

```sql
SELECT strategy, COUNT(*) as trades, SUM(pnl) as total_pnl, AVG(pnl) as avg_pnl
FROM trades
WHERE date(executed_at) >= date('now', '-7 days')
GROUP BY strategy
ORDER BY total_pnl DESC;
```

---

## 6. 常见问题

### Q1: 切换策略后持仓怎么处理？

**当前行为：**
- 重载策略**不会**自动平仓
- 旧持仓继续存在，新信号按新策略执行
- 可能出现新旧策略同时持仓（如果策略都开多）

**手动处理：**
```bash
# 1. 停止 Trader
curl -X POST http://localhost:5000/api/trader/control \
  -H "Content-Type: application/json" \
  -u admin:admin123 \
  -d '{"action": "stop"}'

# 2. 强制平仓所有持仓（通过 /api/order 卖出）
# 或等待止损/止盈自动触发

# 3. 切换策略并重载
# 编辑 modes.json 或使用 /api/strategy/config
curl -X POST http://localhost:5000/api/strategy/reload ...

# 4. 重新启动 Trader
curl -X POST http://localhost:5000/api/trader/control \
  -d '{"action": "start"}'
```

### Q2: 可以多个策略同时运行吗？

**当前版本不支持**。只支持单一策略运行。
**Workaround：** 运行多个 Docker 容器实例，每个使用不同策略（需独立数据目录和端口）。

```bash
# 实例 1：MA 策略
docker run -d -p 5000:5000 ... crypto-trader-pro

# 实例 2：RSI 策略（修改配置后）
docker run -d -p 5001:5000 ... crypto-trader-pro
```

### Q3: 策略文件命名规范？

建议：`<策略名>.json`，如：
- `ma_cross.json`
- `rsi.json`
- `bollinger_bands.json`

文件名（不含 `.json`）将作为 `modes.json` 中 `strategy` 字段的值。

### Q4: 如何验证策略切换成功？

查看日志：
```
INFO - 重载策略配置: rsi
INFO - 策略引擎已初始化: RSI_14_70_30
INFO - 策略信号: {'action': 'buy', 'reason': 'RSI 超卖'}
```

或调用 API：
```bash
curl http://localhost:5000/api/strategy -u admin:admin123
```
返回当前策略状态。

---

## 7. 最佳实践

1. **策略命名清晰**：名称应反映策略类型和参数（如 `RSI_14_30_70`）
2. **版本控制**：修改策略文件前先备份，或使用 Git 管理
3. **分阶段测试**：
   - 先在 local 模式运行 1 天
   - 检查日志和看板，确保按预期运行
   - 再用 testnet 验证订单执行
4. **记录策略表现**：定期保存回测报告和实盘数据，便于对比
5. **单一策略专注**：避免频繁切换，给策略足够时间表现（至少 1 周）

---

## 8. 扩展：自定义策略开发

### 8.1 代码结构

在 `src/engine/strategies/` 创建文件，例如 `my_strategy.py`：

```python
from .base import Strategy
from datetime import datetime

class MyStrategy(Strategy):
    """我的自定义策略"""

    def __init__(self, config: dict):
        super().__init__(config)
        # 从 config 读取参数
        self.period = config.get('period', 20)
        self.threshold = config.get('threshold', 0.02)
        self.buffer = []  # 维护 K 线缓存

    def on_kline(self, kline: dict):
        """
        每根 K 线调用一次

        Args:
            kline: {
                'timestamp': datetime,
                'open': float,
                'high': float,
                'low': float,
                'close': float,
                'volume': float
            }

        Returns:
            {'action': 'buy'/'sell'/'hold', 'reason': '...'} 或 None（无信号）
        """
        # 更新缓存
        self.buffer.append(kline['close'])
        if len(self.buffer) > self.period:
            self.buffer.pop(0)

        # 计算指标
        ma = sum(self.buffer) / len(self.buffer)
        current = kline['close']

        # 生成信号
        if current > ma * (1 + self.threshold):
            return {'action': 'buy', 'reason': f'价格突破 MA+{self.threshold*100}%'}
        elif current < ma * (1 - self.threshold):
            return {'action': 'sell', 'reason': f'价格跌破 MA-{self.threshold*100}%'}
        else:
            return None
```

### 8.2 配置文件

在 `config/strategies/` 创建 `my_strategy.json`：

```json
{
  "name": "MyStrategy_MA20_2pct",
  "type": "my_strategy",
  "symbol": "BTC/USDT",
  "timeframe": "5m",
  "period": 20,
  "threshold": 0.02,
  "position_size": 0.2
}
```

### 8.3 重启与测试

```bash
# 选择新策略
echo '{"strategy": "my_strategy"}' > config/modes.json

# 重启服务或热重载
curl -X POST http://localhost:5000/api/strategy/reload -u admin:admin123

# 观察日志
docker logs -f crypto-trader-pro
```

---

## 9. 参考

- 策略基类：`src/engine/strategies/base.py`
- 现有策略实现：`src/engine/strategies/ma_cross.py`, `rsi_strategy.py`, ...
- Dashboard 策略 API：`src/dashboard/app.py` 中的 `/api/strategies` 和 `/api/strategy/reload`
- PRD 文档：`docs/PRD.md`（策略扩展规划）

---

## 10. 下一步

- 实现多策略并行（Phase 3）
- 策略间独立资金池
- 策略表现对比报告
- 策略参数自动优化（基于网格搜索结果）
