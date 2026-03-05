"""
CCXT 交易所封装 - 支持 testnet 和 live
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
import ccxt.async_support as ccxt

logger = logging.getLogger(__name__)


class CCXTExchange:
    """CCXT 交易所包装器"""

    def __init__(self, exchange_id: str, config: Dict[str, Any]):
        """
        Args:
            exchange_id: 'binance', 'okx', etc.
            config: 配置，必须包含 apiKey, secret, 可选 testnet
        """
        self.exchange_id = exchange_id
        self.config = config
        self.exchange = None
        self._init_exchange()

    def _init_exchange(self):
        """初始化 ccxt exchange 实例"""
        exchange_class = getattr(ccxt, self.exchange_id)
        self.exchange = exchange_class({
            'apiKey': self.config['api_key'],
            'secret': self.config['secret'],
            'timeout': 30000,
            'enableRateLimit': True,
        })
        if self.config.get('testnet', False):
            # 币安 testnet 需要设置URL
            if self.exchange_id == 'binance':
                self.exchange.urls['api'] = 'https://testnet.binance.vision/api'
            logger.info(f"已启用 {self.exchange_id} testnet 模式")
        else:
            logger.info(f"已启用 {self.exchange_id} live 模式")

    async def initialize(self):
        """加载市场信息"""
        await self.exchange.load_markets()
        logger.info(f"交易所 {self.exchange_id} 初始化完成，支持 {len(self.exchange.markets)} 个交易对")

    async def fetch_balance(self, currency: str = 'USDT') -> float:
        """获取余额"""
        try:
            balance = await self.exchange.fetch_balance()
            free = balance.get(currency, {}).get('free', 0.0)
            return float(free)
        except Exception as e:
            logger.error(f"获取余额失败: {e}")
            return 0.0

    async def fetch_positions(self, symbol: str = None) -> List[Dict]:
        """
        获取当前持仓（现货账户不适用，返回空列表）
        永续合约/期货模式才需要
        """
        # 现货模式：通过余额判断持仓
        if self.exchange_id in ['binance', 'okx']:
            # 现货：返回 base currency 余额作为持仓
            if symbol:
                base = symbol.split('/')[1]  # BTC/USDT -> USDT? Actually base is quote? For spot, we hold base asset.
                # Actually symbol format: BTC/USDT -> base=BTC, quote=USDT
                parts = symbol.split('/')
                if len(parts) == 2:
                    base_currency = parts[0]  # BTC
                    balance = await self.fetch_balance(base_currency)
                    if balance > 0:
                        # 需要当前价格来计算价值，这里只返回数量
                        return [{
                            'symbol': symbol,
                            'quantity': balance,
                            'side': 'long',
                            'entry_price': 0.0  # 无法直接获取，需要额外查询
                        }]
            return []
        else:
            # 期货：调用 fetch_positions
            try:
                positions = await self.exchange.fetch_positions([symbol] if symbol else None)
                return positions
            except Exception as e:
                logger.error(f"获取持仓失败: {e}")
                return []

    async def create_market_order(self, symbol: str, side: str, amount: float, price: float = None) -> Dict[str, Any]:
        """创建市价单"""
        try:
            # amount 是 base currency 数量（对于买入/卖出）
            order = await self.exchange.create_market_order(symbol, side, amount)
            logger.info(f"订单创建成功: {side} {amount} {symbol}, order_id={order['id']}")
            return {
                'success': True,
                'order_id': order['id'],
                'filled': order.get('filled', amount),
                'avg_price': order.get('average', price or 0),
                'fee': order.get('fee', {}).get('cost', 0.0),
                'raw': order
            }
        except Exception as e:
            logger.error(f"订单创建失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def fetch_my_trades(self, symbol: str = None, limit: int = 20) -> List[Dict]:
        """获取我的交易历史"""
        try:
            trades = await self.exchange.fetch_my_trades(symbol, limit=limit)
            return trades
        except Exception as e:
            logger.error(f"获取交易历史失败: {e}")
            return []

    async def close(self):
        """关闭连接"""
        if self.exchange:
            await self.exchange.close()
            logger.info("交易所连接已关闭")
