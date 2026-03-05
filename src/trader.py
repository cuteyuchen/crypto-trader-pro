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

    def __init__(self, trade_id: str, symbol: str, side: str, quantity: float, entry_price: float, strategy: str, stop_loss_price: float = None, take_profit_price: float = None):
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
        self.stop_loss_price = stop_loss_price  # 止损触发价
        self.take_profit_price = take_profit_price  # 止盈触发价

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
        self._lock = asyncio.Lock()  # 保护 open_trades 列表的线程安全

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
        async with self._lock:
            for trade in self.open_trades:
                trade.update_price(price)

        # 先检查止损/止盈条件（优先级高于开仓信号）
        await self._check_stop_conditions(price)

        # 如果自动交易关闭，跳过
        if not self.auto_trade:
            return

        # 检查是否还能开新仓（注意：_check_stop_conditions 可能会减少持仓）
        async with self._lock:
            if len(self.open_trades) >= self.max_open_trades:
                return

        # 获取策略信号
        signal = self.strategy_engine.strategy.check_signal(price)
        if not signal or signal['action'] == 'hold':
            return

        # 执行买入
        if signal['action'] == 'buy':
            await self._execute_buy(price, signal['reason'])
        # 执行卖出（仅当有持仓时）- 注意：这里的卖出主要是策略主动平仓（非止损止盈）
        elif signal['action'] == 'sell':
            async with self._lock:
                if self.open_trades:
                    # 平掉所有多头（简化：只平仓最早的一笔）
                    trade = self.open_trades[0]
            if self.open_trades:
                await self._execute_sell(trade, price, signal['reason'])

    async def _check_stop_conditions(self, price: float):
        """
        检查所有持仓的止损/止盈条件

        这是一个独立的检查，优先级高于策略信号
        """
        async with self._lock:
            # 复制一份 open_trades 列表，避免在遍历时修改原列表导致的并发问题
            trades_to_check = list(self.open_trades)

        for trade in trades_to_check:
            # 如果交易没有设置止损止盈价格，跳过
            if trade.stop_loss_price is None and trade.take_profit_price is None:
                continue

            stop_loss_triggered = False
            take_profit_triggered = False

            if trade.stop_loss_price is not None and price <= trade.stop_loss_price:
                stop_loss_triggered = True

            if trade.take_profit_price is not None and price >= trade.take_profit_price:
                take_profit_triggered = True

            # 如果同时触发（理论上不可能，除非价格正好等于两个阈值），优先止损
            if stop_loss_triggered:
                reason = "止损触发"
                logger.info(f"触发止损: trade={trade.id}, price={price}, stop_loss_price={trade.stop_loss_price}")
                await self._execute_sell(trade, price, reason)
            elif take_profit_triggered:
                reason = "止盈触发"
                logger.info(f"触发止盈: trade={trade.id}, price={price}, take_profit_price={trade.take_profit_price}")
                await self._execute_sell(trade, price, reason)

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
            # 计算止损止盈价格（基于买入成交价）
            entry_price = result.get('avg_price', price)
            strategy_config = self.strategy_engine.config
            stop_loss_pct = strategy_config.get('stop_loss_pct')
            take_profit_pct = strategy_config.get('take_profit_pct')

            stop_loss_price = None
            take_profit_price = None

            if stop_loss_pct is not None:
                stop_loss_price = entry_price * (1 - stop_loss_pct)
            if take_profit_pct is not None:
                take_profit_price = entry_price * (1 + take_profit_pct)

            trade = Trade(
                trade_id=result.get('order_id', f"local_{datetime.now().timestamp()}"),
                symbol=symbol,
                side='long',
                quantity=result.get('filled_quantity', quantity),
                entry_price=entry_price,
                strategy=order['strategy'],
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price
            )
            async with self._lock:
                self.open_trades.append(trade)
            logger.info(f"买入成功: {trade} (止损价: {stop_loss_price}, 止盈价: {take_profit_price})")
            if self.notifier:
                self.notifier.send("open_position", "开仓买入", f"{symbol} 买入 {trade.quantity:.6f} @ ${trade.entry_price:.2f}\n止损价: ${stop_loss_price:.2f if stop_loss_price else '未设置'}\n止盈价: ${take_profit_price:.2f if take_profit_price else '未设置'}\n原因: {reason}", {"trade_id": trade.id, "price": trade.entry_price, "stop_loss_price": stop_loss_price, "take_profit_price": take_profit_price})
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
            # 使用锁保护列表修改操作
            async with self._lock:
                if trade in self.open_trades:
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
                reason_display = reason
                # 如果是策略信号卖出，显示原始原因；如果是止损止盈，特别标注
                if reason in ["止损触发", "止盈触发"]:
                    reason_display = f"【{reason}】"
                self.notifier.send("close_position", "平仓卖出", f"{symbol} 卖出 {trade.quantity:.6f} @ ${result.get('avg_price'):.2f}\n盈亏: {pnl_str}\n原因: {reason_display}", {"trade_id": trade.id, "pnl": pnl, "reason": reason})
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
