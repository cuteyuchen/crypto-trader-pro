# 回测引擎真实数据支持 - 使用说明

## 快速开始

### 1. 获取真实历史数据

```python
from src.backtest.ccxt_backtest import CCXTBacktestEngine
from datetime import datetime, timedelta

# 创建数据引擎
engine = CCXTBacktestEngine()

# 下载数据（自动缓存）
df = engine.fetch_historical_data(
    exchange='binance',       # 支持: binance, okx
    symbol='BTC/USDT',
    start_time=datetime(2024, 1, 1),
    end_time=datetime(2024, 12, 31),
    timeframe='1h'            # 支持: 1m, 5m, 1h, 1d 等
)
```

### 2. 运行回测

```python
from src.backtest.engine import BacktestEngine

config = {
    "name": "My Strategy",
    "symbol": "BTC/USDT",
    "type": "ma_cross",      # 或 "rsi", "macd", "bollinger"
    "params": {
        "fast_period": 10,
        "slow_period": 30
    },
    "position_size": 0.2
}

backtest = BacktestEngine(config, initial_balance=10000)
result = backtest.run(klines_df=df)  # 传入真实数据

print(f"总收益: {result['total_pnl']} ({result['total_return_pct']}%)")
print(f"最大回撤: {result['max_drawdown']}%")
print(f"胜率: {result['win_rate']}%")
```

### 3. 命令行工具

```bash
python src/backtest/ccxt_backtest.py \
  --exchange binance \
  --symbol BTC/USDT \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --timeframe 1h \
  --output data/my_data.csv
```

### 4. 运行完整示例

```bash
python examples/ccxt_backtest_demo.py
```

## 关键特性

- ✅ **自动缓存**：已下载的数据会保存在 `data/historical/`，避免重复请求
- ✅ **分页处理**：自动处理交易所的 1000 条限制
- ✅ **多交易所**：支持 binance, okx（可扩展）
- ✅ **数据质量**：自动排序、去重、时间过滤
- ✅ **与现有系统集成**：无需修改策略代码

## 文件说明

| 文件 | 说明 |
|------|------|
| `src/backtest/ccxt_backtest.py` | CCXT 数据获取引擎 |
| `src/backtest/INTEGRATION.md` | 详细集成文档 |
| `examples/ccxt_backtest_demo.py` | 完整使用示例 |
| `tests/unit/test_ccxt_backtest.py` | 单元测试 |

## 注意事项

1. 确保已安装 `ccxt`：`pip install ccxt pandas`
2. 首次运行会从交易所下载数据，可能需要一些时间
3. 交易所 API 有频率限制，大时间范围会自动分页
4. 数据按时间排序并去重，保证回测准确性

## 示例输出

```
============================================================
端到端验证测试
============================================================

1. 测试 CCXTBacktestEngine（使用模拟）...
   ✅ 数据获取成功，DataFrame 格式正确

2. 测试 BacktestEngine 集成...
   ✅ 回测完成，交易次数: 0, 盈亏: $0.00

...
所有测试通过！集成成功。
```

---

详细技术文档请见 `src/backtest/INTEGRATION.md`
