"""
自动交易引擎 - 整合策略、执行、风控
设计参考：freqtrade
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from .engine.strategy_engine import StrategyEngine
from .engine.executor import OrderExecutor
from .engine.risk_manager import RiskManager

logger = logging.getLogger(__name__)


class Trade:
    """交易对象"""

    def __init__(self, trade_id: str, symbol: str, side: str, quantity: float, entry_price: float, strategy: str):
        self.id = trade_id
        self.symbol = symbol
        self.side = side  # 'long' 或 'short'（目前只支持 long）
        self.quantity = quantity
        self.entry_price = entry_price
        self.current_price = entry_price
        self.pnl = 0.0
        self.strategy = strategy
        self.opened_at = datetime.now()
        self.closed_at = None
        self.status = "open"  # open | closed

    def update_price(self, price: float):
        """更新当前价格并计算未实现盈亏"""
        self.current_price = price
        if self.side == "long":
            self.pnl = (price - self.entry_price) * self.quantity
        else:
            self.pnl = (self.entry_price - price) * self.quantity

    def close(self, exit_price: float, fee: float = 0.0):
        """平仓"""
        self.closed_at = datetime.now()
        self.status = "closed"
        realized_pnl = (exit_price - self.entry_price) * self.quantity if self.side == "long" else (self.entry_price - exit_price) * self.quantity
        self.pnl = realized_pnl - fee
        return self.pnl


class Trader:
    """自动交易引擎"""

    def __init__(self, config: Dict[str, Any], executor: OrderExecutor, risk_manager: RiskManager, notifier=None):
        """
        Args:
            config: 系统配置（modes + strategy + 其他）
            executor: 执行器
            risk_manager: 风控
            notifier: 通知器（可选）
        """
        self.config = config
        self.executor = executor
        self.risk_manager = risk_manager
        self.notifier = notifier

        # 状态
        self.running = False
        self.auto_trade = config.get("auto_trade", True)
        self.max_open_trades = config.get("max_open_trades", 3)
        self.open_trades: List[Trade] = []
        self.closed_trades: List[Trade] = []
        self.strategy_engine = None  # 稍后注入

        # 统计
        self.total_pnl = 0.0
        self.win_count = 0
        self.loss_count = 0

        logger.info(f"Trader 初始化: auto_trade={self.auto_trade}, max_open_trades={self.max_open_trades}")

    def set_strategy_engine(self, engine: StrategyEngine):
        """注入策略引擎"""
        self.strategy_engine = engine
        logger.info("策略引擎已注入")

    async def start(self):
        """启动自动交易循环"""
        self.running = True
        logger.info("Trader 启动，开始监控信号...")
        while self.running:
            try:
                await self._check_signals()
                await asyncio.sleep(1)  # 每秒检查一次
            except Exception as e:
                logger.error(f"Trader 循环异常: {e}")
                await asyncio.sleep(5)

    def stop(self):
        """停止"""
        self.running = False
        logger.info("Trader 已停止")

    async def _check_signals(self):
        """检查策略信号并执行"""
        if not self.strategy_engine:
            return

        # 获取最新价格（从 executor 或策略缓存）
        price = self._get_latest_price()
        if price is None:
            return

        # 更新持仓的未实现盈亏
        for trade in self.open_trades:
            trade.update_price(price)

        # 如果自动交易关闭，跳过
        if not self.auto_trade:
            return

        # 检查是否还能开新仓
        if len(self.open_trades) >= self.max_open_trades:
            return

        # 获取策略信号
        signal = self.strategy_engine.strategy.check_signal(price)
        if not signal or signal['action'] == 'hold':
            return

        # 执行买入
        if signal['action'] == 'buy':
            await self._execute_buy(price, signal['reason'])
        # 执行卖出（仅当有持仓时）
        elif signal['action'] == 'sell' and self.open_trades:
            # 平掉所有多头（简化：只平仓最早的一笔）
            trade = self.open_trades[0]
            await self._execute_sell(trade, price, signal['reason'])

    def _get_latest_price(self) -> Optional[float]:
        """获取最新价格"""
        # 尝试从策略引擎的 kline cache 获取
        if hasattr(self.strategy_engine, 'kline_cache'):
            symbol = self.strategy_engine.config.get('symbol', 'BTC/USDT')
            klines = self.strategy_engine.kline_cache.get_klines(symbol, 1)
            if klines:
                return klines[-1]['close']
        return None

    async def _execute_buy(self, price: float, reason: str):
        """执行买入"""
        symbol = self.strategy_engine.config.get('symbol', 'BTC/USDT')
        # 计算数量：使用配置的仓位比例
        position_size = self.strategy_engine.config.get('position_size', 0.2)
        balance = await self.executor.get_balance('USDT')
        stake_amount = balance * position_size
        quantity = stake_amount / price

        order = {
            'symbol': symbol,
            'side': 'buy',
            'quantity': quantity,
            'price': price,
            'type': 'market',
            'strategy': self.strategy_engine.config.get('name', 'unknown')
        }

        # 风控检查
        allowed, reason_deny = self.risk_manager.check_order(order, balance)
        if not allowed:
            logger.warning(f"买入被风控拒绝: {reason_deny}")
            return

        result = await self.executor.execute_order(order)
        if result['success']:
            trade = Trade(
                trade_id=result.get('order_id', f"local_{datetime.now().timestamp()}"),
                symbol=symbol,
                side='long',
                quantity=result.get('filled_quantity', quantity),
                entry_price=result.get('avg_price', price),
                strategy=order['strategy']
            )
            self.open_trades.append(trade)
            logger.info(f"买入成功: {trade}")
            if self.notifier:
                self.notifier.send("open_position", "开仓买入", f"{symbol} 买入 {trade.quantity:.6f} @ ${trade.entry_price:.2f}\n原因: {reason}", {"trade_id": trade.id, "price": trade.entry_price})
        else:
            logger.error(f"买入失败: {result.get('error')}")

    async def _execute_sell(self, trade: Trade, price: float, reason: str):
        """执行卖出（平仓）"""
        symbol = trade.symbol
        order = {
            'symbol': symbol,
            'side': 'sell',
            'quantity': trade.quantity,
            'price': price,
            'type': 'market',
            'strategy': trade.strategy
        }

        result = await self.executor.execute_order(order)
        if result['success']:
            pnl = trade.close(result.get('avg_price', price), result.get('fee', 0.0))
            self.open_trades.remove(trade)
            self.closed_trades.append(trade)
            self.total_pnl += pnl
            if pnl > 0:
                self.win_count += 1
            else:
                self.loss_count += 1
            logger.info(f"卖出成功: {trade} 盈亏 ${pnl:.2f}")
            if self.notifier:
                pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
                self.notifier.send("close_position", "平仓卖出", f"{symbol} 卖出 {trade.quantity:.6f} @ ${result.get('avg_price'):.2f}\n盈亏: {pnl_str}\n原因: {reason}", {"trade_id": trade.id, "pnl": pnl})
        else:
            logger.error(f"卖出失败: {result.get('error')}")

    def get_status(self) -> Dict[str, Any]:
        """获取交易状态"""
        return {
            "running": self.running,
            "auto_trade": self.auto_trade,
            "open_trades_count": len(self.open_trades),
            "closed_trades_count": len(self.closed_trades),
            "total_pnl": self.total_pnl,
            "win_rate": (self.win_count / max(1, (self.win_count + self.loss_count))) * 100,
            "max_open_trades": self.max_open_trades
        }

    def get_open_trades(self) -> List[Dict]:
        """获取活跃交易列表"""
        return [{
            "id": t.id,
            "symbol": t.symbol,
            "side": t.side,
            "quantity": t.quantity,
            "entry_price": t.entry_price,
            "current_price": t.current_price,
            "pnl": t.pnl,
            "opened_at": t.opened_at.isoformat()
        } for t in self.open_trades]

    def get_closed_trades(self, limit: int = 20) -> List[Dict]:
        """获取历史交易"""
        trades = sorted(self.closed_trades, key=lambda x: x.closed_at, reverse=True)[:limit]
        return [{
            "id": t.id,
            "symbol": t.symbol,
            "side": t.side,
            "quantity": t.quantity,
            "entry_price": t.entry_price,
            "exit_price": t.current_price,
            "pnl": t.pnl,
            "opened_at": t.opened_at.isoformat(),
            "closed_at": t.closed_at.isoformat() if t.closed_at else None
        } for t in trades]

    def force_close_all(self):
        """强制平仓所有持仓（用于停止时）"""
        # 实际需要价格，这里简化，将在主循环中调用
        pass
