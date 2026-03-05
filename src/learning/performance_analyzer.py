"""
策略表现分析器 - 评估策略近期表现
"""
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List
import numpy as np

logger = logging.getLogger(__name__)


class PerformanceAnalyzer:
    """策略表现分析器"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def get_strategy_performance(self, strategy: str, days: int = 7) -> Dict[str, Any]:
        """
        获取指定策略的近期表现

        Args:
            strategy: 策略名称
            days: 考察最近 N 天

        Returns:
            包含胜率、平均盈亏、总交易数、总盈亏等指标
        """
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            query = """
                SELECT * FROM trades
                WHERE strategy = ? AND executed_at >= ?
                ORDER BY executed_at ASC
            """
            rows = conn.execute(query, (strategy, cutoff)).fetchall()
            trades = [dict(row) for row in rows]

            if not trades:
                return {
                    "strategy": strategy,
                    "period_days": days,
                    "total_trades": 0,
                    "win_rate": 0.0,
                    "avg_pnl": 0.0,
                    "total_pnl": 0.0,
                    "sharpe": 0.0,
                    "max_drawdown": 0.0
                }

            total_trades = len(trades)
            wins = [t for t in trades if t['pnl'] > 0]
            losses = [t for t in trades if t['pnl'] < 0]
            win_rate = len(wins) / total_trades if total_trades else 0

            pnls = [t['pnl'] for t in trades]
            avg_pnl = np.mean(pnls) if pnls else 0
            total_pnl = np.sum(pnls)

            # 夏普比率（简化，日频）
            if len(pnls) > 1:
                volatility = np.std(pnls)
                sharpe = avg_pnl / volatility if volatility > 0 else 0
            else:
                sharpe = 0

            # 最大回撤
            cumulative = np.cumsum(pnls)
            max_drawdown = 0
            peak = cumulative[0]
            for value in cumulative:
                if value > peak:
                    peak = value
                drawdown = peak - value
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

            return {
                "strategy": strategy,
                "period_days": days,
                "total_trades": total_trades,
                "win_rate": round(win_rate * 100, 1),
                "avg_pnl": round(avg_pnl, 2),
                "total_pnl": round(total_pnl, 2),
                "sharpe": round(sharpe, 2),
                "max_drawdown": round(max_drawdown, 2)
            }
        finally:
            conn.close()

    def compare_strategies(self, strategies: List[str], days: int = 7) -> List[Dict[str, Any]]:
        """比较多个策略表现"""
        results = []
        for s in strategies:
            perf = self.get_strategy_performance(s, days)
            results.append(perf)
        return sorted(results, key=lambda x: x['total_pnl'], reverse=True)


class ParameterOptimizer:
    """参数优化器（简化版）"""

    def __init__(self, analyzer: PerformanceAnalyzer):
        self.analyzer = analyzer

    def suggest_improvements(self, strategy: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据近期表现给出参数改进建议

        规则：
        - 如果胜率 < 40% 且总盈亏为负：建议调整信号阈值（RSI: 扩大超买超卖范围）
        - 如果回撤 > 初始资金的 20%：建议收紧止损
        - 如果交易频率太低：缩小周期
        """
        perf = self.analyzer.get_strategy_performance(strategy)
        suggestions = []
        new_config = config.copy()

        strategy_type = config.get("type") or strategy

        if strategy_type == "rsi":
            oversold = config.get("oversold", 30)
            overbought = config.get("oversold", 70)
            if perf["win_rate"] < 40:
                # 扩大范围，信号更少但更可靠
                new_config["oversold"] = max(20, oversold - 5)
                new_config["overbought"] = min(80, overbought + 5)
                suggestions.append(f"RSI 胜率偏低，扩大超买超卖阈值至 {new_config['oversold']}/{new_config['overbought']}")
            if perf["avg_pnl"] < 0:
                suggestions.append("RSI 平均盈亏为负，建议手动测试或切换策略")

        elif strategy_type == "ma_cross":
            fast = config["params"]["fast_period"]
            slow = config["params"]["slow_period"]
            if perf["total_trades"] < 10:
                # 交易频率低，缩小周期
                new_config["params"]["fast_period"] = max(3, fast - 1)
                new_config["params"]["slow_period"] = max(5, slow - 2)
                suggestions.append(f"交易频率低，缩小 MA 周期至 {new_config['params']['fast_period']}/{new_config['params']['slow_period']}")
            if perf["win_rate"] < 40:
                suggestions.append("MA 交叉胜率偏低，考虑切换策略")

        elif strategy_type == "bollinger":
            period = config.get("bb_period", 20)
            std = config.get("bb_std", 2.0)
            if perf["max_drawdown"] > 200:
                new_config["bb_std"] = min(2.5, std + 0.2)
                suggestions.append(f"回撤较大，增加布林带宽度至 {new_config['bb_std']}")
            if perf["total_trades"] < 5:
                new_config["bb_period"] = max(10, period - 2)
                suggestions.append(f"交易频率低，缩短布林带周期至 {new_config['bb_period']}")

        elif strategy_type == "macd":
            fast = config.get("fast_period", 12)
            slow = config.get("slow_period", 26)
            signal = config.get("signal_period", 9)
            if perf["win_rate"] < 40:
                # 平滑参数：慢一点
                new_config["signal_period"] = signal + 1
                suggestions.append(f"MACD 胜率偏低，增加信号线平滑至 {new_config['signal_period']}")

        if not suggestions:
            suggestions.append("近期表现尚可，无需调整")

        return {
            "strategy": strategy,
            "performance": perf,
            "suggestions": suggestions,
            "new_config": new_config
        }


# 测试示例
if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)

    analyzer = PerformanceAnalyzer("data/simulation.db")
    print("RSI 表现:", analyzer.get_strategy_performance("RSI_14_70_30"))
    print("MA 表现:", analyzer.get_strategy_performance("MA5_MA20_Cross"))
