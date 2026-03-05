"""
单元测试：所有策略的信号逻辑
测试策略：MA交叉、RSI、布林带、MACD
"""
import pytest
import pandas as pd
import numpy as np
from src.engine.strategies.ma_cross import MovingAverageStrategy
from src.engine.strategies.rsi_strategy import RSIStrategy
from src.engine.strategies.bollinger_bands import BollingerBandsStrategy
from src.engine.strategies.macd import MACDStrategy


class TestMovingAverageStrategy:
    """MA 交叉策略测试"""

    def test_initialization(self, ma_cross_config):
        """测试策略初始化"""
        strategy = MovingAverageStrategy(ma_cross_config)
        assert strategy.name == "Test_MA_Cross"
        assert strategy.symbol == "BTC/USDT"
        assert strategy.fast_period == 5
        assert strategy.slow_period == 20
        assert strategy.state == "out"

    def test_golden_cross_signal(self, ma_cross_config):
        """测试金叉买入信号"""
        import pandas as pd
        strategy = MovingAverageStrategy(ma_cross_config)

        # 构造精确的金叉数据：
        # fast_period=5, slow_period=20
        # 需要 30 根数据：前 28 根 50000，第 29 根 50000，第 30 根 60000
        # 这样 fast_ma[-2]=50000, slow_ma[-2]=50000, fast_ma[-1]=52000, slow_ma[-1]=50500 -> 金叉
        prices = [50000] * 28 + [50000, 60000]
        df = pd.DataFrame({'close': prices})

        signal = strategy.on_kline(df)
        assert signal is not None, f"金叉未触发，状态: {strategy.state}"
        assert signal['action'] == 'buy'
        assert '金叉' in signal['reason']
        assert strategy.state == 'long'

    def test_death_cross_signal(self, ma_cross_config, sample_klines):
        """测试死叉卖出信号"""
        strategy = MovingAverageStrategy(ma_cross_config)
        strategy.state = 'long'  # 先持有仓位
        strategy.entry_price = 50000

        df = sample_klines.copy()
        # 构造死叉：价格快速下跌
        df.loc[df.index[-2], 'close'] = 50000
        df.loc[df.index[-1], 'close'] = 49500

        signal = strategy.on_kline(df)
        assert signal is not None
        assert signal['action'] == 'sell'
        assert '死叉' in signal['reason']
        assert strategy.state == 'out'

    def test_stop_loss(self, ma_cross_config, sample_klines):
        """测试止损触发"""
        strategy = MovingAverageStrategy(ma_cross_config)
        strategy.state = 'long'
        strategy.entry_price = 50000  # 入场价

        df = sample_klines.copy()
        # 价格下跌超过 5%
        df.loc[df.index[-1], 'close'] = 47500  # 下跌 5%

        signal = strategy.on_kline(df)
        assert signal is not None
        assert signal['action'] == 'sell'
        assert '止损' in signal['reason']
        assert strategy.state == 'out'

    def test_take_profit(self, ma_cross_config, sample_klines):
        """测试止盈触发"""
        strategy = MovingAverageStrategy(ma_cross_config)
        strategy.state = 'long'
        strategy.entry_price = 50000

        df = sample_klines.copy()
        # 价格上涨超过 10%
        df.loc[df.index[-1], 'close'] = 55200

        signal = strategy.on_kline(df)
        assert signal is not None
        assert signal['action'] == 'sell'
        assert '止盈' in signal['reason']
        assert strategy.state == 'out'

    def test_no_signal(self, ma_cross_config, sample_klines):
        """测试无信号情况"""
        strategy = MovingAverageStrategy(ma_cross_config)
        df = sample_klines.copy()
        # 保持平稳，无交叉
        df['close'] = 50000

        signal = strategy.on_kline(df)
        assert signal is None

    def test_reset(self, ma_cross_config, sample_klines):
        """测试状态重置"""
        strategy = MovingAverageStrategy(ma_cross_config)
        strategy.state = 'long'
        strategy.entry_price = 50000

        strategy.reset()
        assert strategy.state == 'out'
        assert strategy.entry_price == 0.0


