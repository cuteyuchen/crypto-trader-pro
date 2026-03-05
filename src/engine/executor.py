import asyncio
import logging
from typing import Dict, Any, List
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)

# 尝试导入 CCXTExchange（可选，避免未安装时报错）
try:
    from src.exchange.ccxt_exchange import CCXTExchange
except ImportError:
    CCXTExchange = None


class OrderExecutor:
    """订单执行器 - 支持 local | testnet | live"""

    def __init__(self, mode: str, config: Dict[str, Any], simulation_db=None, exchange_config: Dict = None):
        """
        Args:
            mode: "local" | "testnet" | "live"
            config: 本地模拟的配置（local 模式需要）
            simulation_db: SimulationDB 实例（local 模式）
            exchange_config: 交易所配置（testnet/live 需要），包含 exchange_id, api_key, secret, testnet
        """
        self.mode = mode
        self.config = config
        self.simulation_db = simulation_db
        self.exchange_config = exchange_config or {}
        self.exchange = None  # CCXTExchange 实例（testnet/live 用）
        self.initialized = False

    async def initialize(self):
        """初始化连接"""
        if self.mode == "local":
            logger.info("执行器初始化：本地模拟模式")
            self.initialized = True
            return

        if CCXTExchange is None:
            raise RuntimeError("CCXTExchange 模块不可用，请安装 ccxt 库")

        exchange_id = self.exchange_config.get("exchange_id", "binance")
        self.exchange = CCXTExchange(exchange_id, {
            "api_key": self.exchange_config["api_key"],
            "secret": self.exchange_config["secret"],
            "testnet": self.exchange_config.get("testnet", self.mode == "testnet"),
        })
        await self.exchange.initialize()
        self.initialized = True
        logger.info(f"执行器初始化完成（{self.mode} 模式）")

    async def execute_order(self, order_request: Dict[str, Any]) -> Dict[str, Any]:
        """执行订单"""
        if not self.initialized:
            await self.initialize()

        try:
            result = await self._execute(order_request)
            logger.info(f"订单执行: {order_request['symbol']} {order_request['side']} "
                        f"数量 {order_request['quantity']} 结果: {result['success']}")
            return result
        except Exception as e:
            logger.error(f"订单执行异常: {e}")
            return {"success": False, "error": str(e)}

    async def _execute(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """实际执行逻辑"""
        symbol = order["symbol"]
        side = order["side"]
        quantity = float(order["quantity"])
        order_type = order.get("type", "market")
        price = order.get("price")

        if self.mode == "local":
            return await self._execute_local(order, symbol, side, quantity, price, order_type)
        elif self.mode in ("testnet", "live"):
            return await self._execute_ccxt(symbol, side, quantity, price)
        else:
            return {"success": False, "error": f"未知模式: {self.mode}"}

    async def _execute_local(self, order, symbol, side, quantity, price, order_type) -> Dict[str, Any]:
        """本地模拟执行"""
        if price is None:
            price = 50000.0  # 默认假价格，实际应从 WS 获取

        if side == "buy":
            cost = price * quantity
            usdt_balance = self.simulation_db.get_balance("USDT")
            if usdt_balance < cost:
                raise ValueError(f"USDT 余额不足: 需要 ${cost:.2f}, 当前 ${usdt_balance:.2f}")

            self.simulation_db.set_balance("USDT", usdt_balance - cost)
            self.simulation_db.open_position(symbol, "long", quantity, price)

            return {
                "success": True,
                "order_id": f"local_{datetime.now().timestamp()}",
                "filled_quantity": quantity,
                "avg_price": price,
                "fee": cost * 0.001,
                "pnl": 0.0
            }

        elif side == "sell":
            positions = self.simulation_db.get_open_positions(symbol)
            long_positions = [p for p in positions if p["side"] == "long"]
            total_btc = sum(p["quantity"] for p in long_positions)
            if total_btc < quantity:
                raise ValueError(f"BTC 持仓不足: 需要 {quantity}, 可用 {total_btc}")

            if not long_positions:
                raise ValueError("没有可平的长仓持仓")

            exit_price = price
            pnl = self.simulation_db.close_position(symbol, "long", quantity, exit_price)
            proceeds = exit_price * quantity
            fee = proceeds * 0.001
            net = proceeds - fee
            current_usdt = self.simulation_db.get_balance("USDT")
            self.simulation_db.set_balance("USDT", current_usdt + net)

            return {
                "success": True,
                "order_id": f"local_{datetime.now().timestamp()}",
                "filled_quantity": quantity,
                "avg_price": exit_price,
                "fee": fee,
                "pnl": pnl
            }

        return {"success": False, "error": "未知操作"}

    async def _execute_ccxt(self, symbol: str, side: str, quantity: float, price: float = None) -> Dict[str, Any]:
        """通过 CCXT 执行订单（testnet/live）"""
        # 对于市价单，CCXT amount 是基础货币数量
        result = await self.exchange.create_market_order(symbol, side, quantity)
        if result['success']:
            return {
                "success": True,
                "order_id": result['order_id'],
                "filled_quantity": result['filled'],
                "avg_price": result['avg_price'],
                "fee": result['fee'],
                "pnl": 0.0  # 平仓盈亏由策略引擎根据持仓成本单独计算，这里不处理
            }
        else:
            return result

    # ---------- 数据查询接口（供 dashboard 和 main 使用） ----------
    async def get_balance(self, currency: str = "USDT") -> float:
        """获取余额"""
        if self.mode == "local":
            return self.simulation_db.get_balance(currency)
        else:
            return await self.exchange.fetch_balance(currency)

    async def get_positions(self, symbol: str = None) -> List[Dict]:
        """获取持仓列表"""
        if self.mode == "local":
            if symbol:
                positions = self.simulation_db.get_open_positions(symbol)
                # 补充当前价格（从策略缓存或返回0）
                return positions
            else:
                # 本地模式只支持单一 symbol，可扩展
                return []
        else:
            positions = await self.exchange.fetch_positions(symbol)
            # 标准化为本地格式（简化）
            # 这里返回交易所原始格式，dashboard 需要适配
            return positions

    async def get_recent_trades(self, symbol: str = None, limit: int = 20) -> List[Dict]:
        """获取最近交易记录"""
        if self.mode == "local":
            conn = self.simulation_db._get_connection()
            try:
                conn.row_factory = sqlite3.Row
                cur = conn.execute('''
                    SELECT * FROM trades 
                    ORDER BY executed_at DESC 
                    LIMIT ?
                ''', (limit,))
                rows = cur.fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()
        else:
            # CCXT 返回的 trades 格式可能不同
            return await self.exchange.fetch_my_trades(symbol, limit)

    async def close(self):
        """清理资源"""
        if self.exchange:
            await self.exchange.close()
        logger.info("执行器已关闭")
