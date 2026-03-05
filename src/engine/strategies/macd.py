"""
MACD 策略 (Moving Average Convergence Divergence)
MACD 线上穿信号线时买入，下穿时卖出
"""
import logging
import pandas as pd
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class MACDStrategy:
    """MACD 策略"""

    def __init__(self, config: Dict[str, Any]):
        """
        config 示例:
        {
            "name": "MACD_12_26_9",
            "symbol": "BTC/USDT",
            "timeframe": "1m",
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "position_size": 0.2,
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.10
        }
        """
        self.config = config
        self.symbol = config["symbol"]
        self.timeframe = config.get("timeframe", "1m")
        self.fast_period = config.get("fast_period", 12)
        self.slow_period = config.get("slow_period", 26)
        self.signal_period = config.get("signal_period", 9)
        self.position_size = config.get("position_size", 0.2)
        self.stop_loss_pct = config.get("stop_loss_pct", 0.05)
        self.take_profit_pct = config.get("take_profit_pct", 0.10)

        self.state = "out"  # out | long
        self.entry_price = 0.0
        logger.info(f"MACD策略初始化: 快={self.fast_period}, 慢={self.slow_period}, 信号={self.signal_period}")

    def on_kline(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        处理 K 线数据
        """
        # 需要足够数据来计算 MACD
        needed = self.slow_period + self.signal_period
        if len(df) < needed:
            return None

        closes = df['close']

        # 计算 EMA
        fast_ema = closes.ewm(span=self.fast_period, adjust=False).mean()
        slow_ema = closes.ewm(span=self.slow_period, adjust=False).mean()

        # MACD 线
        macd = fast_ema - slow_ema
        # 信号线
        signal = macd.ewm(span=self.signal_period, adjust=False).mean()

        # 判断交叉
        prev_macd = macd.iloc[-2]
        curr_macd = macd.iloc[-1]
        prev_signal = signal.iloc[-2]
        curr_signal = signal.iloc[-1]

        current_price = closes.iloc[-1]

        if self.state == "out":
            # 金叉：MACD 从下往上穿过信号线
            if prev_macd <= prev_signal and curr_macd > curr_signal:
                self.state = "long"
                self.entry_price = current_price
                return {"action": "buy", "reason": "MACD 金叉"}
        elif self.state == "long":
            # 止损止盈
            change = (current_price - self.entry_price) / self.entry_price
            if change <= -self.stop_loss_pct:
                self.state = "out"
                return {"action": "sell", "reason": "触发止损"}
            if change >= self.take_profit_pct:
                self.state = "out"
                return {"action": "sell", "reason": "达到止盈"}

            # 死叉：MACD 从上往下穿过信号线
            if prev_macd >= prev_signal and curr_macd < curr_signal:
                self.state = "out"
                return {"action": "sell", "reason": "MACD 死叉"}

        return None

    def reset(self):
        """重置策略状态"""
        self.state = "out"
        self.entry_price = 0.0

    def get_status(self) -> Dict[str, Any]:
        """获取策略状态"""
        return {
            "name": self.config.get("name", "MACD"),
            "state": self.state,
            "entry_price": self.entry_price,
            "kline_count": 0
        }
