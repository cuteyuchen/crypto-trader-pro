"""
BacktestMetrics 使用示例

展示如何调用 BacktestMetrics 计算回测指标
"""

from src.backtest.metrics import BacktestMetrics
from datetime import datetime, timedelta
import random

def generate_sample_equity_curve():
    """生成示例权益曲线"""
    start_price = 10000.0
    equity = [start_price]
    # 使用固定的起始日期，避免时区问题
    base_date = datetime(2025, 1, 1)

    # 生成30天的数据，每天一个点
    for i in range(1, 30):
        # 随机波动，每天约0.5%波动
        change_pct = random.uniform(-0.01, 0.01)
        new_equity = equity[-1] * (1 + change_pct)
        equity.append(new_equity)

    return [{'time': (base_date + timedelta(days=i)).isoformat(), 'equity': e} for i, e in enumerate(equity)]

def generate_sample_trades():
    """生成示例交易列表"""
    trades = []
    base_time = datetime(2025, 1, 2)  # 从 equity_curve 开始后的几天

    for i in range(5):
        # 买入
        buy_time = base_time + timedelta(days=i * 6)  # 每6天买入一次
        buy_price = 100 + random.uniform(-5, 5)
        quantity = 1.0

        # 卖出（假设在买入后1-3天卖出）
        sell_time = base_time + timedelta(days=i * 6 + random.randint(1, 3))
        sell_price = buy_price * random.uniform(0.95, 1.10)
        pnl = (sell_price - buy_price) * quantity

        trades.append({
            'side': 'buy',
            'price': buy_price,
            'time': buy_time,  # 直接使用 datetime 对象，避免字符串解析问题
            'quantity': quantity
        })
        trades.append({
            'side': 'sell',
            'price': sell_price,
            'time': sell_time,
            'quantity': quantity,
            'pnl': pnl
        })

    print(f"[DEBUG] 生成的 trades: {len(trades)} 笔")
    for idx, t in enumerate(trades):
        time_val = t.get('time')
        print(f"  [{idx}] side={t['side']}, time={time_val}, type={type(time_val)}, repr={repr(time_val)}")

    return trades

def example_basic_usage():
    """基本用法示例"""
    equity_curve = generate_sample_equity_curve()
    trades = generate_sample_trades()

    # 计算所有指标
    metrics = BacktestMetrics.calculate(equity_curve, trades)

    print("=== 回测指标报告 ===")
    print(f"总收益率: {metrics['total_return_pct']}%")
    print(f"年化收益率: {metrics['annual_return_pct']}%")
    print(f"最大回撤: {metrics['max_drawdown_pct']}%")
    print(f"Sharpe 比率: {metrics['sharpe_ratio']}")
    print(f"胜率: {metrics['win_rate_pct']}%")
    print(f"盈亏比: {metrics['profit_loss_ratio']}")
    print(f"交易频率: {metrics['trades_per_day']} 笔/天")
    print(f"平均持仓时间: {metrics['avg_holding_days']} 天")
    print(f"\n盈利分布: {metrics['profit_distribution']}")
    print(f"亏损分布: {metrics['loss_distribution']}")

    return metrics

def example_with_api_response():
    """模拟与 /api/backtest 接口整合的示例"""
    equity_curve = generate_sample_equity_curve()
    trades = generate_sample_trades()

    # 模拟 engine.run() 的结果基础信息
    result = {
        'strategy': 'ma_cross',
        'initial_balance': 10000.0,
        'final_balance': equity_curve[-1]['equity'],
        'equity_curve': equity_curve,
        'trades': trades
    }

    # 添加详细指标
    metrics = BacktestMetrics.calculate(equity_curve, trades)
    result['metrics'] = metrics

    import json
    print("\n=== API 响应示例 ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    return result

if __name__ == "__main__":
    print("示例 1: 基本用法")
    example_basic_usage()

    print("\n" + "="*50 + "\n")

    print("示例 2: API 响应整合")
    example_with_api_response()
