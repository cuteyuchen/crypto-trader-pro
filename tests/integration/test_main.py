"""
集成测试：TradingBot 启动流程
"""
import pytest
import asyncio
import os
import sys
from unittest.mock import Mock, patch, AsyncMock
from src.main import TradingBot


class TestTradingBotStartup:
    """TradingBot 启动流程测试"""

    def test_load_config_local_mode(self, tmp_path):
        """测试本地模式配置加载"""
        # 创建临时配置文件
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # 创建 modes.json
        modes = {
            "mode": "local",
            "dashboard_enabled": True,
            "notifications_enabled": False,
            "strategy": "ma_cross"
        }
        (config_dir / "modes.json").write_text(json.dumps(modes))

        # 创建 strategies/ma_cross.json
        strategies_dir = config_dir / "strategies"
        strategies_dir.mkdir()
        strategy = {
            "name": "Test_MA",
            "symbol": "BTC/USDT",
            "params": {"fast_period": 5, "slow_period": 20}
        }
        (strategies_dir / "ma_cross.json").write_text(json.dumps(strategy))

        # 创建 risk.json
        risk = {"max_trades_per_day": 100}
        (config_dir / "risk.json").write_text(json.dumps(risk))

        # 创建 simulation/local.json
        sim_dir = config_dir / "simulation"
        sim_dir.mkdir()
        sim = {"initial_balance": 10000}
        (sim_dir / "local.json").write_text(json.dumps(sim))

        # 切换到临时目录
        original_dir = os.getcwd()
        os.chdir(tmp_path)

        try:
            bot = TradingBot()
            assert bot.mode_config['mode'] == 'local'
            assert bot.strategy_config['name'] == 'Test_MA'
            assert bot.risk_config['max_trades_per_day'] == 100
            assert bot.sim_config['initial_balance'] == 10000
        finally:
            os.chdir(original_dir)

    def test_init_components_local(self, tmp_path):
        """测试本地模式下组件初始化"""
        # 准备配置
        self._prepare_config(tmp_path)

        original_dir = os.getcwd()
        os.chdir(tmp_path)

        try:
            bot = TradingBot()
            bot.init_components()

            # 检查数据库
            assert bot.db is not None
            assert bot.db.db_path.endswith('simulation.db')

            # 检查策略引擎
            assert bot.strategy_engine is not None
            assert bot.strategy_engine.strategy is not None

            # 检查执行器
            assert bot.executor is not None
            assert bot.executor.mode == "local"
            assert bot.executor.simulation_db is not None

            # 检查风控
            assert bot.risk_manager is not None
            assert hasattr(bot.risk_manager, 'initial_balance')

            # Dashboard（如果启用）
            if bot.mode_config.get('dashboard_enabled', True):
                assert bot.dashboard is not None

            # 通知管理器
            assert bot.notifier is not None

        finally:
            os.chdir(original_dir)

    def _prepare_config(self, tmp_path):
        """准备配置文件"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        modes = {
            "mode": "local",
            "dashboard_enabled": True,
            "notifications_enabled": False,
            "strategy": "ma_cross"
        }
        (config_dir / "modes.json").write_text(json.dumps(modes))

        strategies_dir = config_dir / "strategies"
        strategies_dir.mkdir()
        strategy = {
            "name": "Test_MA",
            "symbol": "BTC/USDT",
            "params": {"fast_period": 5, "slow_period": 20}
        }
        (strategies_dir / "ma_cross.json").write_text(json.dumps(strategy))

        risk = {"max_trades_per_day": 100}
        (config_dir / "risk.json").write_text(json.dumps(risk))

        sim_dir = config_dir / "simulation"
        sim_dir.mkdir()
        sim = {"initial_balance": 10000}
        (sim_dir / "local.json").write_text(json.dumps(sim))

    @pytest.mark.asyncio
    async def test_executor_initialization_local(self, tmp_path, clean_temp_db):
        """测试执行器初始化（本地模式）"""
        import json
        from src.engine.executor import OrderExecutor

        config = {"mode": "local", "initial_balance": 10000}
        from src.data.simulation_db import SimulationDB
        db = SimulationDB(clean_temp_db)
        db.set_balance("USDT", 10000)

        executor = OrderExecutor("local", config, simulation_db=db)
        await executor.initialize()

        assert executor.initialized
        assert executor.simulation_db is not None
        assert executor.mode == "local"

    @pytest.mark.asyncio
    async def test_end_to_end_buy_flow(self, tmp_path, clean_temp_db, ma_cross_config, sample_klines):
        """测试完整的买入流程"""
        # 这个测试模拟整个买入信号到执行的过程
        import json
        from src.engine.strategy_engine import StrategyEngine
        from src.engine.executor import OrderExecutor
        from src.engine.risk_manager import RiskManager

        # 准备组件
        db_path = clean_temp_db
        db = SimulationDB(db_path)
        db.set_balance("USDT", 10000.0)

        # 策略引擎
        strategy_engine = StrategyEngine(ma_cross_config)

        # 执行器
        executor = OrderExecutor("local", {"mode": "local"}, simulation_db=db)
        await executor.initialize()

        # 风控
        risk_config = {"max_trades_per_day": 100, "max_position_size_pct": 0.5}
        risk_manager = RiskManager(risk_config, simulation_db=db)
        risk_manager.initial_balance = 10000.0

        # 设置信号回调
        signal_called = []

        async def on_signal(signal, price, symbol):
            signal_called.append((signal, price, symbol))

            # 模拟 TradingBot 的逻辑
            if signal['action'] == 'buy':
                balance = db.get_balance("USDT")
                position_size = ma_cross_config['position_size']
                position_amount = balance * position_size
                quantity = position_amount / price

                order = {
                    "symbol": symbol,
                    "side": "buy",
                    "quantity": quantity,
                    "price": price,
                    "type": "market",
                    "strategy": ma_cross_config['name']
                }

                allowed, reason = risk_manager.check_order(order, balance)
                assert allowed is True

                result = await executor.execute_order(order)
                assert result['success'] is True

        strategy_engine.set_signal_callback(on_signal)

        # 模拟 K 线数据，构造金叉
        df = sample_klines.copy()
        # 调整价格产生金叉
        df.loc[df.index[-2], 'close'] = 50000
        df.loc[df.index[-1], 'close'] = 50500

        # 发送 K 线
        await strategy_engine.on_kline({
            "exchange": "binance",
            "symbol": "BTC/USDT",
            "timestamp": 1234567890,
            "open": 49900,
            "high": 50600,
            "low": 49900,
            "close": 50500,
            "volume": 100,
            "is_closed": True
        })

        # 验证信号产生并执行
        assert len(signal_called) == 1
        signal, price, symbol = signal_called[0]
        assert signal['action'] == 'buy'
        assert symbol == "BTC/USDT"

        # 验证持仓
        positions = db.get_open_positions("BTC/USDT")
        assert len(positions) == 1

    @pytest.mark.asyncio
    async def test_end_to_end_sell_flow(self, tmp_path, clean_temp_db, ma_cross_config, sample_klines):
        """测试完整的卖出流程（buy→sell）"""
        import json
        from src.engine.strategy_engine import StrategyEngine
        from src.engine.executor import OrderExecutor
        from src.engine.risk_manager import RiskManager

        db_path = clean_temp_db
        db = SimulationDB(db_path)
        db.set_balance("USDT", 0.0)

        # 预开仓（模拟已有持仓）
        db.open_position("BTC/USDT", "long", 0.1, 50000.0)
        db.update_position_price("BTC/USDT", 50500.0)

        strategy_engine = StrategyEngine(ma_cross_config)
        executor = OrderExecutor("local", {"mode": "local"}, simulation_db=db)
        await executor.initialize()

        risk_config = {"max_trades_per_day": 100}
        risk_manager = RiskManager(risk_config)

        sell_called = []

        async def on_signal(signal, price, symbol):
            sell_called.append((signal, price, symbol))

            if signal['action'] == 'sell':
                positions = db.get_open_positions(symbol)
                total_btc = sum(p["quantity"] for p in positions if p["side"] == "long")
                if total_btc <= 0:
                    return

                order = {
                    "symbol": symbol,
                    "side": "sell",
                    "quantity": total_btc,
                    "price": price,
                    "type": "market",
                    "strategy": ma_cross_config['name']
                }

                allowed, reason = risk_manager.check_order(order, 0)
                assert allowed is True

                result = await executor.execute_order(order)
                assert result['success'] is True
                assert result['pnl'] != 0  # 应有盈亏

        strategy_engine.set_signal_callback(on_signal)

        # 构造死叉信号
        df = sample_klines.copy()
        df.loc[df.index[-2], 'close'] = 50500
        df.loc[df.index[-1], 'close'] = 49500  # 下跌，触发死叉或止损

        await strategy_engine.on_kline({
            "exchange": "binance",
            "symbol": "BTC/USDT",
            "timestamp": 1234567890,
            "open": 50500,
            "high": 50600,
            "low": 49500,
            "close": 49500,
            "volume": 100,
            "is_closed": True
        })

        assert len(sell_called) == 1
        signal, price, symbol = sell_called[0]
        assert signal['action'] == 'sell'

        # 验证持仓已平
        positions = db.get_open_positions("BTC/USDT")
        assert len(positions) == 0


import json  # 确保 json 导入
