# Telegram 通知配置指南

## 1. 通知系统架构

Crypto Trader Pro 的通知系统采用**解耦的文件队列设计**：

```
┌─────────────┐
│ 策略引擎     │ → 产生信号
│ Trader      │ → 执行交易
└─────────────┘
       ↓
┌─────────────────────┐
│ NotificationManager │ → 写入 JSONL 文件
│ (data/notifications.jsonl) │
└─────────────────────┘
       ↓
┌─────────────────────┐
│ 主 AI 会话（HEARTBEAT）│ → 读取新通知
│ notification_dispatcher.py │
└─────────────────────┘
       ↓
   ┌────┴────┐
   │ QQ      │（已实现，通过 HEARTBEAT 推送）
   │ Telegram│（待实现，需配置 Bot Token）
   └─────────┘
```

**设计优点：**
- 交易系统不依赖外部 API，运行稳定
- 通知可异步处理，不阻塞交易
- 易于扩展新通知渠道（邮件、钉钉等）

---

## 2. 配置 Telegram Bot

### 步骤 1：向 @BotFather 创建机器人

1. 打开 Telegram，搜索 `@BotFather`
2. 发送 `/newbot`
3. 按提示输入机器人名称（如 `CryptoTraderBot`）和用户名（需唯一，如 `CryptoTraderProBot`）
4. 创建成功后，BotFather 会返回 **HTTP API Token**，格式如：

```
1234567890:ABCdefGHIjkLmnopQRStuVWXyz1234567890
```

**保存此 Token，后续配置需要。**

### 步骤 2：获取 Chat ID

**方法 A：使用 `getUpdates` API**

1. 先在 Telegram 中向你的机器人发送任意消息（如 `/start`）
2. 访问 URL（替换 `YOUR_TOKEN`）：

```
https://api.telegram.org/botYOUR_TOKEN/getUpdates
```

3. 返回 JSON 中查找 `"chat":{"id":123456789,...}`，`id` 即为 Chat ID

示例响应：
```json
{
  "ok": true,
  "result": [
    {
      "update_id": 123456789,
      "message": {
        "message_id": 1,
        "from": {"id": 111111, "is_bot": false, ...},
        "chat": {"id": 222222, "type": "private", ...},  ← 这里
        "date": 1700000000,
        "text": "/start"
      }
    }
  ]
}
```

**方法 B：使用第三方 Bot**
- 向 `@userinfobot` 发送 `/start`，它会返回你的 Telegram ID

### 步骤 3：配置环境变量

在项目根目录的 `.env` 文件中添加：

```bash
# Telegram Bot 配置
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjkLmnopQRStuVWXyz1234567890
TELEGRAM_CHAT_ID=222222  # 你的用户 ID 或群组 ID
```

**注意：**
- Chat ID 可以是个人（`type=private`）或群组（`type=group`/`supergroup`）
- 如果是群组，确保机器人已被添加到群组并有发送消息权限

### 步骤 4：测试连接

手动发送测试消息：

```python
import requests

token = "YOUR_BOT_TOKEN"
chat_id = "YOUR_CHAT_ID"
message = "测试消息：Crypto Trader Pro 通知系统正常"

url = f"https://api.telegram.org/bot{token}/sendMessage"
data = {
    "chat_id": chat_id,
    "text": message,
    "parse_mode": "HTML"  # 可选，支持 HTML 格式
}
response = requests.post(url, data=data)
print(response.json())
```

如果返回 `{"ok":true,"result":{...}}`，则配置成功。

---

## 3. 事件类型与消息格式

系统内置以下事件类型（`NotificationManager.send()`）：

### 3.1 开仓通知 (`open_position`)

**触发时机：** 买入订单成交后

**示例消息：**
```
📢 开仓买入

BTC/USDT 买入 0.01 @ $50000.00
止损价: $47500.00
止盈价: $55000.00
原因: MA金叉
```

### 3.2 平仓通知 (`close_position`)

