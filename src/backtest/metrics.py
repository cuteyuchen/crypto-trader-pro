"""
回测指标计算模块
"""
import logging
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class BacktestMetrics:
    """回测指标计算器"""

    @staticmethod
    def calculate(equity_curve: List[Dict], trades: List[Dict]) -> Dict[str, Any]:
        """
        计算回测指标

        Args:
            equity_curve: 资产曲线，每个元素包含 {'time': timestamp, 'equity': float}
            trades: 交易列表，每个元素包含交易信息（至少需要 side, price, time, quantity, pnl等字段）

        Returns:
            包含所有指标的字典
        """
        metrics = {}

        if not equity_curve:
            logger.warning("equity_curve 为空，返回默认指标")
            return BacktestMetrics._get_default_metrics()

        # 提取权益值序列
        equity_values = [point['equity'] for point in equity_curve]
        # 处理时间格式
        times = []
        for point in equity_curve:
            t = point['time']
            if isinstance(t, str):
                # 尝试解析 ISO 格式 (兼容 Python 3.6)
                try:
                    # 移除时区标记，使用 strptime 解析
                    t_clean = t.replace('Z', '').replace('+00:00', '')
                    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
                        try:
                            times.append(datetime.strptime(t_clean, fmt))
                            break
                        except ValueError:
                            continue
                    else:
                        # 如果都不匹配，尝试 timestamp
                        times.append(datetime.fromtimestamp(float(t)))
                except (ValueError, TypeError):
                    times.append(datetime.now())
            elif isinstance(t, datetime):
                times.append(t)
            elif isinstance(t, (int, float)):
                times.append(datetime.fromtimestamp(t))
            else:
                times.append(datetime.now())

        # 1. 总收益率
        initial_equity = equity_values[0]
        final_equity = equity_values[-1]
        total_return = (final_equity - initial_equity) / initial_equity * 100
        metrics['total_return_pct'] = round(total_return, 2)
        metrics['initial_balance'] = round(initial_equity, 2)
        metrics['final_balance'] = round(final_equity, 2)

        # 2. 年化收益率
        # 计算回测时长（年）
        if len(times) >= 2:
            duration_days = (times[-1] - times[0]).days + (
                        (times[-1] - times[0]).seconds / 86400)  # 加上秒数转换
            if duration_days > 0:
                annual_return = ((1 + total_return / 100) ** (365 / duration_days) - 1) * 100
                metrics['annual_return_pct'] = round(annual_return, 2)
            else:
                metrics['annual_return_pct'] = 0.0
        else:
            metrics['annual_return_pct'] = 0.0

        # 3. 最大回撤（peak-to-trough）
        max_drawdown, max_dd_duration = BacktestMetrics._calculate_max_drawdown(equity_values, times)
        metrics['max_drawdown_pct'] = round(max_drawdown * 100, 2) if max_drawdown is not None else 0.0
        if max_dd_duration:
            metrics['max_drawdown_days'] = round(max_dd_duration, 1)

        # 4. Sharpe 比率（日频数据，无风险利率=0%）
        # 需要转换为日频收益率
        if len(equity_values) >= 2:
            # 计算日收益率
            daily_returns = BacktestMetrics._compute_daily_returns(equity_values, times)
            if len(daily_returns) > 0:
                # 假设无风险利率为0
                excess_returns = np.array(daily_returns)
                if np.std(excess_returns) > 0:
                    sharpe = np.mean(excess_returns) / np.std(excess_returns)
                    # 年化 Sharpe: 乘以 sqrt(252) 假设日频
                    sharpe_annualized = sharpe * np.sqrt(252)
                    metrics['sharpe_ratio'] = round(sharpe_annualized, 3)
                else:
                    metrics['sharpe_ratio'] = 0.0
            else:
                metrics['sharpe_ratio'] = 0.0
        else:
            metrics['sharpe_ratio'] = 0.0

        # 5. 胜率
        closed_trades = [t for t in trades if t.get('side') == 'sell']  # 假设卖出为平仓
        if closed_trades:
            winning_trades = [t for t in closed_trades if t.get('pnl', 0) > 0]
            win_rate = len(winning_trades) / len(closed_trades) * 100
            metrics['win_rate_pct'] = round(win_rate, 2)
            metrics['total_trades'] = len(closed_trades)
        else:
            metrics['win_rate_pct'] = 0.0
            metrics['total_trades'] = 0

        # 6. 盈亏比
        if closed_trades:
            total_profit = sum(t.get('pnl', 0) for t in closed_trades if t.get('pnl', 0) > 0)
            total_loss = abs(sum(t.get('pnl', 0) for t in closed_trades if t.get('pnl', 0) < 0))
            if total_loss > 0:
                profit_loss_ratio = total_profit / total_loss
            else:
                profit_loss_ratio = float('inf') if total_profit > 0 else 0.0
            metrics['profit_loss_ratio'] = round(profit_loss_ratio, 3) if profit_loss_ratio != float('inf') else None
        else:
            metrics['profit_loss_ratio'] = 0.0

        # 7. 盈利/亏损分布
        if closed_trades:
            profits = [t.get('pnl', 0) for t in closed_trades if t.get('pnl', 0) > 0]
            losses = [abs(t.get('pnl', 0)) for t in closed_trades if t.get('pnl', 0) < 0]

            metrics['profit_distribution'] = {
                'count': len(profits),
                'total': round(sum(profits), 2),
                'average': round(np.mean(profits), 2) if profits else 0.0,
                'max': round(max(profits), 2) if profits else 0.0,
                'median': round(np.median(profits), 2) if profits else 0.0
            }
            metrics['loss_distribution'] = {
                'count': len(losses),
                'total': round(sum(losses), 2),
                'average': round(np.mean(losses), 2) if losses else 0.0,
                'max': round(max(losses), 2) if losses else 0.0,
                'median': round(np.median(losses), 2) if losses else 0.0
            }
        else:
            metrics['profit_distribution'] = {'count': 0, 'total': 0.0, 'average': 0.0, 'max': 0.0, 'median': 0.0}
            metrics['loss_distribution'] = {'count': 0, 'total': 0.0, 'average': 0.0, 'max': 0.0, 'median': 0.0}

        # 8. 交易频率（平均每天交易次数）
        if closed_trades:
            if duration_days >= 1:
                trade_frequency = len(closed_trades) / duration_days
                metrics['trades_per_day'] = round(trade_frequency, 2)
            else:
                # 如果回测时间不足一天，计算实际的小时数并折算
                if times and len(times) >= 2:
                    total_hours = (times[-1] - times[0]).total_seconds() / 3600
                    if total_hours > 0:
                        trades_per_hour = len(closed_trades) / total_hours
                        metrics['trades_per_day'] = round(trades_per_hour * 24, 2)
                    else:
                        metrics['trades_per_day'] = 0.0
                else:
                    metrics['trades_per_day'] = 0.0
        else:
            metrics['trades_per_day'] = 0.0

        # 9. 平均持仓时间
        # 需要完整的买卖交易配对来计算
        if trades:
            avg_holding_days = BacktestMetrics._calculate_avg_holding_time(trades)
            metrics['avg_holding_days'] = round(avg_holding_days, 2) if avg_holding_days else None
        else:
            metrics['avg_holding_days'] = None

        # 10. 夏普比率（使用简单方法，基于 equity curve 的日收益率）
        # 已在上面计算，这里添加计算细节
        if 'sharpe_ratio' in metrics:
            metrics['sharpe_calculation'] = {
                'method': 'annualized',
                'period': 'daily',
                'risk_free_rate': 0.0
            }

        # 附加信息
        metrics['backtest_duration_days'] = round(duration_days, 1) if duration_days > 0 else 0.0

        return metrics

    @staticmethod
    def _calculate_max_drawdown(equity_values: List[float], times: List[datetime]) -> (float, Optional[float]):
        """
        计算最大回撤及回撤持续时间

        Returns:
            (max_drawdown, max_dd_duration_days)
        """
        if len(equity_values) < 2:
            return None, None

        peak = equity_values[0]
        max_dd = 0.0
        max_dd_start_idx = 0
        max_dd_end_idx = 0
        current_peak_idx = 0

        for i, equity in enumerate(equity_values):
            if equity > peak:
                peak = equity
                current_peak_idx = i
            else:
                dd = (peak - equity) / peak
                if dd > max_dd:
                    max_dd = dd
                    max_dd_start_idx = current_peak_idx
                    max_dd_end_idx = i

        # 计算最大回撤持续时间（天）
        if max_dd > 0 and times and max_dd_start_idx < len(times) and max_dd_end_idx < len(times):
            duration = (times[max_dd_end_idx] - times[max_dd_start_idx]).days + (
                        (times[max_dd_end_idx] - times[max_dd_start_idx]).seconds / 86400)
        else:
            duration = None

        return max_dd, duration

    @staticmethod
    def _compute_daily_returns(equity_values: List[float], times: List[datetime]) -> List[float]:
        """将权益曲线转换为日频收益率"""
        if len(equity_values) < 2:
            return []

        # 按日期聚合（取每日最后一个权益值）
        daily_equity = {}
        for i, (equity, time) in enumerate(zip(equity_values, times)):
            date_key = time.date()
            daily_equity[date_key] = equity  # 后面的会覆盖前面的，即取当日最后的值

        # 按日期排序
        sorted_dates = sorted(daily_equity.keys())
        if len(sorted_dates) < 2:
            return []

        # 计算日收益率
        returns = []
        prev_equity = daily_equity[sorted_dates[0]]
        for date in sorted_dates[1:]:
            curr_equity = daily_equity[date]
            if prev_equity > 0:
                ret = (curr_equity - prev_equity) / prev_equity
                returns.append(ret)
            prev_equity = curr_equity

        return returns

    @staticmethod
    def _calculate_avg_holding_time(trades: List[Dict]) -> Optional[float]:
        """
        计算平均持仓时间（天）

        假设 trades 是先 buy 后 sell 交替出现
        """
        if len(trades) < 2:
            return None

        # 将时间统一转换为 datetime 对象
        def to_datetime(val):
            if isinstance(val, datetime):
                return val
            if isinstance(val, (int, float)):
                return datetime.fromtimestamp(val)
            if isinstance(val, str):
                # 尝试多种格式
                val_clean = val.replace('Z', '').split('+')[0].split('.')[0]
                for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
                    try:
                        return datetime.strptime(val_clean, fmt)
                    except ValueError:
                        continue
            return None

        # 为每个交易添加 datetime 字段并排序
        enriched_trades = []
        for t in trades:
            dt = to_datetime(t.get('time'))
            if dt:
                enriched_trades.append({**t, '_dt': dt})

        if len(enriched_trades) < 2:
            return None

        # 按时间排序
        sorted_trades = sorted(enriched_trades, key=lambda x: x['_dt'])

        holding_periods = []
        buy_time = None

        for trade in sorted_trades:
            side = trade.get('side', '').lower()

            if side == 'buy':
                buy_time = trade['_dt']
            elif side == 'sell' and buy_time is not None:
                # 计算持仓时间（天）
                holding_days = (trade['_dt'] - buy_time).total_seconds() / 86400
                holding_periods.append(holding_days)
                buy_time = None  # 重置，等待下一个买入

        if holding_periods:
            avg = sum(holding_periods) / len(holding_periods)
            return avg
        else:
            return None

    @staticmethod
    def _get_default_metrics() -> Dict[str, Any]:
        """返回默认指标（当数据不足时）"""
        return {
            'total_return_pct': 0.0,
            'annual_return_pct': 0.0,
            'max_drawdown_pct': 0.0,
            'sharpe_ratio': 0.0,
            'win_rate_pct': 0.0,
            'profit_loss_ratio': 0.0,
            'profit_distribution': {'count': 0, 'total': 0.0, 'average': 0.0, 'max': 0.0, 'median': 0.0},
            'loss_distribution': {'count': 0, 'total': 0.0, 'average': 0.0, 'max': 0.0, 'median': 0.0},
            'trades_per_day': 0.0,
            'avg_holding_days': None,
            'total_trades': 0,
            'initial_balance': 0.0,
            'final_balance': 0.0,
            'backtest_duration_days': 0.0
        }
