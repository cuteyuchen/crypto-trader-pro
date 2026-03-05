# CCXT 历史数据回测引擎 - 集成指南

## 概述

`src/backtest/ccxt_backtest.py` 实现了 `CCXTBacktestEngine` 类，用于从真实交易所获取历史数据并支持回测。

## 核心功能

### 1. 获取历史数据

```python
from src.backtest.ccxt_backtest import CCXTBacktestEngine
from datetime import datetime, timedelta

# 创建引擎
engine = CCXTBacktestEngine(cache_dir="data/historical")

# 获取 BTC/USDT 的最近7天1小时K线
df = engine.fetch_historical_data(
    exchange='binance',
    symbol='BTC/USDT',
    start_time=datetime.now() - timedelta(days=7),
    end_time=datetime.now(),
    timeframe='1h',
    use_cache=True  # 默认使用缓存
)
```

### 2. 缓存机制

- 缓存位置：`data/historical/{hash}.pkl`
- 文件名基于 (exchange, symbol, start_time, end_time) 的 MD5 哈希
- 自动复用缓存，避免重复下载
- 可通过 `engine.clear_cache()` 清理

### 3. 支持的交易所

- `binance` (币安)
- `okx` (OKX)

更多交易所可以通过修改 `supported_exchanges` 列表添加。

### 4. 分页处理

CCXT 的 `fetch_ohlcv` 每次最多返回 1000 条数据。引擎自动处理分页，循环获取直到覆盖指定时间范围。

## 与现有回测引擎集成

现有的 `BacktestEngine` 已经增强以支持外部数据：

```python
from src.backtest.engine import BacktestEngine
from src.backtest.ccxt_backtest import CCXTBacktestEngine
from datetime import datetime, timedelta

# 1. 获取真实数据
ccxt_engine = CCXTBacktestEngine()
df = ccxt_engine.fetch_historical_data(
    exchange='binance',
    symbol='BTC/USDT',
    start_time=datetime(2024, 1, 1),
    end_time=datetime(2024, 12, 31),
    timeframe='1h'
)

# 2. 配置策略
strategy_config = {
    "name": "My MA Strategy",
    "symbol": "BTC/USDT",
    "type": "ma_cross",  # 或 "rsi", "macd", "bollinger"
    "params": {
        "fast_period": 10,
        "slow_period": 30
    },
    "position_size": 0.2
}

# 3. 运行回测（传入 klines_df 参数）
backtest = BacktestEngine(strategy_config, initial_balance=10000)
result = backtest.run(klines_df=df)

# 4. 查看结果
print(f"总收益: {result['total_pnl']} ({result['total_return_pct']}%)")
print(f"最大回撤: {result['max_drawdown']}%")
print(f"交易次数: {result['total_trades']}")
print(f"胜率: {result['win_rate']}%")
```

## 运行示例

执行示例脚本：

```bash
python examples/ccxt_backtest_demo.py
```

这将：
1. 从币安获取最近30天 BTC/USDT 的1小时K线
2. 运行 MA 交叉策略回测
3. 输出结果并保存到 `data/backtest_result.json`

## 命令行工具

`ccxt_backtest.py` 也可以直接运行：

```bash
python src/backtest/ccxt_backtest.py \
  --exchange binance \
  --symbol BTC/USDT \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --timeframe 1h \
  --output data/my_data.csv
```

## 注意事项

### API 限制

- 交易所通常有 API 请求频率限制
- 对于大时间范围，可能需要多次请求分页
- 启用 `enableRateLimit=True` 自动限制请求速率

### 数据格式

返回的 DataFrame 包含以下列：
- `timestamp` (datetime64)
- `open` (float)
- `high` (float)
- `low` (float)
- `close` (float)
- `volume` (float)

### 错误处理

- 网络异常时会记录错误并继续尝试
- 如遇问题，可设置 `use_cache=False` 强制重新下载
- 缓存文件损坏时会自动重新下载

## 替换模拟数据

原来的 `BacktestEngine.generate_mock_data()` 现在不再是默认选项。要使用模拟数据，显式生成：

```python
mock_data = engine.generate_mock_data(periods=1000)
result = engine.run(data=mock_data)
```

或使用 `klines_df=None` 且 `days` 参数。

## 后续优化建议

1. **异步下载**: 使用 `ccxt.async_support` 加快多交易所数据获取
2. **增量更新**: 实现只下载缺少的数据，避免全量重新下载
3. **多线程**: 同时下载多个交易对的数据
4. **数据验证**: 添加 OHLC 合理性检查（high >= max(open, close) 等）
5. **数据库缓存**: 使用 SQLite 替代 pickle 以支持查询和并发

---

## 变更日志

- 2025-03-05: 创建 CCXTBacktestEngine，集成到 BacktestEngine
