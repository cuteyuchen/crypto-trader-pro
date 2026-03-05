"""
布林带策略 (Bollinger Bands)
当价格触及下轨时买入，触及上轨时卖出
"""
import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class BollingerBandsStrategy:
    """布林带策略"""

    def __init__(self, config: Dict[str, Any]):
        """
        config 示例:
        {
            "name": "BB_20_2",
            "symbol": "BTC/USDT",
            "timeframe": "1m",
            "bb_period": 20,
            "bb_std": 2.0,
            "position_size": 0.2,
            "stop_loss_pct": 0.05,
            "take_profit_pct": 0.10
        }
        """
        self.config = config
        self.symbol = config["symbol"]
        self.timeframe = config.get("timeframe", "1m")
        self.bb_period = config.get("bb_period", 20)
        self.bb_std = config.get("bb_std", 2.0)
        self.position_size = config.get("position_size", 0.2)
        self.stop_loss_pct = config.get("stop_loss_pct", 0.05)
        self.take_profit_pct = config.get("take_profit_pct", 0.10)

        self.state = "out"  # out | long
        self.entry_price = 0.0
        logger.info(f"布林带策略初始化: 周期={self.bb_period}, 标准差={self.bb_std}")

    def on_kline(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        处理 K 线数据
        """
        if len(df) < self.bb_period:
            return None

        closes = df['close'].values

        # 计算布林带
        sma = pd.Series(closes).rolling(self.bb_period).mean().iloc[-1]
        std = pd.Series(closes).rolling(self.bb_period).std().iloc[-1]
        upper = sma + self.bb_std * std
        lower = sma - self.bb_std * std

        current_price = closes[-1]

        # 状态机
        if self.state == "out":
            # 价格触及下轨（或低于下轨）买入
            if current_price <= lower:
                self.state = "long"
                self.entry_price = current_price
                return {"action": "buy", "reason": f"价格触及布林带下轨 (价格={current_price:.2f}, 下轨={lower:.2f})"}
        elif self.state == "long":
            # 检查止损止盈
            change = (current_price - self.entry_price) / self.entry_price
            if change <= -self.stop_loss_pct:
                self.state = "out"
                return {"action": "sell", "reason": "触发止损"}
            if change >= self.take_profit_pct:
                self.state = "out"
                return {"action": "sell", "reason": "达到止盈"}

            # 价格触及上轨卖出
            if current_price >= upper:
                self.state = "out"
                return {"action": "sell", "reason": f"价格触及布林带上轨 (价格={current_price:.2f}, 上轨={upper:.2f})"}

        return None

    def reset(self):
        """重置策略状态"""
        self.state = "out"
        self.entry_price = 0.0

    def get_status(self) -> Dict[str, Any]:
        """获取策略状态"""
        return {
            "name": self.config.get("name", "BollingerBands"),
            "state": self.state,
            "entry_price": self.entry_price,
            "kline_count": 0  # 可从外部传入
        }
