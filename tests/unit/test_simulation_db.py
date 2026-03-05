"""
单元测试：SimulationDB 本地模拟数据库
"""
import pytest
import os
from src.data.simulation_db import SimulationDB


class TestSimulationDB:
    """本地模拟数据库测试"""

    def test_initialization(self, clean_temp_db):
        """测试数据库初始化"""
        db = SimulationDB(clean_temp_db)
        assert os.path.exists(clean_temp_db)

        # 检查表结构
        import sqlite3
        conn = sqlite3.connect(clean_temp_db)
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cur.fetchall()]
        conn.close()

        assert 'balance' in tables
        assert 'positions' in tables
        assert 'trades' in tables

    def test_set_and_get_balance(self, clean_temp_db):
        """测试余额设置和获取"""
        db = SimulationDB(clean_temp_db)

        db.set_balance("USDT", 10000.0)
        assert db.get_balance("USDT") == 10000.0

        db.set_balance("USDT", 5000.0)
        assert db.get_balance("USDT") == 5000.0

        # 获取不存在的币种
        assert db.get_balance("BTC") == 0.0

    def test_open_position(self, clean_temp_db):
        """测试开仓"""
        db = SimulationDB(clean_temp_db)

        db.open_position("BTC/USDT", "long", 0.1, 50000.0)

        positions = db.get_open_positions("BTC/USDT")
        assert len(positions) == 1
        assert positions[0]['symbol'] == "BTC/USDT"
        assert positions[0]['side'] == "long"
        assert positions[0]['quantity'] == 0.1
        assert positions[0]['entry_price'] == 50000.0
        assert positions[0]['unrealized_pnl'] == 0

    def test_update_position_price(self, clean_temp_db):
        """测试更新持仓价格"""
        db = SimulationDB(clean_temp_db)
        db.open_position("BTC/USDT", "long", 0.1, 50000.0)

        # 更新到 51000
        db.update_position_price("BTC/USDT", 51000.0)

        positions = db.get_open_positions("BTC/USDT")
        pos = positions[0]
        assert pos['current_price'] == 51000.0
        assert pos['unrealized_pnl'] == (51000 - 50000) * 0.1  # 100 美元

        # 价格下跌
        db.update_position_price("BTC/USDT", 49000.0)
        positions = db.get_open_positions("BTC/USDT")
        pos = positions[0]
        assert pos['unrealized_pnl'] == (49000 - 50000) * 0.1  # -100 美元

    def test_close_position_full(self, clean_temp_db):
        """测试完全平仓"""
        db = SimulationDB(clean_temp_db)
        db.set_balance("USDT", 0.0)
        db.open_position("BTC/USDT", "long", 0.1, 50000.0)

        pnl = db.close_position("BTC/USDT", "long", 0.1, 51000.0, strategy="test_ma")

        # 检查盈亏
        expected_pnl = 0.1 * (51000 - 50000)
        assert abs(pnl - expected_pnl) < 0.01

        # 检查余额更新
        assert db.get_balance("USDT") > 0

        # 检查持仓已清空
        positions = db.get_open_positions("BTC/USDT")
        assert len(positions) == 0

    def test_close_position_partial(self, clean_temp_db):
        """测试部分平仓"""
        db = SimulationDB(clean_temp_db)
        db.set_balance("USDT", 0.0)
        db.open_position("BTC/USDT", "long", 0.2, 50000.0)

        # 平仓一半
        pnl = db.close_position("BTC/USDT", "long", 0.1, 51000.0)

        # 检查仍有持仓
        positions = db.get_open_positions("BTC/USDT")
        assert len(positions) == 1
        assert positions[0]['quantity'] == 0.1

        # 检查部分盈亏已实现
        assert pnl > 0

    def test_close_position_insufficient(self, clean_temp_db):
        """测试持仓不足的平仓"""
        db = SimulationDB(clean_temp_db)
        db.set_balance("USDT", 0.0)
        db.open_position("BTC/USDT", "long", 0.1, 50000.0)

        with pytest.raises(ValueError, match="持仓数量不足"):
            db.close_position("BTC/USDT", "long", 0.2, 51000.0)

    def test_trades_recording(self, clean_temp_db):
        """测试交易记录"""
        db = SimulationDB(clean_temp_db)
        db.set_balance("USDT", 10000.0)

        # 开仓
        db.open_position("BTC/USDT", "long", 0.1, 50000.0)
        # 平仓
        db.close_position("BTC/USDT", "long", 0.1, 51000.0, fee=1.0, strategy="test_ma")

        conn = db._get_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM trades ORDER BY id DESC")
        rows = cur.fetchall()
        conn.close()

        assert len(rows) >= 1
        last_trade = rows[0]
        assert last_trade['symbol'] == "BTC/USDT"
        assert last_trade['side'] == "sell"
        assert last_trade['quantity'] == 0.1
        assert last_trade['price'] == 51000.0
        assert last_trade['fee'] == 1.0
        assert last_trade['strategy'] == "test_ma"
        assert last_trade['pnl'] > 0

    def test_multiple_positions(self, clean_temp_db):
        """测试多持仓（不同 symbol）"""
        db = SimulationDB(clean_temp_db)
        db.set_balance("USDT", 20000.0)

        db.open_position("BTC/USDT", "long", 0.1, 50000.0)
        db.open_position("ETH/USDT", "long", 1.0, 3000.0)

        positions = db.get_open_positions()
        assert len(positions) == 2

        btc_pos = [p for p in positions if p['symbol'] == "BTC/USDT"][0]
        eth_pos = [p for p in positions if p['symbol'] == "ETH/USDT"][0]

        assert btc_pos['quantity'] == 0.1
        assert eth_pos['quantity'] == 1.0