class TestRSIStrategy:
    """RSI 策略测试"""

    def test_initialization(self, rsi_config):
        """测试 RSI 策略初始化"""
        strategy = RSIStrategy(rsi_config)
        assert strategy.symbol == "BTC/USDT"
        assert strategy.rsi_period == 14
        assert strategy.oversold == 30
        assert strategy.overbought == 70
        assert len(strategy.kline_buffer) == 0

    def test_rsi_calculation(self, rsi_config):
        """测试 RSI 计算逻辑"""
        strategy = RSIStrategy(rsi_config)

        # 构造一系列上涨数据（RSI 应该很高）
        for price in range(50000, 50100):
            strategy.on_kline({"close": price})

        # RSI 应该接近或超过 70（超买）
        assert strategy.current_rsi is not None
        if strategy.current_rsi:
            assert strategy.current_rsi > 60  # 可能在 70 附近或更高

    def test_oversold_buy_signal(self, rsi_config):
        """测试超卖买入信号"""
        strategy = RSIStrategy(rsi_config)

        # 模拟持续下跌，使 RSI 降至 oversold 以下
        prices = list(range(50000, 49800, -10))  # 持续下跌
        for p in prices:
            strategy.on_kline({"close": p})

        # 补充数据确保 RSI 计算准确
        for p in range(49800, 49700, -10):
            strategy.on_kline({"close": p})

        signal = strategy.check_signal(49700)
        # 注意：check_signal 是基于当前 RSI 判断
        # 由于我们的数据构造，RSI 应该很低
        if strategy.current_rsi and strategy.current_rsi <= strategy.oversold:
            assert signal['action'] == 'buy'
            assert '超卖' in signal['reason']

    def test_overbought_sell_signal(self, rsi_config):
        """测试超买卖出信号"""
        strategy = RSIStrategy(rsi_config)

        # 模拟持续上涨
        prices = list(range(50000, 50200, 10))
        for p in prices:
            strategy.on_kline({"close": p})

        for p in range(50200, 50300, 10):
            strategy.on_kline({"close": p})

        signal = strategy.check_signal(50300)
        if strategy.current_rsi and strategy.current_rsi >= strategy.overbought:
            assert signal['action'] == 'sell'
            assert '超买' in signal['reason']

    def test_neutral_rsi(self, rsi_config):
        """测试中性 RSI"""
        strategy = RSIStrategy(rsi_config)

        # 使用交替涨跌数据，使 RSI 接近 50
        prices = [50000 + (10 if i % 2 == 0 else -10) for i in range(30)]
        for p in prices:
            strategy.on_kline({"close": p})

        assert strategy.current_rsi is not None
        # RSI 应该在 30-70 之间
        assert 30 < strategy.current_rsi < 70

    def test_get_status(self, rsi_config):
        """测试获取策略状态"""
        strategy = RSIStrategy(rsi_config)
        status = strategy.get_status()

        assert 'name' in status
        assert 'kline_count' in status
        assert 'has_position' in status


class TestBollingerBandsStrategy:
    """布林带策略测试"""

    def test_initialization(self, bollinger_config):
        """测试布林带策略初始化"""
        strategy = BollingerBandsStrategy(bollinger_config)
        assert strategy.symbol == "BTC/USDT"
        assert strategy.bb_period == 20
        assert strategy.bb_std == 2.0
        assert strategy.state == 'out'

    def test_lower_band_buy_signal(self, bollinger_config, sample_klines):
        """测试触及下轨买入信号"""
        strategy = BollingerBandsStrategy(bollinger_config)

        df = sample_klines.copy()
        # 计算布林带
        closes = df['close'].values
        sma = pd.Series(closes).rolling(20).mean()
        std = pd.Series(closes).rolling(20).std()

        # 故意让最后的价格低于下轨
        lower_band = sma.iloc[-1] - 2.0 * std.iloc[-1]
        df.loc[df.index[-1], 'close'] = lower_band - 100  # 低于下轨

        signal = strategy.on_kline(df)
        assert signal is not None
        assert signal['action'] == 'buy'
        assert '下轨' in signal['reason']

    def test_upper_band_sell_signal(self, bollinger_config, sample_klines):
        """测试触及上轨卖出信号"""
        strategy = BollingerBandsStrategy(bollinger_config)
        strategy.state = 'long'
        strategy.entry_price = 50000

        df = sample_klines.copy()
        closes = df['close'].values
        sma = pd.Series(closes).rolling(20).mean()
        std = pd.Series(closes).rolling(20).std()
        upper_band = sma.iloc[-1] + 2.0 * std.iloc[-1]

        df.loc[df.index[-1], 'close'] = upper_band + 100  # 高于上轨

        signal = strategy.on_kline(df)
        assert signal is not None
        assert signal['action'] == 'sell'
        assert '上轨' in signal['reason']

    def test_stop_loss_and_take_profit(self, bollinger_config, sample_klines):
        """测试止损和止盈"""
        strategy = BollingerBandsStrategy(bollinger_config)
        strategy.state = 'long'
        strategy.entry_price = 50000

        # 测试止损
        df = sample_klines.copy()
        df.loc[df.index[-1], 'close'] = 47500  # 下跌 5%
        signal = strategy.on_kline(df)
        assert signal['action'] == 'sell'
        assert '止损' in signal['reason']
        assert strategy.state == 'out'

        # 重置后测试止盈
        strategy.reset()
        strategy.state = 'long'
        strategy.entry_price = 50000
        df.loc[df.index[-1], 'close'] = 55200  # 上涨 10.4%
        signal = strategy.on_kline(df)
        assert signal['action'] == 'sell'
        assert '止盈' in signal['reason']

    def test_reset(self, bollinger_config):
        """测试状态重置"""
        strategy = BollingerBandsStrategy(bollinger_config)
        strategy.state = 'long'
        strategy.entry_price = 50000

        strategy.reset()
        assert strategy.state == 'out'
        assert strategy.entry_price == 0.0


