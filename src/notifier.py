"""
通知管理器 - 将交易事件写入通知队列
主 AI 会话会读取这些通知并发送 QQ 消息
"""
import json
import os
from datetime import datetime
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class NotificationManager:
    """通知管理器"""

    def __init__(self, notifications_dir: str = "data"):
        """
        Args:
            notifications_dir: 通知文件存放目录
        """
        self.notifications_dir = notifications_dir
        self.notifications_file = os.path.join(notifications_dir, "notifications.jsonl")
        self._ensure_dir()

    def _ensure_dir(self):
        """确保目录存在"""
        os.makedirs(self.notifications_dir, exist_ok=True)

    def send(self, event_type: str, title: str, content: str, data: Dict[str, Any] = None):
        """
        发送通知（写入文件）

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
            with open(self.notifications_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(notification, ensure_ascii=False) + '\n')
            logger.info(f"通知已记录: {event_type} - {title}")
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
