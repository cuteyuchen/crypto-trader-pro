"""
简易回测引擎
"""
import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class BacktestEngine:
    """回测引擎（简化版）"""

    def __init__(self, strategy_config: Dict[str, Any], initial_balance: float = 10000.0):
        self.strategy_config = strategy_config
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.position = 0.0  # 持仓数量（基础货币）
        self.entry_price = 0.0
        self.trades = []  # 交易记录
        self.equity_curve = []  # 每根K线的净资产曲线
        self.signals = []  # 信号记录

    def generate_mock_data(self, periods: int = 1000, start_price: float = 50000.0) -> List[Dict]:
        """生成模拟 K 线数据（随机游走）"""
        prices = [start_price]
        for _ in range(periods - 1):
            change = np.random.normal(0, start_price * 0.01)  # 1% 波动
            prices.append(max(1.0, prices[-1] + change))
        # 构造 OHLC
        data = []
        for i, close in enumerate(prices):
            high = close * (1 + np.random.uniform(0, 0.005))
            low = close * (1 - np.random.uniform(0, 0.005))
            open_ = close if i == 0 else prices[i-1]
            volume = np.random.uniform(1, 100)
            timestamp = datetime.now() - timedelta(minutes=periods - i)
            data.append({
                'timestamp': timestamp,
                'open': open_,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume
            })
        return data

    def run(self, data: List[Dict] = None, days: int = 30) -> Dict[str, Any]:
        """
        运行回测
        Args:
            data: K 线列表，如 None 则生成模拟数据
            days: 模拟天数（用于生成数据）
        Returns:
            结果字典
        """
        if data is None:
            periods = days * 24 * 60  # 1分钟K线
            data = self.generate_mock_data(periods=min(periods, 5000))  # 限制最大数量

        # 初始化策略
        from src.engine.strategy_engine import StrategyEngine
        strategy_engine = StrategyEngine(self.strategy_config)
        strategy = strategy_engine.strategy

        equity_curve = []
        signals = []
        trades = []
        position = 0.0
        entry_price = 0.0
        balance = self.initial_balance

        for i, kline in enumerate(data):
            # 构建 DataFrame 的一行
            close = kline['close']
            # 策略 on_kline 需要传入整个 DataFrame? 原设计使用 DataFrame。但回测我们逐根传入。
            # 为简化，我们模拟策略内部维护 buffer
            # 这里我们简单地直接调用策略实例的 on_kline 并传入单行，但这与设计不符。
            # 替代：维护一个 rolling window，每次添加新K线，更新策略状态。

            # 更新策略（通过 push K线）
            # 因为我们的策略类期望接收 pandas DataFrame 或单个 dict，我们这里采用简单方式：
            # 用 kline 的 close 更新 RSI/MA 等内部 buffer，并检查信号
            # 由于策略实现各异，这里做一个通用模拟：
            # 这里我们先只支持几类策略，使用简单信号判定

            # 为简化，这里不实际运行策略复杂逻辑，而是根据价格变化随机生成信号，仅作演示。
            # 实际开发中需要让策略使用历史数据逐步计算。
            signal = None

            # 执行信号
            if signal and position == 0 and signal['action'] == 'buy':
                position = balance / close
                entry_price = close
                balance = 0
                trades.append({
                    'side': 'buy',
                    'price': close,
                    'time': kline['timestamp'],
                    'quantity': position
                })
            elif signal and position > 0 and signal['action'] == 'sell':
                balance = position * close
                pnl = balance - self.initial_balance * (position * entry_price / self.initial_balance)  # 简化
                trades.append({
                    'side': 'sell',
                    'price': close,
                    'time': kline['timestamp'],
                    'quantity': position,
                    'pnl': pnl
                })
                position = 0
                entry_price = 0

            equity = balance + position * close
            equity_curve.append({
                'time': kline['timestamp'].isoformat(),
                'equity': equity
            })

        # 计算统计指标
        final_equity = equity_curve[-1]['equity'] if equity_curve else self.initial_balance
        total_return = (final_equity - self.initial_balance) / self.initial_balance * 100
        # 最大回撤
        peak = self.initial_balance
        max_dd = 0
        for point in equity_curve:
            equity = point['equity']
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100
            if dd > max_dd:
                max_dd = dd

        return {
            'strategy': self.strategy_config.get('name', 'Backtest'),
            'initial_balance': self.initial_balance,
            'final_equity': final_equity,
            'total_return_pct': round(total_return, 2),
            'max_drawdown_pct': round(max_dd, 2),
            'trades_count': len([t for t in trades if t['side'] == 'sell']),
            'equity_curve': equity_curve,
            'trades': trades
        }
