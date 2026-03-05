"""
RSI (Relative Strength Index) 策略
当 RSI 低于 oversold_threshold 时买入，高于 overbought_threshold 时卖出
"""
import logging
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class RSIStrategy:
    """RSI 策略"""

    def __init__(self, config: Dict[str, Any]):
        """
        config 示例:
        {
            "name": "RSI_14_70_30",
            "symbol": "BTC/USDT",
            "timeframe": "1m",
            "rsi_period": 14,
            "oversold": 30,
            "overbought": 70,
            "position_size": 0.2
        }
        """
        self.config = config
        self.symbol = config["symbol"]
        self.timeframe = config.get("timeframe", "1m")
        self.rsi_period = config.get("rsi_period", 14)
        self.oversold = config.get("oversold", 30)
        self.overbought = config.get("overbought", 70)
        self.position_size = config.get("position_size", 0.2)
        
        self.kline_buffer = []  # 存储 K线 close 价格
        self.current_rsi = None
        self.has_position = False  # 简化：是否持有仓位（实际应从持仓查询）
        logger.info(f"RSI策略初始化: {config['name']}, 周期={self.rsi_period}, 超卖={self.oversold}, 超买={self.overbought}")

    def on_kline(self, kline: Dict[str, Any]):
        """接收新 K线"""
        close = kline["close"]
        self.kline_buffer.append(close)
        # 保持 buffer 大小不超过 rsi_period * 2（避免无限增长）
        if len(self.kline_buffer) > self.rsi_period * 4:
            self.kline_buffer = self.kline_buffer[-self.rsi_period*4:]

        if len(self.kline_buffer) >= self.rsi_period + 1:
            self._calculate_rsi()

    def _calculate_rsi(self):
        """计算 RSI"""
        deltas = [self.kline_buffer[i] - self.kline_buffer[i-1] for i in range(1, len(self.kline_buffer))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        
        # 使用最后 rsi_period 个数据
        gains = gains[-self.rsi_period:]
        losses = losses[-self.rsi_period:]
        
        avg_gain = sum(gains) / self.rsi_period
        avg_loss = sum(losses) / self.rsi_period
        
        if avg_loss == 0:
            rs = float('inf')
        else:
            rs = avg_gain / avg_loss
        
        self.current_rsi = 100 - (100 / (1 + rs))
        logger.debug(f"RSI计算: 最近收盘={self.kline_buffer[-1]:.2f}, RSI={self.current_rsi:.2f}")

    def check_signal(self, price: float) -> Dict[str, Any]:
        """
        检查是否产生交易信号
        返回: {"action": "buy"|"sell"|"hold", "reason": "..."} 或 None（无信号）
        """
        if self.current_rsi is None:
            return {"action": "hold", "reason": "RSI 尚未计算"}

        rsi = self.current_rsi
        # 注意：实际应查询当前持仓，这里使用简化状态
        # 这里无法直接访问持仓，所以通过策略信号可能重复。外部 executor 会检查持仓。

        if rsi <= self.oversold:
            return {"action": "buy", "reason": f"RSI={rsi:.1f} <= {self.oversold} (超卖)"}
        elif rsi >= self.overbought:
            return {"action": "sell", "reason": f"RSI={rsi:.1f} >= {self.overbought} (超买)"}
        else:
            return {"action": "hold", "reason": f"RSI={rsi:.1f}，持有"}

    def get_status(self) -> Dict[str, Any]:
        """获取策略状态"""
        return {
            "name": self.config.get("name", "RSIStrategy"),
            "state": f"RSI={self.current_rsi:.1f}" if self.current_rsi else "计算中",
            "kline_count": len(self.kline_buffer),
            "has_position": self.has_position
        }
