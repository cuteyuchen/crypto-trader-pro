# 回测系统详细指南

## 概述

Crypto Trader Pro 内置了完整的回测引擎，支持：
- 从真实交易所获取历史数据（CCXT）
- 多种时间周期（1m, 5m, 1h, 1d 等）
- 详细性能指标计算（Sharpe, 最大回撤, 胜率, 盈亏比）
- 可视化支持（权益曲线、交易点位）
- 数据自动缓存，加速后续回测

---

## CCXT 历史数据获取

### 1. CCXTBacktestEngine 详解

`src/backtest/ccxt_backtest.py` 提供了 `CCXTBacktestEngine` 类，专门负责从交易所获取历史 K 线数据。

**核心方法：**

```python
from src.backtest.ccxt_backtest import CCXTBacktestEngine
from datetime import datetime

engine = CCXTBacktestEngine(cache_dir="data/historical")
df = engine.fetch_historical_data(
    exchange='binance',      # 'binance' 或 'okx'
    symbol='BTC/USDT',       # 交易对
    start_time=datetime(2024, 1, 1),
    end_time=datetime(2024, 12, 31),
    timeframe='1h',          # 时间周期
    use_cache=True           # 使用缓存（默认 True）
)
```

**返回格式：**
- `pandas.DataFrame`，包含列：`timestamp`, `open`, `high`, `low`, `close`, `volume`
- 索引已重置，按时间升序排列
- 已去重、过滤时间范围

### 2. 缓存机制

- 缓存文件位于 `data/historical/*.pkl`
- 文件名基于 `exchange_symbol_start_end` 的 MD5 哈希
- 自动检测缓存，避免重复下载
- 可通过 `engine.clear_cache(older_than_days=N)` 清理旧缓存

**示例：清理 7 天前的缓存**
```python
engine.clear_cache(older_than_days=7)
```

### 3. 数据完整性

- 自动处理 CCXT 的 1000 条限制，循环下载直到目标时间范围
- 时间间隔计算基于 `timeframe`，避免数据重叠或遗漏
- 过滤交易所返回的多余数据（确保 `timestamp < end_time`）

---

## 回测执行流程

### BacktestEngine 类

`src/backtest/engine.py` 中的 `BacktestEngine` 负责运行回测逻辑。

**基本用法：**

```python
from src.backtest.engine import BacktestEngine

# 加载策略配置（从 JSON 文件）
import json
with open('config/strategies/ma_cross.json') as f:
    strategy_cfg = json.load(f)

# 创建回测引擎
engine = BacktestEngine(strategy_cfg, initial_balance=10000)

# 方式 1: 传入 pandas DataFrame（CCXT 下载的真实数据）
result = engine.run(klines_df=df)

# 方式 2: 传入 List[Dict] 格式的 K 线
result = engine.run(data=klines_list)

# 方式 3: 生成模拟数据（测试用）
result = engine.run(days=30)  # 生成 30 天 1分钟K线
```

**返回结果包含：**
```json
{
  "strategy": "MA5_MA20_Cross",
  "initial_balance": 10000,
  "final_balance": 11234.56,
  "total_pnl": 1234.56,
  "total_return_pct": 12.35,
  "equity_curve": [...],
  "trades": [...]
}
```

### 策略信号获取

回测引擎内部通过 `StrategyEngine` 调用策略的 `on_kline()` 方法：
- **逐条模式**：RSI、MACD 等策略，每次传入单根 K 线，策略内部维护 buffer
- **DataFrame 模式**：MA、布林带等策略，传入完整 DataFrame，策略整体计算

---

## 指标计算与解读

`src/backtest/metrics.py` 提供了 `BacktestMetrics` 类，计算所有回测指标。

### 指标列表

| 指标名 | 说明 | 计算方法 |
|-------|------|----------|
| `total_return_pct` | 总收益率（%） | `(final - initial) / initial * 100` |
| `annual_return_pct` | 年化收益率（%） | `(1 + total_return)^(365/days) - 1` |
| `max_drawdown_pct` | 最大回撤（%） | 权益曲线从峰值到谷底的最大跌幅 |
| `sharpe_ratio` | 夏普比率 | 日收益均值 / 日收益标准差 × √252 |
| `win_rate_pct` | 胜率（%） | 盈利交易数 / 总交易数 |
| `profit_loss_ratio` | 盈亏比 | 总盈利 / 总亏损 |
| `trades_per_day` | 日均交易次数 | 总交易数 / 回测天数 |
| `avg_holding_days` | 平均持仓天数 | 所有交易的持仓时间均值 |

**示例：**

```python
from src.backtest.metrics import BacktestMetrics

metrics = BacktestMetrics.calculate(
    equity_curve=result['equity_curve'],
    trades=result['trades']
)

print(f"总收益率: {metrics['total_return_pct']}%")
print(f"夏普比率: {metrics['sharpe_ratio']}")
print(f"最大回撤: {metrics['max_drawdown_pct']}%")
print(f"胜率: {metrics['win_rate_pct']}%")
```

### 指标解读建议

| 指标 | 优秀 | 良好 | 可接受 | 差 |
|------|------|------|--------|-----|
| 年化收益率 | >30% | 20-30% | 10-20% | <10% |
| 最大回撤 | <5% | 5-10% | 10-20% | >20% |
| 夏普比率 | >2 | 1-2 | 0.5-1 | <0.5 |
| 胜率 | >60% | 50-60% | 40-50% | <40% |
| 盈亏比 | >2 | 1.5-2 | 1-1.5 | <1 |

