"""
Pytest 配置和共享 fixtures
"""
import os
import sys
import pytest
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 设置测试环境变量
os.environ['DASHBOARD_USER'] = 'test_admin'
os.environ['DASHBOARD_PASS'] = 'test_pass'


@pytest.fixture(scope='session')
def temp_db(tmp_path_factory):
    """创建临时数据库目录"""
    db_dir = tmp_path_factory.mktemp('data')
    db_path = db_dir / 'test_simulation.db'
    yield str(db_path)
    # 清理在最后处理


@pytest.fixture(scope='function')
def clean_temp_db(temp_db):
    """每个测试使用干净的数据库"""
    # 确保数据库文件不存在
    if os.path.exists(temp_db):
        os.remove(temp_db)
    yield temp_db
    # 测试后清理
    if os.path.exists(temp_db):
        os.remove(temp_db)


@pytest.fixture(scope='session')
def sample_klines():
    """提供样本 K 线数据用于策略测试"""
    import pandas as pd
    import numpy as np

    # 生成 100 根 1 分钟 K 线
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
    return df


@pytest.fixture(scope='session')
def ma_cross_config():
    """MA 交叉策略配置"""
    return {
        "name": "Test_MA_Cross",
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


@pytest.fixture(scope='session')
def rsi_config():
    """RSI 策略配置"""
    return {
        "name": "Test_RSI",
        "symbol": "BTC/USDT",
        "timeframe": "1m",
        "rsi_period": 14,
        "oversold": 30,
        "overbought": 70,
        "position_size": 0.2
    }


@pytest.fixture(scope='session')
def bollinger_config():
    """布林带策略配置"""
    return {
        "name": "Test_Bollinger",
        "symbol": "BTC/USDT",
        "timeframe": "1m",
        "bb_period": 20,
        "bb_std": 2.0,
        "position_size": 0.2,
        "stop_loss_pct": 0.05,
        "take_profit_pct": 0.10
    }


@pytest.fixture(scope='session')
def macd_config():
    """MACD 策略配置"""
    return {
        "name": "Test_MACD",
        "symbol": "BTC/USDT",
        "timeframe": "1m",
        "fast_period": 12,
        "slow_period": 26,
        "signal_period": 9,
        "position_size": 0.2,
        "stop_loss_pct": 0.05,
        "take_profit_pct": 0.10
    }


@pytest.fixture(scope='session')
def risk_config():
    """风控配置"""
    return {
        "max_trades_per_day": 100,
        "max_position_size_pct": 0.5,
        "max_daily_loss_pct": 0.1,
        "emergency_stop_enabled": True
    }


@pytest.fixture(scope='session')
def sim_config():
    """本地模拟配置"""
    return {
        "initial_balance": 10000.0,
        "mode": "local"
    }
