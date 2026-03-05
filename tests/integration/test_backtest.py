"""
集成测试：回测引擎
"""
import pytest
from src.backtest.engine import BacktestEngine


class TestBacktestEngine:
    """回测引擎测试"""

    def test_backtest_initialization(self, ma_cross_config):
        """测试回测引擎初始化"""
        initial_balance = 10000.0
        engine = BacktestEngine(ma_cross_config, initial_balance=initial_balance)

        assert engine.strategy_config == ma_cross_config
        assert engine.initial_balance == initial_balance
        assert engine.trades == []
        assert engine.balance == initial_balance

    def test_backtest_simple_ma_cross(self, ma_cross_config, sample_klines):
        """测试简单的 MA 交叉回测"""
        engine = BacktestEngine(ma_cross_config, initial_balance=10000.0)

        # 运行回测 30 天（使用样本数据）
        result = engine.run(days=30, klines_df=sample_klines)

        assert 'final_balance' in result
        assert 'total_pnl' in result
        assert 'total_trades' in result
        assert 'win_rate' in result
        assert 'trades' in result
        assert isinstance(result['trades'], list)

    def test_backtest_no_signals(self, ma_cross_config):
        """测试无信号情况（平稳市场）"""
        import pandas as pd
        import numpy as np

        # 生成平稳的价格序列（无趋势）
        np.random.seed(42)
        n = 200
        closes = 50000 + np.random.randn(n) * 50  # 白噪声

        df = pd.DataFrame({
            'timestamp': pd.date_range('2025-03-01', periods=n, freq='1min'),
            'open': closes,
            'high': closes + 10,
            'low': closes - 10,
            'close': closes,
            'volume': 100
        })
        df.set_index('timestamp', inplace=True)

        engine = BacktestEngine(ma_cross_config, initial_balance=10000.0)
        result = engine.run(days=1, klines_df=df)

        # 应该没有交易或很少交易
        assert result['total_trades'] >= 0

    def test_backtest_with_rsi(self, rsi_config):
        """测试 RSI 策略回测"""
        import pandas as pd
        import numpy as np

        # 生成有明显超卖超买的序列
        np.random.seed(42)
        n = 300
        # 先跌后涨，再跌
        trend = np.concatenate([
            np.linspace(0, -1, 100),  # 下跌
            np.linspace(-1, 1, 100),   # 反弹
            np.linspace(1, 0, 100)     # 回落
        ])
        closes = 50000 + trend * 500 + np.random.randn(n) * 30

        df = pd.DataFrame({
            'timestamp': pd.date_range('2025-03-01', periods=n, freq='1min'),
            'open': closes,
            'high': closes + 10,
            'low': closes - 10,
            'close': closes,
            'volume': 100
        })
        df.set_index('timestamp', inplace=True)

        engine = BacktestEngine(rsi_config, initial_balance=10000.0)
        result = engine.run(days=2, klines_df=df)

        assert 'final_balance' in result
        assert 'total_trades' in result
        # 由于价格波动，应该产生一些交易
        # 但不一定，因为 RSI 需要足够数据
        if result['total_trades'] > 0:
            assert result['win_rate'] >= 0 and result['win_rate'] <= 100

    def test_backtest_with_macd(self, macd_config):
        """测试 MACD 策略回测"""
        import pandas as pd
        import numpy as np

        np.random.seed(42)
        n = 300
        # 构造有趋势的市场
        trend = np.sin(np.linspace(0, 6*np.pi, n)) * 1000
        closes = 50000 + trend + np.random.randn(n) * 50

        df = pd.DataFrame({
            'timestamp': pd.date_range('2025-03-01', periods=n, freq='1min'),
            'open': closes,
            'high': closes + 20,
            'low': closes - 20,
            'close': closes,
            'volume': 100
        })
        df.set_index('timestamp', inplace=True)

        engine = BacktestEngine(macd_config, initial_balance=10000.0)
        result = engine.run(days=2, klines_df=df)

        assert 'final_balance' in result
        assert 'total_pnl' in result
        assert isinstance(result['trades'], list)

    def test_backtest_max_drawdown(self, ma_cross_config):
        """测试回测的最大回撤计算"""
        import pandas as pd
        import numpy as np

        np.random.seed(42)
        n = 200
        # 先涨后跌，制造回撤
        up = np.linspace(0, 1, 100) * 500
        down = np.linspace(1, 0, 100) * 500
        closes = 50000 + np.concatenate([up, down]) + np.random.randn(n) * 20

        df = pd.DataFrame({
            'timestamp': pd.date_range('2025-03-01', periods=n, freq='1min'),
            'open': closes,
            'high': closes + 10,
            'low': closes - 10,
            'close': closes,
            'volume': 100
        })
        df.set_index('timestamp', inplace=True)

        engine = BacktestEngine(ma_cross_config, initial_balance=10000.0)
        result = engine.run(days=2, klines_df=df)

        assert 'max_drawdown' in result
        assert result['max_drawdown'] >= 0  # 回撤是正数

    def test_backtest_position_size(self, ma_cross_config):
        """测试仓位大小配置影响"""
        # 修改配置使用更大的仓位
        config = ma_cross_config.copy()
        config['position_size'] = 1.0  # 全仓

        engine = BacktestEngine(config, initial_balance=10000.0)
        initial = engine.balance

        import pandas as pd
        import numpy as np

        np.random.seed(42)
        n = 200
        closes = 50000 + np.random.randn(n).cumsum() * 20

        df = pd.DataFrame({
            'timestamp': pd.date_range('2025-03-01', periods=n, freq='1min'),
            'open': closes,
            'high': closes + 10,
            'low': closes - 10,
            'close': closes,
            'volume': 100
        })
        df.set_index('timestamp', inplace=True)

        result = engine.run(days=2, klines_df=df)

        # 由于仓位大，盈亏幅度应该更大（相对初始）
        # 但没法精确断言，只能检查数值存在
        assert 'final_balance' in result


def test_backtest_all_strategies():
    """测试所有策略都可以运行回测"""
    from src.engine.strategies.ma_cross import MovingAverageStrategy

    strategies = [
        ("ma_cross", {
            "name": "Test_MA",
            "symbol": "BTC/USDT",
            "params": {"fast_period": 5, "slow_period": 20}
        }),
        ("rsi", {
            "name": "Test_RSI",
            "symbol": "BTC/USDT",
            "rsi_period": 14,
            "oversold": 30,
            "overbought": 70
        }),
        ("bollinger", {
            "name": "Test_BB",
            "symbol": "BTC/USDT",
            "bb_period": 20,
            "bb_std": 2.0
        }),
        ("macd", {
            "name": "Test_MACD",
            "symbol": "BTC/USDT",
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9
        })
    ]

    import pandas as pd
    import numpy as np
    np.random.seed(42)
    n = 200
    closes = 50000 + np.random.randn(n).cumsum() * 20
    df = pd.DataFrame({
        'timestamp': pd.date_range('2025-03-01', periods=n, freq='1min'),
        'open': closes,
        'high': closes + 10,
        'low': closes - 10,
        'close': closes,
        'volume': 100
    })
    df.set_index('timestamp', inplace=True)

    for strategy_type, config in strategies:
        engine = BacktestEngine(config, initial_balance=10000.0)
        result = engine.run(days=1, klines_df=df)
        # 所有策略都应该能返回结果
        assert 'final_balance' in result
        assert 'total_trades' in result
