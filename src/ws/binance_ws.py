import asyncio
import json
import logging
from typing import Callable, Dict, Any
import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)


class BinanceWS:
    """Binance WebSocket 客户端"""

    def __init__(self, symbol: str = "btcusdt", callback: Callable = None):
        """
        Args:
            symbol: 交易对，小写，如 "btcusdt"
            callback: 收到消息时的回调函数，接收 dict 参数
        """
        self.symbol = symbol.lower()
        self.callback = callback
        self.ws_url = "wss://stream.binance.com:9443/ws"
        self.connection = None
        self.running = False

    async def connect(self):
        """建立 WebSocket 连接"""
        stream_name = f"{self.symbol}@kline_1m"  # 使用 1分钟 K 线流
        url = f"{self.ws_url}/{stream_name}"
        logger.info(f"连接到 Binance WS: {url}")
        self.connection = await websockets.connect(url)
        logger.info("Binance WS 已连接")

    async def disconnect(self):
        """断开连接"""
        if self.connection:
            await self.connection.close()
            logger.info("Binance WS 已断开")

    async def listen(self):
        """监听消息"""
        self.running = True
        while self.running:
            try:
                if not self.connection:
                    await self.connect()

                message = await self.connection.recv()
                data = json.loads(message)

                if self.callback:
                    await self.callback(self._normalize(data))

            except ConnectionClosed as e:
                logger.warning(f"Binance WS 连接关闭: {e}, 尝试重连...")
                self.connection = None
                await asyncio.sleep(5)  # 重连间隔
            except Exception as e:
                logger.error(f"Binance WS 错误: {e}")
                await asyncio.sleep(1)

    def _normalize(self, data: dict) -> dict:
        """标准化 K 线数据格式"""
        k = data.get("k", {})
        return {
            "exchange": "binance",
            "symbol": k.get("s", "").upper(),
            "timestamp": k.get("t", 0),  # K线开始时间
            "open": float(k.get("o", 0)),
            "high": float(k.get("h", 0)),
            "low": float(k.get("l", 0)),
            "close": float(k.get("c", 0)),
            "volume": float(k.get("v", 0)),
            "is_closed": k.get("x", False),
            "raw": data
        }

    async def start(self):
        """启动监听（异步）"""
        logger.info("启动 Binance WS 监听...")
        await self.listen()

    def stop(self):
        """停止监听"""
        self.running = False


# 测试用
async def test_callback(data):
    print(f"收到价格: {data['symbol']} = ${data['price']:.2f}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ws = BinanceWS("btcusdt", test_callback)
    try:
        asyncio.run(ws.start())
    except KeyboardInterrupt:
        ws.stop()
