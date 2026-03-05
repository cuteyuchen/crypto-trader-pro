#!/usr/bin/env python
"""
端到端验证：CCXT 回测引擎集成测试
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime, timedelta
import pandas as pd
import numpy as np

print("="*60)
print("端到端验证测试")
print("="*60)

# 1. 测试 CCXTBacktestEngine
print("\n1. 测试 CCXTBacktestEngine（使用模拟）...")
from unittest.mock import patch, MagicMock
sys.modules['ccxt'] = MagicMock()

from src.backtest.ccxt_backtest import CCXTBacktestEngine

engine = CCXTBacktestEngine(cache_dir="/tmp/ccxt_test_e2e")
mock_ohlcv = [
    [1704067200000, 50000.0, 50100.0, 49900.0, 50050.0, 100.0],
    [1704070800000, 50050.0, 50200.0, 50000.0, 50150.0, 150.0],
    [1704074400000, 50150.0, 50300.0, 50100.0, 50200.0, 120.0],
]

with patch('ccxt.binance') as MockExchange:
    mock_exchange = MagicMock()
    mock_exchange.fetch_ohlcv.return_value = mock_ohlcv
    mock_exchange.load_markets = MagicMock()
    MockExchange.return_value = mock_exchange

    df = engine.fetch_historical_data(
        exchange='binance',
        symbol='BTC/USDT',
        start_time=datetime(2024, 1, 1),
        end_time=datetime(2024, 1, 2),
        timeframe='1h'
    )

    assert len(df) == 3, f"Expected 3 rows, got {len(df)}"
    assert list(df.columns) == ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    print("   ✅ 数据获取成功，DataFrame 格式正确")

# 2. 测试 BacktestEngine 与真实数据
print("\n2. 测试 BacktestEngine 集成...")
from src.backtest.engine import BacktestEngine

config = {
    "name": "Test_MA",
    "symbol": "BTC/USDT",
    "type": "ma_cross",
    "params": {"fast_period": 2, "slow_period": 3}
}

backtest = BacktestEngine(config, initial_balance=10000)
result = backtest.run(klines_df=df)

assert 'final_balance' in result
assert 'total_pnl' in result
assert 'max_drawdown' in result
assert 'total_trades' in result
assert 'win_rate' in result
print(f"   ✅ 回测完成，交易次数: {result['total_trades']}, 盈亏: ${result['total_pnl']:.2f}")

# 3. 测试 RSI 策略
print("\n3. 测试 RSI 策略...")
rsi_config = {
    "name": "Test_RSI",
    "symbol": "BTC/USDT",
    "rsi_period": 14,
    "oversold": 30,
    "overbought": 70,
    "position_size": 0.2
}
rsi_backtest = BacktestEngine(rsi_config, initial_balance=10000)
rsi_result = rsi_backtest.run(klines_df=df)
print(f"   ✅ RSI 策略成功，交易次数: {rsi_result['total_trades']}")

# 4. 测试 MACD 策略
print("\n4. 测试 MACD 策略...")
macd_config = {
    "name": "Test_MACD",
    "symbol": "BTC/USDT",
    "fast_period": 12,
    "slow_period": 26,
    "signal_period": 9,
    "position_size": 0.2
}
macd_backtest = BacktestEngine(macd_config, initial_balance=10000)
macd_result = macd_backtest.run(klines_df=df)
print(f"   ✅ MACD 策略成功，交易次数: {macd_result['total_trades']}")

# 5. 缓存测试
print("\n5. 测试缓存机制...")
cache_file = engine._get_cache_filename('binance', 'BTC/USDT', 1, 2)
cache_path = Path(cache_file)
assert cache_path.name.endswith('.pkl')
print(f"   ✅ 缓存文件名: {cache_path.name}")

# 清理
import shutil
engine.close()
try:
    shutil.rmtree("/tmp/ccxt_test_e2e")
except:
    pass

print("\n" + "="*60)
print("所有测试通过！集成成功。")
print("="*60)