**触发时机：** 卖出订单成交后（包括止损/止盈触发）

**示例消息：**
```
📢 平仓卖出

BTC/USDT 卖出 0.01 @ $51000.00
盈亏: +$123.45
原因: 【止损触发】
```

**注意：** 止损/止盈触发时，原因会标注 `【止损触发】` 或 `【止盈触发】`

### 3.3 错误通知 (`error`)

**触发时机：** 订单执行失败或系统异常

**示例消息：**
```
📢 系统错误

订单执行失败: Insufficient balance
时间: 2025-03-05 10:30:00
```

### 3.4 每日报告 (`daily_summary`)

**触发时机：** 每天凌晨第一次运行主循环时

**示例消息：**
```
📊 每日交易报告 - 2025-03-05

💰 账户余额: $10123.45
🎯 初始资金: $10000.00
📈 今日交易: 3 笔
💵 已实现盈亏: $234.56
💸 手续费: $12.34
🧮 净盈亏: $222.22
📊 总资产变化: +$123.45
```

---

## 4. 集成到主 AI 会话

需要在 `notification_dispatcher.py`（已存在）中添加 Telegram 发送逻辑。

### 4.1 实现 TelegramNotifier 类

```python
# 在 notification_dispatcher.py 中添加
import os
import requests

class TelegramNotifier:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.enabled = bool(self.token and self.chat_id)
        if self.enabled:
            print("[TelegramNotifier] 已启用")
        else:
            print("[TelegramNotifier] 未配置，跳过")

    def send(self, text: str):
        """发送消息到 Telegram"""
        if not self.enabled:
            return

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",  # 支持 HTML 格式
            "disable_web_page_preview": True
        }
        try:
            resp = requests.post(url, data=payload, timeout=10)
            if resp.status_code != 200:
                print(f"[TelegramNotifier] 发送失败: {resp.text}")
        except Exception as e:
            print(f"[TelegramNotifier] 请求异常: {e}")
```

### 4.2 修改主循环

在 `dispatch_notifications()` 函数中：

```python
def dispatch_notifications():
    notifier = NotificationManager("data")
    telegram = TelegramNotifier()  # ← 新增

    # 读取上次检查时间（从文件或内存）
    last_check = get_last_check_time()

    pending = notifier.get_pending(last_check)
    for n in pending:
        # 格式化消息
        msg = f"📢 {n['title']}\n\n{n['content']}"

        # 发送到 QQ（已有）
        send_qq_message(msg)

        # 发送到 Telegram（新增）
        telegram.send(msg)

    # 保存本次检查时间
    save_last_check_time()
```

### 4.3 频率控制

- HEARTBEAT 默认每 30 分钟运行一次
-  telegram 发送频率与 QQ 一致
- Telegram Bot API 有速率限制（约 30 条/秒），足够使用

---

## 5. 高级配置

### 5.1 消息模板自定义

可以修改 `NotificationManager.send()` 调用处的消息格式，或添加模板引擎。

**示例：为不同事件类型设置不同格式**

```python
def format_message(event_type, title, content, data):
    templates = {
        'open_position': "📈 {title}\n{content}",
        'close_position': "📉 {title}\n{content}",
        'error': "❌ {title}\n{content}",
        'daily_summary': "📊 {title}\n{content}"
    }
    tmpl = templates.get(event_type, "📢 {title}\n{content}")
    return tmpl.format(title=title, content=content)
```

### 5.2 富文本与 Emoji

支持 HTML `<b>粗体</b>`、`<i>斜体</i>`：

```python
msg = f"""📢 <b>{title}</b>

交易对: <code>{symbol}</code>
买入量: <b>{quantity} BTC</b>
价格: <code>${price:,.2f}</code>
"""
telegram.send(msg)
```

**常用 Emoji：**
- 📈 开多 / 买入
- 📉 平仓 / 卖出
- 💰 资金 / 余额
- ⚠️ 警告 / 风险
- ❌ 错误
- ✅ 成功
- 🔔 通知

