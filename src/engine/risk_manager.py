import logging
from datetime import datetime, timedelta
from typing import Dict, Any

logger = logging.getLogger(__name__)


class RiskManager:
    """风控管理器"""

    def __init__(self, config: Dict[str, Any], simulation_db=None):
        self.config = config
        self.db = simulation_db
        self.daily_pnl = 0.0
        self.trade_count_today = 0
        self.last_reset_day = datetime.now().date()
        self.cooldown_until = None  # 冷却期截止时间

    def check_order(self, order_request: Dict[str, Any], current_balance: float) -> tuple[bool, str]:
        """
        检查是否允许下单

        Returns:
            (allowed: bool, reason: str)
        """
        # 1. 检查冷却期
        if self.cooldown_until and datetime.now() < self.cooldown_until:
            return False, f"处于冷却期，剩余等待时间: {(self.cooldown_until - datetime.now()).seconds}秒"

        # 2. 检查每日交易次数
        self._update_daily_counters()
        if self.trade_count_today >= self.config.get("max_trades_per_day", 100):
            return False, "已达到每日交易次数上限"

        # 3. 检查单笔仓位大小
        side = order_request["side"]
        quantity = order_request["quantity"]
        price = order_request.get("price", 0)
        if price == 0:
            # 无法评估，暂放行
            return True, ""

        order_value = price * quantity
        position_pct = order_value / current_balance if current_balance > 0 else 0
        max_position_pct = self.config.get("max_position_size_pct", 0.5)
        if position_pct > max_position_pct:
            return False, f"仓位过大: {position_pct*100:.1f}% > 限制 {max_position_pct*100:.1f}%"

        # 4. 检查滑点控制（当前价格不可用时跳过）
        # TODO: 基于当前市场价格评估

        # 5. 检查熔断（根据条件设置 self.cooldown_until）
        # 这里暂时不实现

        return True, ""

    def on_trade_completed(self, pnl: float):
        """交易完成后的回调（更新风控状态）"""
        self.daily_pnl += pnl
        self.trade_count_today += 1

        # 检查日内最大亏损
        max_daily_loss_pct = self.config.get("max_daily_loss_pct", 0.1)
        # 需要知道初始资金，这里假设从 DB 获得
        # 简化：在 main 初始化时传入 initial balance
        if hasattr(self, 'initial_balance') and self.daily_pnl < -self.initial_balance * max_daily_loss_pct:
            logger.warning(f"触发日内亏损熔断！当前亏损 ${self.daily_pnl:.2f}")
            self.cooldown_until = datetime.now() + timedelta(hours=1)
            if self.config.get("emergency_stop_enabled", True):
                # TODO: 设置全局停止交易标志
                pass

        # 更新日期
        self._update_daily_counters()

    def _update_daily_counters(self):
        """更新每日计数器（跨天重置）"""
        today = datetime.now().date()
        if today != self.last_reset_day:
            self.last_reset_day = today
            self.trade_count_today = 0
            self.daily_pnl = 0
            logger.info("风控：新的一天，重置交易计数和盈亏")

    def reset(self):
        """重置风控状态"""
        self.daily_pnl = 0.0
        self.trade_count_today = 0
        self.last_reset_day = datetime.now().date()
        self.cooldown_until = None


# 测试
if __name__ == "__main__":
    config = {
        "max_trades_per_day": 10,
        "max_position_size_pct": 0.1,
        "max_daily_loss_pct": 0.05,
        "emergency_stop_enabled": True
    }
    rm = RiskManager(config)
    rm.initial_balance = 10000

    # 模拟检查
    allowed, reason = rm.check_order({
        "side": "buy",
        "quantity": 0.01,
        "price": 50000
    }, 10000)
    print(f"允许下单: {allowed}, 原因: {reason}")
