"""
通知管理器 - 将交易事件写入通知队列并发送到多个通道
主 AI 会话会读取这些通知并发送 QQ 消息；同时支持 Telegram Bot
"""
import json
import os
import requests
from datetime import datetime
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Telegram Bot 通知器"""

    def __init__(self, bot_token: str, chat_id: str):
        """
        Args:
            bot_token: Telegram Bot Token (如 123456:ABC...)
            chat_id: 目标聊天 ID（可为用户 ID、群组 ID，支持 @username）
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self.enabled = bool(bot_token and chat_id)

    def send(self, title: str, content: str, parse_mode: str = "HTML") -> bool:
        """
        发送 Telegram 消息

        Returns:
            bool: 发送成功返回 True，失败返回 False
        """
        if not self.enabled:
            return False

        # 组合消息：标题加粗，正文
        message = f"<b>{title}</b>\n\n{content}"

        try:
            resp = requests.post(self.api_url, data={
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_notification': False
            }, timeout=10)
            if resp.status_code == 200:
                logger.info(f"Telegram 消息发送成功: {title}")
                return True
            else:
                logger.warning(f"Telegram 消息发送失败: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Telegram 消息异常: {e}")
            return False


class NotificationManager:
    """通知管理器（多通道）"""

    def __init__(self, notifications_dir: str = "data"):
        """
        Args:
            notifications_dir: 通知文件存放目录
        """
        self.notifications_dir = notifications_dir
        self.notifications_file = os.path.join(notifications_dir, "notifications.jsonl")
        self._ensure_dir()

        # 初始化 Telegram 通知器（从环境变量读取）
        self.telegram = TelegramNotifier(
            bot_token=os.getenv('TELEGRAM_BOT_TOKEN', ''),
            chat_id=os.getenv('TELEGRAM_CHAT_ID', '')
        )
        if self.telegram.enabled:
            logger.info("Telegram 通知已启用")
        else:
            logger.info("Telegram 通知未配置（环境变量缺失）")

    def _ensure_dir(self):
        """确保目录存在"""
        os.makedirs(self.notifications_dir, exist_ok=True)

    def send(self, event_type: str, title: str, content: str, data: Dict[str, Any] = None):
        """
        发送通知（多通道）

        Args:
            event_type: 事件类型 ("open_position", "close_position", "error", "daily_summary")
            title: 通知标题
            content: 通知正文（简洁）
            data: 额外数据（可选）
        """
        notification = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "title": title,
            "content": content,
            "data": data or {}
        }
        try:
            # 1. 写入文件（供 QQ Bot 心跳读取）
            with open(self.notifications_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(notification, ensure_ascii=False) + '\n')
            logger.info(f"通知已记录: {event_type} - {title}")

            # 2. 同时发送 Telegram（如果启用）
            if self.telegram.enabled:
                # 根据事件类型选择表情和格式
                emoji_map = {
                    "open_position": "🟢",
                    "close_position": "🔵",
                    "stop_loss": "🔴",
                    "take_profit": "🟡",
                    "error": "❌",
                    "daily_summary": "📊"
                }
                emoji = emoji_map.get(event_type, "ℹ️")
                tg_title = f"{emoji} {title}"
                self.telegram.send(tg_title, content)
        except Exception as e:
            logger.error(f"通知发送失败: {e}")
        except Exception as e:
            logger.error(f"写入通知失败: {e}")

    def get_pending(self, last_check_timestamp: str = None) -> list:
        """
        获取待处理通知（从上次检查时间之后）

        Args:
            last_check_timestamp: ISO 格式时间戳，如 "2025-03-05T07:00:00"

        Returns:
            通知列表
        """
        pending = []
        if not os.path.exists(self.notifications_file):
            return pending

        with open(self.notifications_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    notif = json.loads(line)
                    if last_check_timestamp and notif["timestamp"] <= last_check_timestamp:
                        continue
                    pending.append(notif)
                except json.JSONDecodeError:
                    continue
        return pending

    def clear_old(self, days: int = 7):
        """清理旧通知（保留最近 N 天的）"""
        # 简化实现：不删除文件，因为 jsonl 追加写入很难删除特定行
        # 可以定期归档或由主 AI 会话标记已读
        pass
