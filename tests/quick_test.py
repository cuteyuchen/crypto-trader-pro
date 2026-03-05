#!/usr/bin/env python3
"""
简单测试脚本：启动 bot 并运行 1 分钟
"""
import asyncio
import sys
import os

# 将项目根目录加入 sys.path，以便直接导入 src 下的模块
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.data.simulation_db import SimulationDB
from src.engine.strategy_engine import StrategyEngine
from src.engine.executor import OrderExecutor
from src.engine.risk_manager import RiskManager
from src.ws.binance_ws import BinanceWS

async def quick_test():
    print("=== 快速测试开始 ===\n")

    # 1. 测试数据库
    print("1. 初始化模拟数据库...")
    db = SimulationDB(":memory:")
    db.set_balance("USDT", 10000)
    print(f"   余额: ${db.get_balance('USDT'):.2f}")

    # 2. 测试策略引擎
    print("2. 测试策略引擎...")
    engine = StrategyEngine("config/strategies/ma_cross.json")
    print(f"   策略: {engine.strategy.name}")

    # 3. 测试执行器
    print("3. 测试执行器 (local 模式)...")
    executor = OrderExecutor("local", {}, simulation_db=db)
    await executor.initialize()
    result = await executor.execute_order({
        "symbol": "BTC/USDT",
        "side": "buy",
        "quantity": 0.01,
        "price": 50000,
        "type": "market"
    })
    print(f"   下单结果: {result['success']}, 余额剩余 ${db.get_balance('USDT'):.2f}, 持仓数: {len(db.get_open_positions('BTC/USDT'))}")

    # 4. 测试风控
    print("4. 测试风控...")
    risk = RiskManager({"max_position_size_pct": 0.5})
    allowed, reason = risk.check_order({
        "side": "buy",
        "quantity": 1.0,
        "price": 50000
    }, 10000)
    print(f"   大额订单检查: {allowed}, {reason}")

    # 5. 测试 WebSocket (只连接 10 秒)
    print("5. 测试 WebSocket 连接 (10秒)...")
    ws = BinanceWS("btcusdt")
    ws_task = asyncio.create_task(ws.start())
    await asyncio.sleep(10)
    ws.stop()
    ws_task.cancel()
    print("   WebSocket 测试完成")

    print("\n=== 所有基础组件测试通过！ ===")

if __name__ == "__main__":
    asyncio.run(quick_test())