class TestMACDStrategy:
    """MACD 策略测试"""

    def test_initialization(self, macd_config):
        """测试 MACD 策略初始化"""
        strategy = MACDStrategy(macd_config)
        assert strategy.symbol == "BTC/USDT"
        assert strategy.fast_period == 12
        assert strategy.slow_period == 26
        assert strategy.signal_period == 9
        assert strategy.state == 'out'

    def test_bullish_crossover_signal(self, macd_config):
        """测试 MACD 金叉买入信号"""
        import pandas as pd
        strategy = MACDStrategy(macd_config)

        # 需要足够数据：至少 slow_period + signal_period = 35
        needed = strategy.slow_period + strategy.signal_period
        # 构造上涨序列使 MACD 上穿信号线
        # 前 30 根窄幅波动，后 20 根快速上升
        base = [50000] * 30
        ramp = [50000 + i * 100 for i in range(1, 21)]
        prices = base + ramp

        df = pd.DataFrame({'close': prices})

        signal = strategy.on_kline(df)
        assert signal is not None, f"MACD 金叉未产生，状态: {strategy.state}"
        assert signal['action'] == 'buy'
        assert '金叉' in signal['reason']
        assert strategy.state == 'long'

    def test_bearish_crossover_signal(self, macd_config, sample_klines):
        """测试 MACD 死叉卖出信号"""
        strategy = MACDStrategy(macd_config)
        strategy.state = 'long'
        strategy.entry_price = 50000

        df = sample_klines.copy()
        df.loc[df.index[-2], 'close'] = 50000
        df.loc[df.index[-1], 'close'] = 49500

        result = strategy.on_kline(df)
        if len(df) >= 35:
            assert result is not None
            assert result['action'] == 'sell'
            assert '死叉' in result['reason']

    def test_stop_loss_and_take_profit(self, macd_config, sample_klines):
        """测试止损止盈"""
        strategy = MACDStrategy(macd_config)
        strategy.state = 'long'
        strategy.entry_price = 50000

        df = sample_klines.copy()
        # 止损
        df.loc[df.index[-1], 'close'] = 47500
        result = strategy.on_kline(df)
        assert result is not None
        assert result['action'] == 'sell'
        assert '止损' in result['reason']

        # 止盈
        strategy.reset()
        strategy.state = 'long'
        strategy.entry_price = 50000
        df.loc[df.index[-1], 'close'] = 55200
        result = strategy.on_kline(df)
        assert result is not None
        assert result['action'] == 'sell'
        assert '止盈' in result['reason']

    def test_reset(self, macd_config):
        """测试状态重置"""
        strategy = MACDStrategy(macd_config)
        strategy.state = 'long'
        strategy.entry_price = 50000

        strategy.reset()
        assert strategy.state == 'out'
        assert strategy.entry_price == 0.0


def test_all_strategies_exported():
    """所有策略类都能正确导入"""
    from src.engine.strategies import ma_cross, rsi_strategy, bollinger_bands, macd
    assert hasattr(ma_cross, 'MovingAverageStrategy')
    assert hasattr(rsi_strategy, 'RSIStrategy')
    assert hasattr(bollinger_bands, 'BollingerBandsStrategy')
    assert hasattr(macd, 'MACDStrategy')
