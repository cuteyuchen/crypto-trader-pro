"""
单元测试：OrderExecutor 的本地执行逻辑
"""
import pytest
import asyncio
from src.engine.executor import OrderExecutor
from src.data.simulation_db import SimulationDB


class TestOrderExecutorLocal:
    """本地模拟执行器测试"""

    @pytest.mark.asyncio
    async def test_initialization_local(self, clean_temp_db, sim_config):
        """测试本地模式初始化"""
        db = SimulationDB(clean_temp_db)
        db.set_balance("USDT", sim_config["initial_balance"])

        executor = OrderExecutor("local", sim_config, simulation_db=db)
        await executor.initialize()

        assert executor.initialized is True
        assert executor.mode == "local"
        assert executor.simulation_db is not None

    @pytest.mark.asyncio
    async def test_buy_order_success(self, clean_temp_db, sim_config):
        """测试买入订单成功执行"""
        initial_balance = 10000.0
        db = SimulationDB(clean_temp_db)
        db.set_balance("USDT", initial_balance)

        executor = OrderExecutor("local", sim_config, simulation_db=db)
        await executor.initialize()

        # 执行买入
        order = {
            "symbol": "BTC/USDT",
            "side": "buy",
            "quantity": 0.1,
            "price": 50000.0,
            "type": "market",
            "strategy": "test_ma_cross"
        }

        result = await executor.execute_order(order)

        assert result['success'] is True
        assert result['filled_quantity'] == 0.1
        assert result['avg_price'] == 50000.0
        assert 'fee' in result
        assert result['fee'] > 0

        # 检查余额减少
        new_balance = db.get_balance("USDT")
        expected_balance = initial_balance - (50000 * 0.1) - result['fee']
        assert abs(new_balance - expected_balance) < 0.01

        # 检查持仓
        positions = db.get_open_positions("BTC/USDT")
        assert len(positions) == 1
        assert positions[0]['quantity'] == 0.1
        assert positions[0]['side'] == 'long'
        assert positions[0]['entry_price'] == 50000.0

    @pytest.mark.asyncio
    async def test_buy_order_insufficient_balance(self, clean_temp_db, sim_config):
        """测试余额不足的买入订单"""
        db = SimulationDB(clean_temp_db)
        db.set_balance("USDT", 100.0)  # 只有 100 USDT

        executor = OrderExecutor("local", sim_config, simulation_db=db)
        await executor.initialize()

        order = {
            "symbol": "BTC/USDT",
            "side": "buy",
            "quantity": 0.1,
            "price": 50000.0,
            "type": "market",
            "strategy": "test"
        }

        result = await executor.execute_order(order)

        assert result['success'] is False
        assert '余额不足' in result['error']

    @pytest.mark.asyncio
    async def test_sell_order_success(self, clean_temp_db, sim_config):
        """测试卖出订单成功执行（平仓）"""
        initial_balance = 0.0
        db = SimulationDB(clean_temp_db)
        db.set_balance("USDT", initial_balance)

        # 先开仓
        db.open_position("BTC/USDT", "long", 0.1, 50000.0)
        # 手动更新当前价格（影响盈亏计算）
        db.update_position_price("BTC/USDT", 51000.0)

        executor = OrderExecutor("local", sim_config, simulation_db=db)
        await executor.initialize()

        order = {
            "symbol": "BTC/USDT",
            "side": "sell",
            "quantity": 0.1,
            "price": 51000.0,
            "type": "market",
            "strategy": "test"
        }

        result = await executor.execute_order(order)

        assert result['success'] is True
        assert result['filled_quantity'] == 0.1
        assert result['avg_price'] == 51000.0
        assert 'pnl' in result
        # 盈利：0.1 * (51000 - 50000) = 100 美元
        expected_pnl = 0.1 * (51000 - 50000)
        assert abs(result['pnl'] - expected_pnl) < 0.01

        # 检查余额增加（包括卖出所得减去手续费）
        new_balance = db.get_balance("USDT")
        expected_balance = (51000 * 0.1) - result['fee'] + expected_pnl
        assert abs(new_balance - expected_balance) < 0.01

        # 检查持仓已清空
        positions = db.get_open_positions("BTC/USDT")
        assert len(positions) == 0

    @pytest.mark.asyncio
    async def test_sell_order_insufficient_position(self, clean_temp_db, sim_config):
        """测试持仓不足的卖出订单"""
        db = SimulationDB(clean_temp_db)
        db.set_balance("USDT", 10000.0)
        # 没有开仓

        executor = OrderExecutor("local", sim_config, simulation_db=db)
        await executor.initialize()

        order = {
            "symbol": "BTC/USDT",
            "side": "sell",
            "quantity": 0.1,
            "price": 50000.0,
            "type": "market",
            "strategy": "test"
        }

        result = await executor.execute_order(order)
        assert result['success'] is False
        assert '持仓不足' in result['error']

    @pytest.mark.asyncio
    async def test_partial_position_close(self, clean_temp_db, sim_config):
        """测试部分平仓"""
        db = SimulationDB(clean_temp_db)
        db.set_balance("USDT", 0.0)

        # 开仓 0.2 BTC
        db.open_position("BTC/USDT", "long", 0.2, 50000.0)
        db.update_position_price("BTC/USDT", 51000.0)

        executor = OrderExecutor("local", sim_config, simulation_db=db)
        await executor.initialize()

        # 卖出 0.1 BTC（部分平仓）
        order = {
            "symbol": "BTC/USDT",
            "side": "sell",
            "quantity": 0.1,
            "price": 51000.0,
            "type": "market",
            "strategy": "test"
        }

        result = await executor.execute_order(order)

        assert result['success'] is True
        assert result['filled_quantity'] == 0.1

        # 检查仍有 0.1 持仓
        positions = db.get_open_positions("BTC/USDT")
        assert len(positions) == 1
        assert positions[0]['quantity'] == 0.1

    @pytest.mark.asyncio
    async def test_fee_calculation(self, clean_temp_db, sim_config):
        """测试手续费计算（0.1%）"""
        db = SimulationDB(clean_temp_db)
        db.set_balance("USDT", 20000.0)

        executor = OrderExecutor("local", sim_config, simulation_db=db)
        await executor.initialize()

        # 买入 0.1 BTC @ 50000
        price = 50000.0
        quantity = 0.1
        order = {
            "symbol": "BTC/USDT",
            "side": "buy",
            "quantity": quantity,
            "price": price,
            "type": "market",
            "strategy": "test"
        }

        result = await executor.execute_order(order)

        expected_fee = price * quantity * 0.001
        assert abs(result['fee'] - expected_fee) < 0.01

    @pytest.mark.asyncio
    async def test_unknown_side(self, clean_temp_db, sim_config):
        """测试未知操作类型"""
        db = SimulationDB(clean_temp_db)
        db.set_balance("USDT", 10000.0)

        executor = OrderExecutor("local", sim_config, simulation_db=db)
        await executor.initialize()

        order = {
            "symbol": "BTC/USDT",
            "side": "unknown",
            "quantity": 0.1,
            "price": 50000.0,
            "type": "market",
            "strategy": "test"
        }

        result = await executor.execute_order(order)
        assert result['success'] is False
        assert '未知操作' in result['error']

    @pytest.mark.asyncio
    async def test_get_balance(self, clean_temp_db, sim_config):
        """测试获取余额"""
        db = SimulationDB(clean_temp_db)
        db.set_balance("USDT", 10000.0)

        executor = OrderExecutor("local", sim_config, simulation_db=db)
        await executor.initialize()

        balance = await executor.get_balance("USDT")
        assert balance == 10000.0

    @pytest.mark.asyncio
    async def test_get_positions(self, clean_temp_db, sim_config):
        """测试获取持仓"""
        db = SimulationDB(clean_temp_db)
        db.set_balance("USDT", 10000.0)
        db.open_position("BTC/USDT", "long", 0.1, 50000.0)
        db.update_position_price("BTC/USDT", 51000.0)

        executor = OrderExecutor("local", sim_config, simulation_db=db)
        await executor.initialize()

        positions = await executor.get_positions("BTC/USDT")
        assert len(positions) == 1
        assert positions[0]['quantity'] == 0.1
        assert positions[0]['side'] == 'long'

    @pytest.mark.asyncio
    async def test_get_recent_trades(self, clean_temp_db, sim_config):
        """测试获取最近交易记录"""
        db = SimulationDB(clean_temp_db)
        db.set_balance("USDT", 10000.0)

        # 执行几笔交易
        db.open_position("BTC/USDT", "long", 0.1, 50000.0)
        db.close_position("BTC/USDT", "long", 0.1, 51000.0, strategy="test_ma")

        executor = OrderExecutor("local", sim_config, simulation_db=db)
        await executor.initialize()

        trades = await executor.get_recent_trades("BTC/USDT", limit=10)
        assert len(trades) >= 1
        assert trades[0]['side'] in ['buy', 'sell']
        assert 'price' in trades[0]
