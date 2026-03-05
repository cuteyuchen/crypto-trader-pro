#!/usr/bin/env python3
"""
生成测试数据：插入持仓、余额、交易记录
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = "data/simulation.db"

def init_db():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # 创建表（如果不存在）
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS balance (
            id INTEGER PRIMARY KEY,
            currency TEXT UNIQUE NOT NULL,
            amount REAL NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity REAL NOT NULL,
            entry_price REAL NOT NULL,
            current_price REAL NOT NULL,
            unrealized_pnl REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP NULL
        );
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            fee REAL DEFAULT 0,
            pnl REAL DEFAULT 0,
            executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    return conn

def insert_test_data(conn):
    # 设置余额为 8500 USDT（初始10000，买入花费500，手续费50）
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO balance (currency, amount, updated_at) VALUES ('USDT', ?, ?)",
                (8500.0, datetime.now()))
    # 插入持仓：BTC 多单
    cur.execute("""
        INSERT INTO positions (symbol, side, quantity, entry_price, current_price, unrealized_pnl, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ("BTC/USDT", "long", 0.01, 50000.0, 51000.0, (51000-50000)*0.01, datetime.now()))
    # 插入两条交易记录
    now = datetime.now()
    cur.execute("""
        INSERT INTO trades (symbol, side, quantity, price, fee, pnl, executed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ("BTC/USDT", "buy", 0.01, 50000.0, 50.0, 0.0, now))
    cur.execute("""
        INSERT INTO trades (symbol, side, quantity, price, fee, pnl, executed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, ("BTC/USDT", "sell", 0.01, 51000.0, 51.0, (51000-50000)*0.01 - 50 - 51, now))
    conn.commit()

if __name__ == "__main__":
    conn = init_db()
    insert_test_data(conn)
    conn.close()
    print("✅ 测试数据已插入")
