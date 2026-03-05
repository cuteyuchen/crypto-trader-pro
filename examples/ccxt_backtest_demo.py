"""
CCXT 历史数据回测引擎使用示例

演示如何：
1. 获取真实历史数据
2. 运行回测
3. 查看结果
"""
import argparse
from datetime import datetime, timedelta
import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.backtest.ccxt_backtest import CCXTBacktestEngine
from src.backtest.engine import BacktestEngine


def run_backtest_with_real_data():
    """
    使用真实历史数据运行回测的完整流程
    """
    # 1. 创建 CCXT 数据引擎
    data_engine = CCXTBacktestEngine(cache_dir="data/historical")
    
    # 2. 定义回测参数
    exchange = "binance"
    symbol = "BTC/USDT"
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)  # 回测最近30天
    
    # 3. 获取历史数据（自动使用缓存）
    print(f"正在获取 {exchange} {symbol} 的历史数据...")
    df = data_engine.fetch_historical_data(
        exchange=exchange,
        symbol=symbol,
        start_time=start_date,
        end_time=end_date,
        timeframe="1h",  # 1小时K线
        use_cache=True
    )
    
    if df.empty:
        print("未获取到数据，请检查网络连接或参数")
        return
    
    print(f"获取到 {len(df)} 条K线数据")
    print(f"时间范围: {df['timestamp'].iloc[0]} 到 {df['timestamp'].iloc[-1]}")
    print("\n前5行数据:")
    print(df.head())
    
    # 4. 配置策略
    strategy_config = {
        "name": "MA_Cross_RealData",
        "symbol": symbol,
        "timeframe": "1h",
        "type": "ma_cross",
        "params": {
            "fast_period": 10,
            "slow_period": 30
        },
        "position_size": 0.2  # 使用20%仓位
    }
    
    # 5. 创建回测引擎
    backtest_engine = BacktestEngine(
        strategy_config=strategy_config,
        initial_balance=10000.0
    )
    
    print("\n开始回测...")
    
    # 6. 运行回测（传入真实数据）
    result = backtest_engine.run(klines_df=df)
    
    # 7. 输出回测结果
    print("\n" + "="*60)
    print("回测结果")
    print("="*60)
    print(f"策略名称: {result['strategy']}")
    print(f"初始资金: ${result['initial_balance']:,.2f}")
    print(f"最终资金: ${result['final_balance']:,.2f}")
    print(f"总盈亏: ${result['total_pnl']:,.2f} ({result['total_return_pct']:.2f}%)")
    print(f"最大回撤: {result['max_drawdown_pct']:.2f}%")
    print(f"总交易次数: {result['total_trades']}")
    print(f"胜率: {result['win_rate']:.2f}%")
    
    # 8. 保存结果
    import json
    result_file = Path("data/backtest_result.json")
    result_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 简化保存，只保存部分信息
    summary = {
        "strategy": result['strategy'],
        "exchange": exchange,
        "symbol": symbol,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "initial_balance": result['initial_balance'],
        "final_balance": result['final_balance'],
        "total_pnl": result['total_pnl'],
        "total_return_pct": result['total_return_pct'],
        "max_drawdown_pct": result['max_drawdown_pct'],
        "total_trades": result['total_trades'],
        "win_rate": result['win_rate']
    }
    
    with open(result_file, 'w') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n结果已保存到: {result_file}")
    
    # 9. 清理资源
    data_engine.close()


if __name__ == "__main__":
    run_backtest_with_real_data()
