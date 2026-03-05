import asyncio
import logging
from typing import Dict, Any, List
from enum import Enum
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)

# 尝试导入 CCXTExchange（可选，避免未安装时报错）
try:
    from src.exchange.ccxt_exchange import CCXTExchange
except ImportError:
    CCXTExchange = None


class OrderType(Enum):
    """订单类型枚举"""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


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
        strategy = order.get("strategy")  # 策略名称

        if self.mode == "local":
            return await self._execute_local(order, symbol, side, quantity, price, order_type, strategy)
        elif self.mode in ("testnet", "live"):
            return await self._execute_ccxt(symbol, side, quantity, price, order_type)
        else:
            return {"success": False, "error": f"未知模式: {self.mode}"}

    async def _execute_local(self, order, symbol, side, quantity, price, order_type, strategy: str = None) -> Dict[str, Any]:
        """本地模拟执行"""
        # 获取当前市场价格（从 kline cache 或使用默认）
        current_price = self._get_current_price(symbol)
        if price is None and order_type != "market":
            price = current_price

        if order_type == OrderType.MARKET.value:
            return await self._execute_market_local(symbol, side, quantity, current_price, strategy)
        elif order_type == OrderType.LIMIT.value:
            return await self._execute_limit_local(symbol, side, quantity, price, strategy, current_price)
        elif order_type == OrderType.STOP_LOSS.value:
            return await self._execute_stop_loss_local(symbol, side, quantity, price, strategy, current_price)
        elif order_type == OrderType.TAKE_PROFIT.value:
            return await self._execute_take_profit_local(symbol, side, quantity, price, strategy, current_price)
        else:
            return {"success": False, "error": f"未知订单类型: {order_type}"}

    async def _execute_market_local(self, symbol, side, quantity, price, strategy: str = None) -> Dict[str, Any]:
        """执行市价单（本地）"""
        if side == "buy":
            cost = price * quantity
            usdt_balance = self.simulation_db.get_balance("USDT")
            if usdt_balance < cost:
                raise ValueError(f"USDT 余额不足: 需要 ${cost:.2f}, 当前 ${usdt_balance:.2f}")

            self.simulation_db.set_balance("USDT", usdt_balance - cost)
            self.simulation_db.open_position(symbol, "long", quantity, price)

            # 记录买入交易（策略名）
            fee = cost * 0.001
            conn = self.simulation_db._get_connection()
            try:
                conn.execute("""
                    INSERT INTO trades (symbol, side, quantity, price, fee, pnl, strategy, executed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (symbol, "buy", quantity, price, fee, 0.0, strategy))
                conn.commit()
            finally:
                conn.close()

            return {
                "success": True,
                "order_id": f"local_{datetime.now().timestamp()}",
                "filled_quantity": quantity,
                "avg_price": price,
                "fee": fee,
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
            pnl = self.simulation_db.close_position(symbol, "long", quantity, exit_price, strategy=strategy)
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

    async def _execute_limit_local(self, symbol, side, quantity, limit_price, strategy: str = None, current_price: float = None) -> Dict[str, Any]:
        """执行限价单（本地）"""
        # 检查是否立即成交
        if side == "buy" and current_price <= limit_price:
            # 市价低于限价，立即成交
            return await self._execute_market_local(symbol, side, quantity, limit_price, strategy)
        elif side == "sell" and current_price >= limit_price:
            # 市价高于限价，立即成交
            return await self._execute_market_local(symbol, side, quantity, limit_price, strategy)
        else:
            # 未成交，返回挂单状态
            # 在实际系统中，我们会把订单存入待成交队列，需要轮询
            # 这里简化，返回 pending 状态，不记录到数据库
            return {
                "success": True,
                "order_id": f"limit_pending_{datetime.now().timestamp()}",
                "filled_quantity": 0.0,
                "avg_price": 0.0,
                "fee": 0.0,
                "pnl": 0.0,
                "status": "pending",
                "message": "订单已提交，等待成交"
            }

    async def _execute_stop_loss_local(self, symbol, side, quantity, stop_price, strategy: str = None, current_price: float = None) -> Dict[str, Any]:
        """执行止损单（本地）"""
        # 止损逻辑：当价格达到止损价时，触发市价单
        # 对于多头止损：当市场价格 <= stop_price 时，触发卖出
        # 这里简化：立即检查是否已触发
        if current_price <= stop_price:
            # 触发，执行市价卖出
            return await self._execute_market_local(symbol, "sell", quantity, current_price, strategy)
        else:
            # 未触发，返回 pending
            return {
                "success": True,
                "order_id": f"stop_loss_pending_{datetime.now().timestamp()}",
                "filled_quantity": 0.0,
                "avg_price": 0.0,
                "fee": 0.0,
                "pnl": 0.0,
                "status": "pending",
                "message": "止损单已设定，等待触发"
            }

    async def _execute_take_profit_local(self, symbol, side, quantity, take_profit_price, strategy: str = None, current_price: float = None) -> Dict[str, Any]:
        """执行止盈单（本地）"""
        # 止盈逻辑：当价格达到止盈价时，触发市价单
        # 对于多头止盈：当市场价格 >= take_profit_price 时，触发卖出
        if current_price >= take_profit_price:
            return await self._execute_market_local(symbol, "sell", quantity, current_price, strategy)
        else:
            return {
                "success": True,
                "order_id": f"take_profit_pending_{datetime.now().timestamp()}",
                "filled_quantity": 0.0,
                "avg_price": 0.0,
                "fee": 0.0,
                "pnl": 0.0,
                "status": "pending",
                "message": "止盈单已设定，等待触发"
            }

    def _get_current_price(self, symbol: str) -> float:
        """获取当前价格（本地模式）"""
        # 尝试从策略引擎的 kline cache 获取
        # 由于 executor 可能没有直接的 strategy_engine 引用，这里通过全局途径或配置
        # 暂时返回固定值，实际需要从外部传入或从数据库/缓存读取
        return 50000.0  # TODO: 从实时数据源获取

    async def _execute_ccxt(self, symbol: str, side: str, quantity: float, price: float = None, order_type: str = 'market') -> Dict[str, Any]:
        """通过 CCXT 执行订单（testnet/live）"""
        try:
            # 根据订单类型执行
            if order_type == 'market':
                result = await self.exchange.create_market_order(symbol, side, quantity)
            elif order_type == 'limit':
                if price is None:
                    return {'success': False, 'error': '限价单需要指定价格'}
                result = await self.exchange.create_limit_order(symbol, side, quantity, price)
            elif order_type == 'stop_loss':
                if price is None:
                    return {'success': False, 'error': '止损单需要指定 stop_price'}
                result = await self.exchange.create_stop_loss_order(symbol, side, quantity, stop_price=price)
            elif order_type == 'take_profit':
                if price is None:
                    return {'success': False, 'error': '止盈单需要指定 take_profit_price'}
                result = await self.exchange.create_take_profit_order(symbol, side, quantity, take_profit_price=price)
            else:
                return {'success': False, 'error': f'不支持的订单类型: {order_type}'}

            if result['success']:
                return {
                    "success": True,
                    "order_id": result['order_id'],
                    "filled_quantity": result.get('filled', quantity if order_type == 'market' else 0.0),
                    "avg_price": result.get('avg_price', price or 0),
                    "fee": result.get('fee', 0.0),
                    "pnl": 0.0,
                    "status": result.get('status', 'open')
                }
            else:
                return result
        except Exception as e:
            logger.error(f"CCXT 订单执行失败: {e}")
            return {'success': False, 'error': str(e)}

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
