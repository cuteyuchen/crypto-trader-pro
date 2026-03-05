#!/usr/bin/env python
"""
快速检查 BacktestEngine 是否正确处理真实数据
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from src.backtest.engine import BacktestEngine

# 生成测试数据
np.random.seed(42)
n = 100
dates = pd.date_range('2025-03-01', periods=n, freq='1min')
close = 50000 + np.random.randn(n).cumsum() * 10

df = pd.DataFrame({
    'timestamp': dates,
    'open': close - np.random.rand(n) * 50,
    'high': close + np.random.rand(n) * 50,
    'low': close - np.random.rand(n) * 50,
    'close': close,
    'volume': np.random.randint(100, 1000, n)
})
df.set_index('timestamp', inplace=True)

# MA 交叉策略
config = {
    "name": "Test_MA_Cross",
    "symbol": "BTC/USDT",
    "timeframe": "1m",
    "type": "ma_cross",
    "params": {
        "fast_period": 5,
        "slow_period": 20
    },
    "position_size": 0.2
}

engine = BacktestEngine(config)
result = engine.run(klines_df=df)

print("测试成功！")
print(f"策略: {result['strategy']}")
print(f"初始/最终资金: {result['initial_balance']} -> {result['final_balance']}")
print(f"总交易次数: {result['total_trades']}")
print(f"最大回撤: {result['max_drawdown']}%")
