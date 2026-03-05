"""
单元测试：RiskManager 风控逻辑
"""
import pytest
from datetime import datetime, timedelta
from src.engine.risk_manager import RiskManager


class TestRiskManager:
    """风控管理器测试"""

    def test_initialization(self, risk_config):
        """测试风控器初始化"""
        rm = RiskManager(risk_config)
        assert rm.config == risk_config
        assert rm.daily_pnl == 0.0
        assert rm.trade_count_today == 0
        assert rm.cooldown_until is None

    def test_check_order_position_size(self, risk_config):
        """测试仓位大小检查"""
        rm = RiskManager(risk_config)
        rm.initial_balance = 10000.0

        # 正常仓位（20%）
        allowed, reason = rm.check_order({
            "side": "buy",
            "quantity": 0.1,
            "price": 20000.0  # 价值 2000，占 20%
        }, 10000.0)
        assert allowed is True

        # 过大仓位（60% > 50% 限制）
        allowed, reason = rm.check_order({
            "side": "buy",
            "quantity": 0.1,
            "price": 60000.0  # 价值 6000，占 60%
        }, 10000.0)
        assert allowed is False
        assert '仓位过大' in reason

    def test_check_order_daily_trade_limit(self, risk_config):
        """测试每日交易次数限制"""
        rm = RiskManager(risk_config)
        rm.initial_balance = 10000.0
        rm.trade_count_today = 10  # 模拟已达到上限
        rm.last_reset_day = datetime.now().date()

        allowed, reason = rm.check_order({
            "side": "buy",
            "quantity": 0.1,
            "price": 50000.0
        }, 10000.0)
        assert allowed is False
        assert '每日交易次数上限' in reason

    def test_check_order_cooldown(self, risk_config):
        """测试冷却期检查"""
        rm = RiskManager(risk_config)
        rm.initial_balance = 10000.0
        # 设置冷却期至未来
        rm.cooldown_until = datetime.now() + timedelta(seconds=300)

        allowed, reason = rm.check_order({
            "side": "buy",
            "quantity": 0.1,
            "price": 50000.0
        }, 10000.0)
        assert allowed is False
        assert '冷却期' in reason

    def test_on_trade_completed_daily_count(self, risk_config):
        """测试交易完成后的计数更新"""
        rm = RiskManager(risk_config)
        rm.initial_balance = 10000.0

        rm.on_trade_completed(100.0)
        assert rm.trade_count_today == 1
        assert rm.daily_pnl == 100.0

        rm.on_trade_completed(-50.0)
        assert rm.trade_count_today == 2
        assert rm.daily_pnl == 50.0

    def test_daily_loss_熔断(self, risk_config):
        """测试日内最大亏损熔断"""
        rm = RiskManager(risk_config)
        rm.initial_balance = 10000.0
        rm.config['max_daily_loss_pct'] = 0.05  # 5%
        rm.config['emergency_stop_enabled'] = True

        # 模拟亏损达到限制
        rm.daily_pnl = -600.0  # -6% of 10000
        rm.on_trade_completed(0.0)  # 触发检查

        assert rm.cooldown_until is not None
        # 熔断后应设置 1 小时冷却

    def test_daily_reset(self, risk_config):
        """测试每日计数器重置"""
        rm = RiskManager(risk_config)
        rm.trade_count_today = 10
        rm.daily_pnl = 500.0
        rm.last_reset_day = datetime.now().date()

        # 模拟新的一天
        rm._update_daily_counters()  # 在同一天不会重置
        assert rm.trade_count_today == 10

        # 修改日期模拟新的一天
        rm.last_reset_day = (datetime.now() - timedelta(days=1)).date()
        rm._update_daily_counters()
        assert rm.trade_count_today == 0
        assert rm.daily_pnl == 0.0

    def test_reset(self, risk_config):
        """测试手动重置"""
        rm = RiskManager(risk_config)
        rm.trade_count_today = 10
        rm.daily_pnl = 500.0
        rm.cooldown_until = datetime.now() + timedelta(hours=1)

        rm.reset()

        assert rm.trade_count_today == 0
        assert rm.daily_pnl == 0.0
        assert rm.cooldown_until is None

    def test_check_order_zero_price(self, risk_config):
        """测试价格为零的情况（应放行）"""
        rm = RiskManager(risk_config)
        rm.initial_balance = 10000.0

        allowed, reason = rm.check_order({
            "side": "buy",
            "quantity": 0.1,
            "price": 0  # 未知价格
        }, 10000.0)
        # 无法评估仓位大小时应放行
        assert allowed is True
        assert reason == ""
