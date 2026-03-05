"""
OKX WebSocket 客户端
文档：https://www.okx.com/docs-v5/zh/#websocket-api
"""
import asyncio
import json
import logging
from typing import Callable
import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)


class OKXWS:
    """OKX WebSocket 客户端"""

    def __init__(self, symbol: str = "BTC-USDT", callback: Callable = None):
        """
        Args:
            symbol: 交易对，格式 "BTC-USDT"
            callback: 回调函数，接收 dict
        """
        self.symbol = symbol.upper()  # 保持大写，OKX 需要
        self.callback = callback
        self.ws_url = "wss://ws.okx.com:8443/ws/v5/public"
        self.connection = None
        self.running = False

    async def connect(self):
        """建立连接并订阅K线"""
        url = self.ws_url  # 不使用 brokerId 参数
        logger.info(f"连接到 OKX WS: {url} (symbol: {self.symbol})")
        self.connection = await websockets.connect(url)
        
        # OKX 订阅：channel + instId
        subscribe_msg = {
            "op": "subscribe",
            "args": [
                {
                    "channel": "candle1m",
                    "instId": self.symbol
                }
            ]
        }
        await self.connection.send(json.dumps(subscribe_msg))
        logger.info("OKX WS 已订阅 K线")

    async def disconnect(self):
        if self.connection:
            await self.connection.close()
            logger.info("OKX WS 已断开")

    def _normalize_kline(self, candle: list) -> dict:
        """OKX K线数组转标准格式"""
        # [ts, open, high, low, close, vol, volCcy, ...]
        return {
            "exchange": "okx",
            "symbol": self.symbol.replace("-", "/"),
            "timestamp": int(candle[0]),
            "open": float(candle[1]),
            "high": float(candle[2]),
            "low": float(candle[3]),
            "close": float(candle[4]),
            "volume": float(candle[5]),
            "is_closed": True
        }

    async def listen(self):
        """监听消息"""
        self.running = True
        while self.running:
            try:
                if not self.connection:
                    await self.connect()

                message = await self.connection.recv()
                data = json.loads(message)

                if data.get("event") == "error":
                    logger.error(f"OKX WS 错误: {data}")
                    continue

                if "data" in data and self.callback:
                    for candle in data["data"]:
                        kline = self._normalize_kline(candle)
                        await self.callback(kline)

            except ConnectionClosed as e:
                logger.warning(f"OKX WS 连接关闭: {e}, 重连中...")
                self.connection = None
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"OKX WS 异常: {e}")
                await asyncio.sleep(1)

    async def start(self):
        """启动监听"""
        logger.info("启动 OKX WS 监听...")
        await self.listen()

    def stop(self):
        self.running = False


async def test_callback(kline):
    print(f"OKX K线: {kline['symbol']} close=${kline['close']:.2f}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ws = OKXWS("BTC-USDT", test_callback)
    try:
        asyncio.run(ws.start())
    except KeyboardInterrupt:
        ws.stop()