### 5.3 静默时段（可选）

可在 `notification_dispatcher.py` 中添加时间段过滤，避免夜间打扰：

```python
from datetime import datetime, time

def is_quiet_hours():
    now = datetime.now().time()
    start = time(23, 0)
    end = time(8, 0)
    if start <= end:
        return start <= now < end
    else:
        # 跨天的情况（23:00 - 08:00）
        return now >= start or now < end

if is_quiet_hours():
    # 只发送高优先级通知（如错误、止损）
    if event_type in ['error', 'stop_loss']:
        telegram.send(msg)
else:
    telegram.send(msg)
```

---

## 6. 调试与故障排除

### 6.1 测试脚本

创建 `test_telegram.py`：

```python
#!/usr/bin/env python3
import os
import sys
sys.path.append('.')
from notification_dispatcher import TelegramNotifier

token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")

if not token or not chat_id:
    print("请先配置 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID")
    sys.exit(1)

telegram = TelegramNotifier()
telegram.send("✅ Telegram 通知测试成功！")
```

运行：
```bash
python test_telegram.py
```

### 6.2 常见错误

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| `{"ok":false,"error_code":403,"description":"chat not found"}` | Chat ID 错误 | 检查是否向机器人发送过消息；使用 `getUpdates` 确认 |
| `{"ok":false,"error_code":429,"description":"Too Many Requests"}` | 触发速率限制 | 减少发送频率，或等待 1 秒后再试 |
| `{"ok":false,"error_code":400,"description":"bad request"}` | 消息格式错误 | 检查 payload 格式，确保 `chat_id` 为字符串或整数 |
| 请求超时 | 网络问题 | 检查服务器能否访问外网（api.telegram.org） |

### 6.3 查看机器人状态

访问：
```
https://api.telegram.org/botYOUR_TOKEN/getMe
```

返回机器人信息：
```json
{
  "ok": true,
  "result": {
    "id": 1234567890,
    "is_bot": true,
    "first_name": "CryptoTraderProBot",
    "username": "CryptoTraderProBot"
  }
}
```

---

## 7. 多频道通知（扩展）

### 7.1 多个 Chat ID

支持同时通知多个用户/群组：

```python
class MultiTelegramNotifier:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        # 多个 chat_id，用逗号分隔
        chat_ids = os.getenv("TELEGRAM_CHAT_IDS", "")
        self.chat_ids = [cid.strip() for cid in chat_ids.split(",") if cid.strip()]

    def send(self, text):
        for chat_id in self.chat_ids:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            requests.post(url, data={"chat_id": chat_id, "text": text})
```

`.env` 配置：
```bash
TELEGRAM_CHAT_IDS=111111,222222,333333
```

### 7.2 通知级别过滤

例如：仅高风险事件才发送 Telegram，普通通知只发 QQ：

```python
def dispatch():
    for n in pending:
        msg = format_message(n)

        # QQ 全部发送
        send_qq(msg)

        # Telegram 只发送错误和止损
        if n['type'] in ['error', 'close_position']:
            if n.get('data', {}).get('reason') in ['止损触发', 'error']:
                telegram.send(msg)
```

---

## 8. 安全性

- **Token 保密**：`.env` 文件不应提交到 Git，添加到 `.gitignore`
- **Chat ID** 虽然是公开的，但也不建议硬编码在代码中
- 使用环境变量或配置文件管理敏感信息
- 生产环境建议使用独立的 Telegram Bot，不要与管理员私人 Bot 混用

---

## 9. 参考资源

- Telegram Bot API：https://core.telegram.org/bots/api
- CCXT 文档：https://docs.ccxt.com/
- 通知管理器源码：`src/notifier.py`
- 主 AI 会话：`notification_dispatcher.py`

---

## 10. 下一步

- 集成邮件通知（SMTP）
- 钉钉/企业微信机器人（Webhook）
- 多语言消息模板
- 通知频率限制与聚合（避免刷屏）