**综合判断：**
- **Sharpe > 1.5 且 最大回撤 < 10%** → 优秀，适合实盘
- **Sharpe < 0.5 或 最大回撤 > 20%** → 策略可能无效，需优化或放弃
- **胜率 < 40% 且 盈亏比 < 1** → 信号质量差，建议调整参数或换策略

---

## Web 界面回测

### 回测页面功能

访问 `http://localhost:5000` → 「回测」标签页。

**表单字段：**
- **策略**：下拉选择，列出 `config/strategies/*.json` 中的策略
- **回测天数**：滑动选择 1-90 天
- **初始资金**：输入框，默认 10000

**操作：**
1. 选择策略（如 `ma_cross`）
2. 设置天数（如 30）
3. 点击「开始回测」
4. 等待 5-30 秒（取决于数据量和天数）
5. 查看结果面板

**结果展示：**
- **核心指标卡片**：收益率、年化、最大回撤、Sharpe、胜率
- **资金曲线图**：使用 Chart.js 绘制
- **交易明细表格**：时间、方向、价格、盈亏

### API 接口

**POST `/api/backtest`**

请求体：
```json
{
  "strategy": "ma_cross",
  "days": 30,
  "initial_balance": 10000
}
```

响应：
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
    ...
  ],
  "trades": [
    {"time": "2024-01-01T10:30:00", "side": "buy", "quantity": 0.02, "price": 45000, ...},
    ...
  ]
}
```

---

## 常见问题

### Q1: 回测速度慢怎么办？

**原因分析：**
- 首次回测需要从交易所下载数据（网络速度）
- 数据量大（90天 1分钟K线约 129,600 条）

**优化建议：**
1. 使用缓存：`use_cache=True`（默认开启）
2. 增加时间周期：`timeframe='1h'` 或 `'4h'` 减少数据量
3. 缩短回测天数
4. 使用本地缓存的数据文件（避免重复下载）

### Q2: 回测结果与实盘差异大？

可能原因：
- **交易成本未计入**：当前回测未精确计算手续费和滑点
- **流动性影响**：大单在实盘可能影响价格
- **信号延迟**：回测假设即时成交，实盘可能有延迟

**改进：**
- 在回测中模拟手续费（可按交易金额的 0.1% 扣除）
- 考虑滑点（可按价格的 0.1% 估算）
- 使用 `limit` 订单而非 `market` 订单模拟

### Q3: 如何验证回测准确性？

**检查点：**
1. 对比手动计算的小样本（如最近 10 笔交易）
2. 查看交易明细，确认买卖逻辑符合策略规则
3. 验证权益曲线是否平滑，无明显跳变
4. 检查是否有重复交易或遗漏

### Q4: 支持哪些策略类型？

目前已实现：
- `ma_cross`：移动平均线交叉
- `rsi`：RSI 超买超卖
- `bollinger`：布林带突破
- `macd`：MACD 金叉死叉

**添加自定义策略：**
1. 在 `src/engine/strategies/` 创建新类，继承 `Strategy` 基类
2. 实现 `on_kline()` 方法，返回 `{'action': 'buy'/'sell'/'hold', 'reason': '...'}` 或 `None`
3. 在 `config/strategies/` 创建配置文件，`type` 字段匹配策略类名

---

## 最佳实践

1. **先用模拟数据测试**：`engine.run(days=7)` 快速验证逻辑
2. **再用真实数据回测**：下载 30-90 天数据，观察稳定性
3. **参数优化**：使用 `ParameterOptimizer` 或手动网格搜索
4. **样本外测试**：用最近 7 天数据验证（避免过拟合）
5. **逐步实盘**：先用小额 testnet 验证执行，再切换到 live

---

## 参考代码

完整回测脚本示例（CLI 工具）：

```python
# tools/backtest_cli.py
import argparse
from src.backtest.ccxt_backtest import CCXTBacktestEngine
from src.backtest.engine import BacktestEngine
from src.backtest.metrics import BacktestMetrics
import json

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--strategy', default='ma_cross')
    parser.add_argument('--days', type=int, default=30)
    parser.add_argument('--exchange', default='binance')
    parser.add_argument('--output', default='backtest_result.json')
    args = parser.parse_args()

    # 1. 下载历史数据
    from datetime import datetime, timedelta
    end = datetime.now()
    start = end - timedelta(days=args.days)

    engine = CCXTBacktestEngine()
    df = engine.fetch_historical_data(
        exchange=args.exchange,
        symbol='BTC/USDT',
        start_time=start,
        end_time=end,
        timeframe='1h'
    )

    # 2. 加载策略配置
    with open(f'config/strategies/{args.strategy}.json') as f:
        strategy_cfg = json.load(f)

    # 3. 运行回测
    backtester = BacktestEngine(strategy_cfg, initial_balance=10000)
    result = backtester.run(klines_df=df)

    # 4. 计算指标
    metrics = BacktestMetrics.calculate(result['equity_curve'], result['trades'])
    result['metrics'] = metrics

    # 5. 保存结果
    with open(args.output, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"回测完成，结果保存到 {args.output}")
    print(f"总收益率: {metrics['total_return_pct']}%")
    print(f"Sharpe: {metrics['sharpe_ratio']}")

if __name__ == '__main__':
    main()
```

运行：
```bash
python tools/backtest_cli.py --strategy rsi --days 30 --output result.json
```

---

## 下一步

- 收集更多历史数据（建议至少 1 年）
- 尝试不同参数组合，找到最优配置
- 在 testnet 上线验证策略稳定性
- 参考 PRD.md 中的 Phase 3 规划，探索高级功能
