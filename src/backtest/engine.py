"""
简易回测引擎
"""
import logging
import numpy as np
import pandas as pd
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

    def run(self, data: List[Dict] = None, klines_df: pd.DataFrame = None, days: int = 30) -> Dict[str, Any]:
        """
        运行回测
        Args:
            data: K 线列表（List[Dict]），如 None 则使用 klines_df 或生成模拟数据
            klines_df: pandas DataFrame 格式的 K 线数据（索引为 timestamp，列包含 open/high/low/close/volume）
            days: 模拟天数（用于生成数据）
        Returns:
            结果字典
        """
        # 决定数据源优先级: data > klines_df > 模拟数据
        if data is not None:
            # 使用传入的 List[Dict] 数据
            klines = data
        elif klines_df is not None:
            # 将 DataFrame 转换为 List[Dict]
            klines_df_reset = klines_df.reset_index()
            klines = klines_df_reset.to_dict('records')
            # 确保 timestamp 列是 datetime 对象
            for k in klines:
                if isinstance(k['timestamp'], pd.Timestamp):
                    k['timestamp'] = k['timestamp'].to_pydatetime()
        else:
            # 生成模拟数据
            periods = days * 24 * 60  # 1分钟K线
            klines = self.generate_mock_data(periods=min(periods, 5000))  # 限制最大数量

        # 初始化策略
        from src.engine.strategy_engine import StrategyEngine
        strategy_engine = StrategyEngine(self.strategy_config)
        strategy = strategy_engine.strategy

        # 初始化策略
        from src.engine.strategy_engine import StrategyEngine, KLineCache
        strategy_engine = StrategyEngine(self.strategy_config)
        strategy = strategy_engine.strategy
        
        # 重置策略状态（如果支持）
        if hasattr(strategy, 'reset'):
            strategy.reset()
        
        equity_curve = []
        signals = []
        trades = []
        position = 0.0
        entry_price = 0.0
        balance = self.initial_balance
        
        # 判断策略类型以决定调用方式
        # 1. RSI, MACD 等策略维护内部 buffer，逐条传入
        # 2. MA, Bollinger 等使用外部 DataFrame，需要传入完整 DataFrame
        strategy_type = self.strategy_config.get('type')
        if not strategy_type and 'rsi_period' in self.strategy_config:
            strategy_type = 'rsi'
        elif not strategy_type and 'fast_period' in self.strategy_config and 'bb_period' not in self.strategy_config:
            # MA 交叉
            strategy_type = 'ma_cross'
        
        if strategy_type in ['rsi', 'macd']:
            # 逐条调用，策略内部维护 buffer
            for i, kline in enumerate(klines):
                signal = strategy.on_kline(kline)
                
                if signal:
                    signals.append({
                        'time': kline['timestamp'].isoformat(),
                        'action': signal['action'],
                        'reason': signal.get('reason', '')
                    })
                
                # 执行信号（简化版交易逻辑）
                close = kline['close']
                if signal and position == 0 and signal['action'] == 'buy':
                    position = balance * self.strategy_config.get('position_size', 1.0) / close
                    entry_price = close
                    balance -= balance * self.strategy_config.get('position_size', 1.0)
                    trades.append({
                        'side': 'buy',
                        'price': close,
                        'time': kline['timestamp'],
                        'quantity': position
                    })
                elif signal and position > 0 and signal['action'] == 'sell':
                    balance += position * close
                    trades.append({
                        'side': 'sell',
                        'price': close,
                        'time': kline['timestamp'],
                        'quantity': position
                    })
                    position = 0
                    entry_price = 0

                equity = balance + position * close
                equity_curve.append({
                    'time': kline['timestamp'].isoformat(),
                    'equity': equity
                })
        else:
            # MA, Bollinger 等策略：使用 KLineCache，传入 DataFrame
            kline_cache = KLineCache(maxlen=1000)
            
            for i, kline in enumerate(klines):
                # 添加到缓存
                kline_cache.add_kline(strategy_engine.config["symbol"], {
                    "timestamp": kline['timestamp'],
                    "open": kline['open'],
                    "high": kline['high'],
                    "low": kline['low'],
                    "close": kline['close'],
                    "volume": kline['volume']
                })
                
                # 获取 DataFrame 并调用策略
                df = kline_cache.get_dataframe(strategy_engine.config["symbol"], 1000)
                signal = strategy.on_kline(df)
                
                if signal:
                    signals.append({
                        'time': kline['timestamp'].isoformat(),
                        'action': signal['action'],
                        'reason': signal.get('reason', '')
                    })
                
                # 执行信号
                close = kline['close']
                if signal and position == 0 and signal['action'] == 'buy':
                    position = balance * self.strategy_config.get('position_size', 1.0) / close
                    entry_price = close
                    balance -= balance * self.strategy_config.get('position_size', 1.0)
                    trades.append({
                        'side': 'buy',
                        'price': close,
                        'time': kline['timestamp'],
                        'quantity': position
                    })
                elif signal and position > 0 and signal['action'] == 'sell':
                    balance += position * close
                    trades.append({
                        'side': 'sell',
                        'price': close,
                        'time': kline['timestamp'],
                        'quantity': position
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
        total_pnl = final_equity - self.initial_balance
        total_return = total_pnl / self.initial_balance * 100
        
        # 计算最大回撤
        peak = self.initial_balance
        max_drawdown = 0
        for point in equity_curve:
            equity = point['equity']
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak * 100
            if dd > max_drawdown:
                max_drawdown = dd
        
        # 计算交易统计
        sell_trades = [t for t in trades if t['side'] == 'sell']
        total_trades = len(sell_trades)
        
        # 计算胜率（基于卖出的盈亏）
        winning_trades = 0
        for trade in sell_trades:
            # 计算该笔交易的盈亏
            buy_trade = next((t for t in trades if t['side'] == 'buy' and t['time'] < trade['time']), None)
            if buy_trade:
                trade_pnl = trade['quantity'] * trade['price'] - buy_trade['quantity'] * buy_trade['price']
                if trade_pnl > 0:
                    winning_trades += 1
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        return {
            'strategy': self.strategy_config.get('name', 'Backtest'),
            'initial_balance': self.initial_balance,
            'final_balance': final_equity,
            'total_pnl': round(total_pnl, 2),
            'total_return_pct': round(total_return, 2),
            'max_drawdown': round(max_drawdown, 2),
            'max_drawdown_pct': round(max_drawdown, 2),
            'total_trades': total_trades,
            'win_rate': round(win_rate, 2),
            'equity_curve': equity_curve,
            'trades': trades
        }
