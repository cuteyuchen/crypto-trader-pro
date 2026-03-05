import asyncio
import logging
import json
import os
import threading
import sqlite3
from datetime import date
from dotenv import load_dotenv

# 导入自定义模块
from src.ws.binance_ws import BinanceWS
from src.ws.okx_ws import OKXWS
from src.data.simulation_db import SimulationDB
from src.engine.strategy_engine import StrategyEngine
from src.engine.executor import OrderExecutor
from src.engine.risk_manager import RiskManager
from src.dashboard.app import Dashboard
from src.notifier import NotificationManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TradingBot:
    """交易机器人主控制器"""

    def __init__(self):
        self.running = False
        self.load_config()
        self.init_components()
        self.last_daily_report_date = None  # 上次发送日报的日期

    def load_config(self):
        """加载配置文件"""
        # 加载环境变量
        load_dotenv(".env")

        with open("config/modes.json", "r") as f:
            self.mode_config = json.load(f)

        with open("config/risk.json", "r") as f:
            self.risk_config = json.load(f)

        with open("config/strategies/ma_cross.json", "r") as f:
            self.strategy_config = json.load(f)

        with open("config/simulation/local.json", "r") as f:
            self.sim_config = json.load(f)

        # 加载交易所配置（testnet/live 需要）
        self.exchange_config = None
        mode = self.mode_config["mode"]
        if mode in ("testnet", "live"):
            exchange_id = self.mode_config.get("exchange", "binance")
            # 从环境变量读取 API Key/Secret
            api_key = os.getenv(f"{exchange_id.upper()}_API_KEY")
            api_secret = os.getenv(f"{exchange_id.upper()}_SECRET_KEY")
            if not api_key or not api_secret:
                raise ValueError(f"请在 .env 文件中设置 {exchange_id.upper()}_API_KEY 和 {exchange_id.upper()}_SECRET_KEY")
            self.exchange_config = {
                "exchange_id": exchange_id,
                "api_key": api_key,
                "secret": api_secret,
                "testnet": (mode == "testnet")
            }
            logger.info(f"模式: {mode} (交易所 API)")
            logger.info(f"交易所: {exchange_id} 配置已从环境变量加载")
        else:
            logger.info(f"模式: {mode}")
            logger.info(f"初始余额: {self.sim_config['initial_balance']}")

    def init_components(self):
        """初始化组件"""
        mode = self.mode_config["mode"]

        # 数据库（local 模式需要）
        if mode == "local":
            self.db = SimulationDB()
            self.db.set_balance("USDT", self.sim_config["initial_balance"])
        else:
            self.db = None

        # 策略引擎
        self.strategy_engine = StrategyEngine("config/strategies/ma_cross.json")
        self.strategy_engine.set_signal_callback(self.on_signal)

        # 执行器
        exchange_cfg = self.exchange_config if mode in ("testnet", "live") else None
        self.executor = OrderExecutor(mode, self.sim_config, simulation_db=self.db, exchange_config=exchange_cfg)
        self.executor_ready = asyncio.Future()  # 用于标记初始化完成

        # 风控
        self.risk_manager = RiskManager(self.risk_config, simulation_db=self.db)
        self.risk_manager.initial_balance = self.sim_config["initial_balance"]

        # WebSocket（支持多交易所）
        exchange = self.mode_config.get("exchange", "binance").lower()
        symbol_config = self.strategy_config["symbol"]
        if exchange == "binance":
            ws_symbol = symbol_config.lower().replace("/", "")
            self.ws = BinanceWS(symbol=ws_symbol, callback=self.on_kline)
        elif exchange == "okx":
            ws_symbol = symbol_config.upper().replace("/", "-")
            self.ws = OKXWS(symbol=ws_symbol, callback=self.on_kline)
        else:
            raise ValueError(f"不支持的交易所: {exchange}")
        logger.info(f"使用交易所: {exchange}, 交易对: {symbol_config}")

        # Dashboard（可选）
        self.dashboard = None
        if self.mode_config.get("dashboard_enabled", True):
            self.dashboard = Dashboard(self, host='0.0.0.0', port=5000)
            logger.info("Dashboard 已启用 (http://localhost:5000)")

        # 通知管理器（默认启用）
        self.notifier = NotificationManager("data")
        self.notifications_enabled = self.mode_config.get("notifications_enabled", True)

    async def on_kline(self, kline: dict):
        """K线回调"""
        # 更新策略引擎
        await self.strategy_engine.on_kline(kline)

    async def on_signal(self, signal: dict, price: float, symbol: str):
        """策略信号回调"""
        logger.info(f"收到信号: {signal}, 价格: ${price:.2f}")

        action = signal["action"]
        if action == "buy":
            # 计算买入数量：固定比例仓位
            balance = self.db.get_balance("USDT") if self.db else 10000
            position_amount = balance * self.strategy_config["position_size"]
            quantity = position_amount / price

            order = {
                "symbol": symbol,
                "side": "buy",
                "quantity": quantity,
                "price": price,
                "type": "market",
                "strategy": self.strategy_config["name"]
            }

            # 风控检查
            allowed, reason = self.risk_manager.check_order(order, balance)
            if not allowed:
                logger.warning(f"风控拒绝买入: {reason}")
                if self.notifications_enabled:
                    self.notifier.send("error", "买入订单被风控拒绝", reason, {
                        "signal": signal,
                        "price": price,
                        "balance": balance
                    })
                return

            result = await self.executor.execute_order(order)
            if result["success"]:
                logger.info(f"买入成功: 数量 {result['filled_quantity']:.6f}, 均价 ${result['avg_price']:.2f}")
                if self.notifications_enabled:
                    self.notifier.send("open_position", "开仓买入", 
                        f"买入 {symbol} {result['filled_quantity']:.6f} @ ${result['avg_price']:.2f}\n"
                        f"原因: {signal['reason']}\n"
                        f"手续费: ${result['fee']:.4f}",
                        {
                            "symbol": symbol,
                            "side": "buy",
                            "quantity": result['filled_quantity'],
                            "price": result['avg_price'],
                            "fee": result['fee'],
                            "reason": signal['reason']
                        }
                    )
            else:
                logger.error(f"买入失败: {result['error']}")
                if self.notifications_enabled:
                    self.notifier.send("error", "买入订单执行失败", result['error'], {
                        "signal": signal,
                        "price": price,
                        "quantity": quantity
                    })

        elif action == "sell":
            # 查看持仓
            positions = self.db.get_open_positions(symbol)
            long_positions = [p for p in positions if p["side"] == "long"]
            total_btc = sum(p["quantity"] for p in long_positions)
            if total_btc <= 0:
                logger.warning("没有 BTC 持仓，无法卖出")
                return

            quantity = total_btc  # 全平

            order = {
                "symbol": symbol,
                "side": "sell",
                "quantity": quantity,
                "price": price,
                "type": "market",
                "strategy": self.strategy_config["name"]
            }

            allowed, reason = self.risk_manager.check_order(order, 0)
            if not allowed:
                logger.warning(f"风控拒绝卖出: {reason}")
                if self.notifications_enabled:
                    self.notifier.send("error", "卖出订单被风控拒绝", reason, {
                        "signal": signal,
                        "price": price,
                        "quantity": quantity
                    })
                return

            result = await self.executor.execute_order(order)
            if result["success"]:
                logger.info(f"卖出成功: 数量 {result['filled_quantity']:.6f}, 盈亏 ${result['pnl']:.2f}")
                self.risk_manager.on_trade_completed(result["pnl"])
                if self.notifications_enabled:
                    pnl = result['pnl']
                    pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
                    self.notifier.send("close_position", "平仓卖出",
                        f"卖出 {symbol} {result['filled_quantity']:.6f} @ ${result['avg_price']:.2f}\n"
                        f"盈亏: {pnl_str}\n"
                        f"原因: {signal['reason']}",
                        {
                            "symbol": symbol,
                            "side": "sell",
                            "quantity": result['filled_quantity'],
                            "price": result['avg_price'],
                            "pnl": pnl,
                            "fee": result['fee'],
                            "reason": signal['reason']
                        }
                    )
            else:
                logger.error(f"卖出失败: {result['error']}")
                if self.notifications_enabled:
                    self.notifier.send("error", "卖出订单执行失败", result['error'], {
                        "signal": signal,
                        "price": price,
                        "quantity": quantity
                    })

    async def run(self):
        """主运行循环"""
        self.running = True
        logger.info("启动交易机器人...")

        # 1. 初始化执行器（异步等待完成）
        await self.executor.initialize()
        self.executor_ready.set_result(True)  # 标记完成
        logger.info("执行器初始化完成")

        # 保存事件循环引用，供 Dashboard 线程使用
        self.event_loop = asyncio.get_running_loop()

        # 2. 启动 Dashboard（后台线程）
        if self.dashboard:
            dashboard_thread = threading.Thread(target=self.dashboard.run, daemon=True)
            dashboard_thread.start()
            logger.info("Dashboard 线程已启动")

        # 3. 启动 WebSocket 监听
        ws_task = asyncio.create_task(self.ws.start())

        # 4. 主循环：打印状态 + 日报检查
        try:
            while self.running:
                await asyncio.sleep(10)
                await self.print_status()
                await self.check_daily_report()
        except KeyboardInterrupt:
            logger.info("收到停止信号")
            self.running = False
            await self.ws.stop()
            ws_task.cancel()

    async def print_status(self):
        """打印当前状态"""
        if self.db:
            usdt = self.db.get_balance("USDT")
            positions = self.db.get_open_positions(self.strategy_config["symbol"])
            total_pnl = sum(p["unrealized_pnl"] for p in positions)
            logger.info(f"[状态] USDT余额: ${usdt:.2f}, 未实现盈亏: ${total_pnl:.2f}, 持仓数: {len(positions)}")
            for pos in positions:
                logger.info(f"  持仓: {pos['symbol']} {pos['side']} {pos['quantity']:.6f} "
                            f"入场价 ${pos['entry_price']:.2f} 当前价 ${pos['current_price']:.2f} 浮盈 ${pos['unrealized_pnl']:.2f}")
        else:
            # testnet/live 模式：从 executor 查询（异步）
            try:
                usdt = await self.executor.get_balance("USDT")
                positions = await self.executor.get_positions(self.strategy_config["symbol"])
                # positions 可能是 CCXT 原始格式，这里简化处理
                logger.info(f"[状态] USDT余额: ${usdt:.2f}, 持仓数: {len(positions)}")
                for pos in positions:
                    # 兼容 CCXT position 结构
                    symbol = pos.get('symbol', self.strategy_config["symbol"])
                    side = pos.get('side', 'long')
                    qty = pos.get('contracts', pos.get('quantity', 0))
                    entry = pos.get('entryPrice', 0)
                    mark = pos.get('markPrice', 0)
                    upnl = pos.get('unrealizedPnl', 0)
                    logger.info(f"  持仓: {symbol} {side} {qty} 入场价 ${entry} 当前价 ${mark} 浮盈 ${upnl}")
            except Exception as e:
                logger.error(f"获取状态失败: {e}")
                logger.info("运行中...")

    async def check_daily_report(self):
        """检查并发送每日报告（如果到了新的一天）"""
        from datetime import date
        today = date.today()
        if self.last_daily_report_date != today:
            # 新的一天，生成日报
            self.last_daily_report_date = today
            if self.notifications_enabled and self.db:
                # 查询昨日已实现盈亏（今日凌晨到现在的交易）
                # 简化：查询今日所有 trades
                conn = self.db._get_connection()
                try:
                    conn.row_factory = sqlite3.Row
                    cur = conn.execute('''
                        SELECT COUNT(*) as trade_count, SUM(pnl) as total_pnl, SUM(fee) as total_fee
                        FROM trades
                        WHERE date(executed_at) = ?
                    ''', (today.isoformat(),))
                    row = cur.fetchone()
                    trade_count = row['trade_count']
                    total_pnl = row['total_pnl'] or 0.0
                    total_fee = row['total_fee'] or 0.0
                finally:
                    conn.close()

                usdt = self.db.get_balance("USDT")
                initial = self.sim_config["initial_balance"]
                net_pnl = total_pnl - total_fee

                report = (
                    f"📊 每日交易报告 - {today}\n\n"
                    f"💰 账户余额: ${usdt:.2f}\n"
                    f"🎯 初始资金: ${initial:.2f}\n"
                    f"📈 今日交易: {trade_count} 笔\n"
                    f"💵 已实现盈亏: ${total_pnl:.2f}\n"
                    f"💸 手续费: ${total_fee:.2f}\n"
                    f"🧮 净盈亏: ${net_pnl:.2f}\n"
                    f"📊 总资产变化: ${usdt - initial:+.2f}"
                )
                self.notifier.send("daily_summary", "每日交易报告", report, {
                    "date": today.isoformat(),
                    "trade_count": trade_count,
                    "total_pnl": total_pnl,
                    "total_fee": total_fee,
                    "net_pnl": net_pnl,
                    "balance": usdt
                })
                logger.info("已发送每日报告")

    async def stop(self):
        """停止"""
        self.running = False


async def main():
    bot = TradingBot()
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序退出")
