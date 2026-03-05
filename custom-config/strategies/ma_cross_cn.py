from freqtrade.strategy import IStrategy
from talib.abstract import SMA
import pandas as pd
from typing import Dict, Any

class MA交叉策略(IStrategy):
    """
    MA 移动平均线交叉策略（中文版）
    当快线上穿慢线时买入，下穿时卖出
    """
    timeframe = "5m"
    minimal_roi = {"0": 0.10}
    stoploss = -0.05
    trailing_stop = False

    # 策略参数
    fast_period = 10
    slow_period = 30

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """计算技术指标"""
        dataframe['fast_ma'] = SMA(dataframe['close'], timeperiod=self.fast_period)
        dataframe['slow_ma'] = SMA(dataframe['close'], timeperiod=self.slow_period)
        return dataframe

    def populate_buy_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """生成买入信号"""
        dataframe.loc[
            (dataframe['fast_ma'] > dataframe['slow_ma']) &
            (dataframe['fast_ma'].shift(1) <= dataframe['slow_ma'].shift(1)),
            'buy'] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """生成卖出信号"""
        dataframe.loc[
            (dataframe['fast_ma'] < dataframe['slow_ma']) &
            (dataframe['fast_ma'].shift(1) >= dataframe['slow_ma'].shift(1)),
            'sell'] = 1
        return dataframe

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, **kwargs) -> bool:
        self.log(f"✅ 买入确认: {pair} 数量={amount} 价格={rate}")
        return True

    def confirm_trade_exit(self, pair: str, order_type: str, amount: float, rate: float,
                           reason: str, **kwargs) -> bool:
        self.log(f"🔵 卖出确认: {pair} 数量={amount} 价格={rate} 原因={reason}")
        return True
