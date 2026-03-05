"""
移动平均线交叉策略（金叉/死叉）
"""
import logging
import pandas as pd
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class MovingAverageStrategy:
    """MA 交叉策略"""

    def __init__(self, config: Dict[str, Any]):
        self.name = config.get("name", "MA_Cross")
        self.symbol = config["symbol"]
        self.timeframe = config.get("timeframe", "1m")
        self.fast_period = config["params"]["fast_period"]
        self.slow_period = config["params"]["slow_period"]
        self.position_size = config.get("position_size", 0.2)  # 仓位比例
        self.stop_loss_pct = config.get("stop_loss_pct", 0.05)
        self.take_profit_pct = config.get("take_profit_pct", 0.10)

        self.state = "out"  # out | long | short
        self.entry_price = 0.0

    def on_kline(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        处理新的 K 线（逐根返回信号）

        Returns:
            None 表示无信号
            {"action": "buy"|"sell", "reason": "..."} 表示交易信号
        """
        if len(df) < self.slow_period:
            return None

        # 计算 MA
        fast_ma = df['close'].rolling(self.fast_period).mean()
        slow_ma = df['close'].rolling(self.slow_period).mean()

        i = -1  # 最新一根
        if len(fast_ma) < 2:
            return None

        prev_fast = fast_ma.iloc[-2]
        curr_fast = fast_ma.iloc[-1]
        prev_slow = slow_ma.iloc[-2]
        curr_slow = slow_ma.iloc[-1]

        if self.state == "out":
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                self.state = "long"
                self.entry_price = df['close'].iloc[-1]
                return {"action": "buy", "reason": "MA金叉"}
        elif self.state == "long":
            current_price = df['close'].iloc[-1]
            change = (current_price - self.entry_price) / self.entry_price
            if change <= -self.stop_loss_pct:
                self.state = "out"
                return {"action": "sell", "reason": "触发止损"}
            if change >= self.take_profit_pct:
                self.state = "out"
                return {"action": "sell", "reason": "达到止盈"}

            if prev_fast >= prev_slow and curr_fast < curr_slow:
                self.state = "out"
                return {"action": "sell", "reason": "MA死叉"}

        return None

    def reset(self):
        """重置策略状态"""
        self.state = "out"
        self.entry_price = 0.0
