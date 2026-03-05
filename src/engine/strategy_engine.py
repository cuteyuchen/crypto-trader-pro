import asyncio
import logging
from collections import deque
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# 策略类注册
STRATEGY_CLASSES = {
    "ma_cross": "MovingAverageStrategy",  # 实际类名
    "rsi": "RSIStrategy"
}


class KLineCache:
    """K线缓存 - 维护最近的K线数据"""

    def __init__(self, maxlen: int = 1000):
        self.maxlen = maxlen
        self.data: Dict[str, deque] = {}  # symbol -> deque of dicts
        # dict 包含: timestamp, open, high, low, close, volume

    def add_kline(self, symbol: str, kline: Dict[str, Any]):
        """添加一条 K 线数据"""
        if symbol not in self.data:
            self.data[symbol] = deque(maxlen=self.maxlen)
        self.data[symbol].append(kline)

    def get_klines(self, symbol: str, count: int = 100) -> List[Dict[str, Any]]:
        """获取指定数量的 K 线"""
        if symbol not in self.data:
            return []
        arr = list(self.data[symbol])
        return arr[-count:] if len(arr) >= count else arr

    def get_dataframe(self, symbol: str, count: int = 100) -> pd.DataFrame:
        """获取作为 DataFrame（方便计算指标）"""
        klines = self.get_klines(symbol, count)
        if not klines:
            return pd.DataFrame()
        df = pd.DataFrame(klines)
        df.set_index('timestamp', inplace=True)
        return df


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

        # 判断交叉（最简单的金叉死叉）
        # fast_ma[i-2] <= slow_ma[i-2] and fast_ma[i-1] > slow_ma[i-1] -> 金叉买入
        # fast_ma[i-2] >= slow_ma[i-2] and fast_ma[i-1] < slow_ma[i-1] -> 死叉卖出

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
            # 止损止盈检查（简化）
            current_price = df['close'].iloc[-1]
            change = (current_price - self.entry_price) / self.entry_price
            if change <= -self.stop_loss_pct:
                self.state = "out"
                return {"action": "sell", "reason": "触发止损"}
            if change >= self.take_profit_pct:
                self.state = "out"
                return {"action": "sell", "reason": "达到止盈"}

            # 死叉平仓
            if prev_fast >= prev_slow and curr_fast < curr_slow:
                self.state = "out"
                return {"action": "sell", "reason": "MA死叉"}

        return None

    def reset(self):
        """重置策略状态"""
        self.state = "out"
        self.entry_price = 0.0


class StrategyEngine:
    """策略引擎 - 支持多种策略"""

    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self.kline_cache = KLineCache()
        self.strategy = self._create_strategy(self.config)
        logger.info(f"策略引擎初始化: {self.strategy.name}")

    def _load_config(self, path: str) -> Dict[str, Any]:
        import json
        with open(path, 'r') as f:
            return json.load(f)

    def _create_strategy(self, config: Dict[str, Any]):
        """根据配置创建策略实例"""
        # 支持多种策略
        if "type" in config:
            strategy_type = config["type"]
            if strategy_type == "ma_cross":
                from .strategies.ma_cross import MovingAverageStrategy
                return MovingAverageStrategy(config)
            elif strategy_type == "rsi":
                from .strategies.rsi_strategy import RSIStrategy
                return RSIStrategy(config)
            elif strategy_type == "bollinger":
                from .strategies.bollinger_bands import BollingerBandsStrategy
                return BollingerBandsStrategy(config)
            elif strategy_type == "macd":
                from .strategies.macd import MACDStrategy
                return MACDStrategy(config)
            else:
                raise ValueError(f"不支持的策略类型: {strategy_type}")
        else:
            # 向后兼容：默认使用 MA 交叉（旧的配置格式）
            return MovingAverageStrategy(config)

    async def on_kline(self, kline: Dict[str, Any]):
        """
        收到 K 线数据（Binance WS 推送）

        Args:
            kline: {
                "exchange": "binance",
                "symbol": "BTC/USDT",
                "timestamp": ...,
                "open": ..., "high": ..., "low": ..., "close": ..., "volume": ...,
                "is_closed": true/false
            }
        """
        symbol = kline["symbol"]
        # 只处理已闭合的 K 线，避免未闭合的干扰
        if not kline.get("is_closed", True):
            # 未闭合的K线，可以更新缓存，但不触发策略判断
            self.kline_cache.add_kline(symbol, {
                "timestamp": kline["timestamp"],
                "open": kline["open"],
                "high": kline["high"],
                "low": kline["low"],
                "close": kline["close"],
                "volume": kline["volume"]
            })
            return

        # 添加完整 K 线到缓存
        self.kline_cache.add_kline(symbol, {
            "timestamp": kline["timestamp"],
            "open": kline["open"],
            "high": kline["high"],
            "low": kline["low"],
            "close": kline["close"],
            "volume": kline["volume"]
        })

        # 策略判断
        df = self.kline_cache.get_dataframe(symbol, 100)
        signal = self.strategy.on_kline(df)
        if signal:
            logger.info(f"策略信号: {signal}")
            # 发送信号给执行器（需要通过回调）
            if hasattr(self, 'signal_callback'):
                price = kline["close"]
                await self.signal_callback(signal, price, symbol)

    def set_signal_callback(self, callback):
        """设置信号回调"""
        self.signal_callback = callback

    def get_status(self) -> Dict[str, Any]:
        """获取策略状态"""
        return {
            "name": self.strategy.name,
            "state": self.strategy.state,
            "entry_price": self.strategy.entry_price,
            "kline_count": len(self.kline_cache.get_klines(self.config["symbol"]))
        }


# 测试
if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)

    engine = StrategyEngine("config/strategies/ma_cross.json")

    # 模拟价格序列
    prices = [50000 + i*10 for i in range(200)]
    for p in prices:
        asyncio.run(engine.on_price({
            "exchange": "binance",
            "symbol": "BTC/USDT",
            "price": p,
            "timestamp": 1234567890 + p
        }))
    print("Done")
