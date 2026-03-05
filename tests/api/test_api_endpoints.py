"""
API 端点测试（使用 pytest + requests）
"""
import pytest
import json
import os
import tempfile
from unittest.mock import Mock, patch, AsyncMock
from flask import Flask

# 导入 Dashboard 类用于测试
from src.dashboard.app import Dashboard


class TestAPIEndpoints:
    """API 端点测试套件"""

    @pytest.fixture
    def app(self, tmp_path, clean_temp_db, ma_cross_config, sim_config, risk_config):
        """创建测试用的 Flask 应用"""
        # 创建临时的配置文件和数据库
        self._setup_temp_config(tmp_path, ma_cross_config, sim_config, risk_config, clean_temp_db)

        # 创建模拟的 TradingBot
        mock_bot = self._create_mock_bot(clean_temp_db)

        # 创建 Dashboard 实例
        dashboard = Dashboard(mock_bot, host='127.0.0.1', port=5001)
        # 禁用认证以便测试（或者提供测试凭据）
        dashboard.auth_user = 'test_admin'
        dashboard.auth_pass = 'test_pass'

        yield dashboard.app

    def _setup_temp_config(self, tmp_path, ma_cross_config, sim_config, risk_config, db_path):
        """设置临时配置文件"""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # modes.json
        modes = {
            "mode": "local",
            "dashboard_enabled": True,
            "notifications_enabled": False,
            "strategy": "ma_cross"
        }
        (config_dir / "modes.json").write_text(json.dumps(modes))

        # strategies/ma_cross.json
        strategies_dir = config_dir / "strategies"
        strategies_dir.mkdir()
        (strategies_dir / "ma_cross.json").write_text(json.dumps(ma_cross_config))

        # risk.json
        (config_dir / "risk.json").write_text(json.dumps(risk_config))

        # simulation/local.json
        sim_dir = config_dir / "simulation"
        sim_dir.mkdir()
        (sim_dir / "local.json").write_text(json.dumps(sim_config))

    def _create_mock_bot(self, db_path):
        """创建带有模拟组件的 TradingBot"""
        mock_bot = Mock()
        mock_bot.mode_config = {"mode": "local", "dashboard_enabled": True}
        mock_bot.strategy_config = {
            "name": "Test_MA",
            "symbol": "BTC/USDT",
            "position_size": 0.2
        }
        mock_bot.running = True

        # 模拟数据库
        mock_db = Mock()
        mock_db.get_balance.return_value = 10000.0
        mock_db.get_open_positions.return_value = []
        mock_bot.db = mock_db

        # 模拟策略引擎
        mock_strategy_engine = Mock()
        mock_strategy_engine.get_status.return_value = {
            "name": "Test_MA",
            "state": "out",
            "entry_price": 0.0
        }
        mock_bot.strategy_engine = mock_strategy_engine

        # 模拟 executor
        mock_executor = Mock()
        mock_executor.get_balance = AsyncMock(return_value=10000.0)
        mock_executor.get_positions = AsyncMock(return_value=[])
        mock_executor.get_recent_trades = AsyncMock(return_value=[
            {
                "id": "test1",
                "executed_at": "2025-03-05T10:00:00",
                "symbol": "BTC/USDT",
                "side": "buy",
                "quantity": 0.1,
                "price": 50000.0,
                "fee": 0.5
            }
        ])
        # execute_order 异步且返回 dict
        async def mock_execute(order):
            if order['side'] == 'buy':
                return {
                    "success": True,
                    "order_id": "test_order_1",
                    "filled_quantity": order['quantity'],
                    "avg_price": order.get('price', 50000.0),
                    "fee": order.get('quantity', 0.1) * order.get('price', 50000.0) * 0.001,
                    "pnl": 0.0
                }
            elif order['side'] == 'sell':
                return {
                    "success": True,
                    "order_id": "test_order_2",
                    "filled_quantity": order['quantity'],
                    "avg_price": order.get('price', 51000.0),
                    "fee": order.get('quantity', 0.1) * order.get('price', 51000.0) * 0.001,
                    "pnl": 100.0
                }
            return {"success": False, "error": "unknown"}

        mock_executor.execute_order = AsyncMock(side_effect=mock_execute)
        mock_bot.executor = mock_executor

        # 模拟 executor_ready（用于 /api/order）
        mock_bot.executor_ready = Mock()
        mock_bot.executor_ready.done.return_value = True
        mock_bot.executor_ready.result.return_value = None

        return mock_bot

    def test_api_status(self, app):
        """测试 GET /api/status"""
        client = app.test_client()
        response = client.get('/api/status')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['mode'] == 'local'
        assert data['running'] is True
        assert data['strategy'] == 'Test_MA'
        assert data['symbol'] == 'BTC/USDT'

    def test_api_balance(self, app):
        """测试 GET /api/balance"""
        client = app.test_client()
        response = client.get('/api/balance')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'USDT' in data
        assert data['USDT'] == 10000.0

    def test_api_positions(self, app):
        """测试 GET /api/positions"""
        client = app.test_client()
        response = client.get('/api/positions')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)

    def test_api_trades(self, app):
        """测试 GET /api/trades"""
        client = app.test_client()
        response = client.get('/api/trades?limit=20')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert 'side' in data[0]

    def test_api_strategy(self, app):
        """测试 GET /api/strategy"""
        client = app.test_client()
        response = client.get('/api/strategy')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'name' in data
        assert 'state' in data

    def test_api_order_buy(self, app):
        """测试 POST /api/order (buy)"""
        client = app.test_client()
        payload = {
            "side": "buy",
            "quantity": 0.1,
            "price": 50000.0
        }
        response = client.post('/api/order', json=payload,
                               headers={'Content-Type': 'application/json'})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['filled_quantity'] == 0.1
        assert 'avg_price' in data

    def test_api_order_sell(self, app):
        """测试 POST /api/order (sell)"""
        client = app.test_client()
        payload = {
            "side": "sell",
            "quantity": 0.1,
            "price": 51000.0
        }
        response = client.post('/api/order', json=payload,
                               headers={'Content-Type': 'application/json'})
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['pnl'] == 100.0

    def test_api_order_invalid_mode(self, app):
        """测试非 local 模式下的下单拒绝"""
        # 修改 bot.mode_config 模拟非 local 模式
        from unittest.mock import patch
        app.bot = self._create_mock_bot('/tmp/test.db')
        app.bot.mode_config['mode'] = 'testnet'

        client = app.test_client()
        payload = {"side": "buy", "quantity": 0.1}
        response = client.post('/api/order', json=payload)
        assert response.status_code == 400
        data = json.loads(response.data)
        assert '仅 local 模式' in data['error']

    def test_api_strategies_list(self, app, tmp_path):
        """测试 GET /api/strategies"""
        # 需要确保有策略配置文件
        client = app.test_client()
        response = client.get('/api/strategies')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        # 至少应该发现 ma_cross
        names = [s['type'] for s in data]
        assert 'ma_cross' in names

    def test_api_strategy_reload(self, app):
        """测试 POST /api/strategy/reload"""
        client = app.test_client()
        response = client.post('/api/strategy/reload')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True

    def test_api_backtest(self, app):
        """测试 POST /api/backtest"""
        client = app.test_client()
        payload = {
            "strategy": "ma_cross",
            "days": 7,
            "initial_balance": 10000
        }
        response = client.post('/api/backtest', json=payload)
        assert response.status_code == 200
        data = json.loads(response.data)
        # 回测应该返回报告
        assert 'final_balance' in data or 'total_pnl' in data or 'trades' in data

    def test_api_config_get(self, app, tmp_path):
        """测试 GET /api/config"""
        client = app.test_client()
        response = client.get('/api/config')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'mode' in data

    def test_api_logs(self, app):
        """测试 GET /api/logs"""
        client = app.test_client()
        response = client.get('/api/logs')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'logs' in data

    def test_health_check(self, app):
        """测试 GET /health"""
        client = app.test_client()
        response = client.get('/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
