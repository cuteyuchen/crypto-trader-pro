import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class SimulationDB:
    """本地模拟交易数据库"""

    def __init__(self, db_path: str = "data/simulation.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS balance (
                    id INTEGER PRIMARY KEY,
                    currency TEXT UNIQUE NOT NULL,
                    amount REAL NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,  -- long | short
                    quantity REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    current_price REAL NOT NULL,
                    unrealized_pnl REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    closed_at TIMESTAMP NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,  -- buy | sell
                    quantity REAL NOT NULL,
                    price REAL NOT NULL,
                    fee REAL DEFAULT 0,
                    pnl REAL DEFAULT 0,  -- 平仓时的盈亏
                    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            logger.info("模拟数据库初始化完成")

    def set_balance(self, currency: str, amount: float):
        """设置余额（初始化或更新）"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO balance (currency, amount, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (currency, amount))
            conn.commit()

    def get_balance(self, currency: str) -> float:
        """获取余额"""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT amount FROM balance WHERE currency = ?", (currency,))
            row = cur.fetchone()
            return row[0] if row else 0.0

    def open_position(self, symbol: str, side: str, quantity: float, entry_price: float):
        """开仓：插入持仓记录"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO positions (symbol, side, quantity, entry_price, current_price, unrealized_pnl, created_at)
                VALUES (?, ?, ?, ?, ?, 0, CURRENT_TIMESTAMP)
            """, (symbol, side, quantity, entry_price))
            conn.commit()
            logger.info(f"开仓: {symbol} {side} {quantity} @ ${entry_price:.2f}")

    def update_position_price(self, symbol: str, current_price: float):
        """更新持仓的当前价格和未实现盈亏"""
        with sqlite3.connect(self.db_path) as conn:
            # 查找未平仓的持仓
            cur = conn.execute("""
                SELECT id, side, quantity, entry_price FROM positions
                WHERE symbol = ? AND closed_at IS NULL
            """, (symbol,))
            rows = cur.fetchall()
            for pos_id, side, qty, entry in rows:
                if side == "long":
                    upnl = (current_price - entry) * qty
                elif side == "short":
                    upnl = (entry - current_price) * qty
                else:
                    upnl = 0
                conn.execute("""
                    UPDATE positions
                    SET current_price = ?, unrealized_pnl = ?
                    WHERE id = ?
                """, (current_price, upnl, pos_id))
            conn.commit()

    def close_position(self, symbol: str, side: str, quantity: float, exit_price: float, fee: float = 0) -> float:
        """平仓：记录交易并标记持仓为已关闭"""
        with sqlite3.connect(self.db_path) as conn:
            # 查找对应的未平仓持仓（FIFO）
            cur = conn.execute("""
                SELECT id, quantity, entry_price FROM positions
                WHERE symbol = ? AND side = ? AND closed_at IS NULL
                ORDER BY created_at ASC
                LIMIT 1
            """, (symbol, side))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"没有找到可平仓的持仓: {symbol} {side}")

            pos_id, qty, entry_price = row
            if qty < quantity:
                raise ValueError(f"持仓数量不足: 需要 {quantity}, 可用 {qty}")

            # 计算盈亏
            if side == "long":
                pnl = (exit_price - entry_price) * quantity
            else:  # short
                pnl = (entry_price - exit_price) * quantity

            # 插入交易记录
            conn.execute("""
                INSERT INTO trades (symbol, side, quantity, price, fee, pnl, executed_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (symbol, "sell" if side == "long" else "buy", quantity, exit_price, fee, pnl))

            # 如果部分平仓，减少持仓数量；完全平仓则标记 closed_at
            remaining = qty - quantity
            if remaining > 0:
                conn.execute("""
                    UPDATE positions SET quantity = ? WHERE id = ?
                """, (remaining, pos_id))
            else:
                conn.execute("""
                    UPDATE positions SET closed_at = CURRENT_TIMESTAMP WHERE id = ?
                """, (pos_id,))

            conn.commit()
            logger.info(f"平仓: {symbol} {side} {quantity} @ ${exit_price:.2f}, 盈亏 ${pnl:.2f}")
            return pnl

    def get_open_positions(self, symbol: str = None) -> List[Dict]:
        """获取所有未平仓持仓"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = """
                SELECT * FROM positions
                WHERE closed_at IS NULL
                AND symbol = ?
            """ if symbol else """
                SELECT * FROM positions
                WHERE closed_at IS NULL
            """
            params = (symbol,) if symbol else ()
            cur = conn.execute(query, params)
            rows = cur.fetchall()
            return [dict(row) for row in rows]

    def get_balance_total(self) -> float:
        """获取总余额（所有币种汇总为USDT）"""
        # 简化：只返回 USDT 余额
        return self.get_balance("USDT")

    def _get_connection(self):
        """获取数据库连接（供外部使用，需手动关闭）"""
        return sqlite3.connect(self.db_path)



# 简单测试
if __name__ == "__main__":
    db = SimulationDB("test_simulation.db")
    db.set_balance("USDT", 10000)
    print("余额:", db.get_balance("USDT"))
    db.open_position("BTC/USDT", "long", 0.01, 50000)
    print("持仓:", db.get_open_positions())
    db.update_position_price("BTC/USDT", 51000)
    print("更新价格后:", db.get_open_positions())
    db.close_position("BTC/USDT", "long", 0.01, 51000)
    print("最终余额:", db.get_balance("USDT"))
