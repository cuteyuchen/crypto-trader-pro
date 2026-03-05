# Freqtrade 定制化设计方案

## 1. 项目概述

基于官方 freqtrade 构建中文版、移动端友好的加密货币自动交易系统。**不修改 freqtrade 核心代码**，通过配置、模板覆盖、静态资源替换实现定制，确保随时可升级官方版本。

---

## 2. 系统架构

### 2.1 原版 freqtrade 架构

```
┌─────────────────────────────────────────────┐
│            freqtrade (Python 包)             │
│  ├── 策略引擎 (strategy.py)                 │
│  ├── 订单执行 (execute.py)                  │
│  ├── 回测引擎 (backtesting.py)              │
│  ├── 优化器 (optimizer.py)                  │
│  ├── WebUI (Flask + Plotly)                 │
│  └── 数据存储 (SQLite)                      │
└─────────────────────────────────────────────┘
```

### 2.2 定制版架构（分层隔离）

```
~/crypto-trader/
├── freqtrade/                 # 原版（通过 pip 或 git 安装，不变）
│   └── site-packages/freqtrade/
├── custom-config/             # 定制配置层
│   ├── config.json            # 主配置（中文化）
│   ├── strategies/            # 自定义策略（中文注释）
│   └── pairlists/             # 交易对列表
├── custom-ui/                 # 定制表现层
│   ├── templates/             # 覆盖 WebUI 模板（中文化）
│   ├── static/
│   │   ├── css/
│   │   │   └── mobile.css    # 移动端样式
│   │   ├── js/
│   │   └── img/
│   └── patches/               # 其他补丁（如有）
├── docker-compose.yml         # 容器编排（挂载 custom-* 目录）
├── .env                       # 环境变量（API Key）
├── data/                      # 持久化数据（SQLite, logs）
└── README.md                  # 使用说明
```

**核心原则**：
- `freqtrade/` 目录**完全不变**，任何 freqtrade 版本升级只需 `pip install -U freqtrade`
- 所有定制文件在 `custom-*` 目录，易于备份和迁移
- Docker 卷挂载实现配置和 UI 覆盖

---

## 3. 配置结构中文化

### 3.1 主配置 `custom-config/config.json`

```json
{
  "max_open_trades": 3,
  "stake_currency": "USDT",
  "stake_amount": 100,
  "dry_run": true,
  "dry_run_wallet": 10000,
  "exchange": {
    "name": "okx",
    "key": "${OKX_API_KEY}",
    "secret": "${OKX_SECRET}",
    "password": "${OKX_PASSPHRASE}",
    "ccxt_config": {},
    "ccxt_async_config": {}
  },
  "pairlists": [
    {
      "method": "StaticPairList",
      "pairlist": [
        "BTC/USDT",
        "ETH/USDT"
      ]
    }
  ],
  "strategy": "MA交叉策略",
  "timeframe": "5m",
  "timerange": "20240101-",
  "version": 2,
  "dataformat_ohlcv": "feather",
  "dataformat_trades": "jsonl",
  "logfile": "logs/freqtrade.log",
  "loglevel": "info",
  "state": "state.json",
  "position_adjustment_enable": false,
  "bot_name": "加密货币交易机器人",
  "metrics": "sharpe",
  "max_drawdown": 0.20,
  "stoploss": -0.05,
  "trailing_stop": false,
  "roi": {
    "0": 0.10
  },
  "notifications": {
    "telegram": {
      "enabled": false
    }
  }
}
```

**中文化要点**：
- `strategy` 字段使用自定义策略的中文类名
- `bot_name` 显示在 WebUI 标题
- 所有注释说明使用中文（可在 JSON 中通过 `# 注释` 形式，实际使用环境变量或单独文档）

---

### 3.2 策略配置示例 `custom-config/strategies/ma_cross_cn.py`

```python
from freqtrade.strategy import IStrategy
from talib.abstract import SMA
import pandas as pd
from typing import Dict, Any

class MA交叉策略(IStrategy):
    """
    MA 移动平均线交叉策略（中文版）
    当快线上穿慢线时买入，下穿时卖出
    """
    # --- 基础设置 ---
    timeframe = "5m"
    minimal_roi = {"0": 0.10}
    stoploss = -0.05
    trailing_stop = False

    # --- 策略参数 ---
    fast_period = 10
    slow_period = 30

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        计算技术指标
        """
        dataframe['fast_ma'] = SMA(dataframe['close'], timeperiod=self.fast_period)
        dataframe['slow_ma'] = SMA(dataframe['close'], timeperiod=self.slow_period)
        return dataframe

    def populate_buy_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        生成买入信号
        """
        dataframe.loc[
            (dataframe['fast_ma'] > dataframe['slow_ma']) &
            (dataframe['fast_ma'].shift(1) <= dataframe['slow_ma'].shift(1)),
            'buy'] = 1
        return dataframe

    def populate_sell_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        生成卖出信号
        """
        dataframe.loc[
            (dataframe['fast_ma'] < dataframe['slow_ma']) &
            (dataframe['fast_ma'].shift(1) >= dataframe['slow_ma'].shift(1)),
            'sell'] = 1
        return dataframe

    # 可选：自定义日志（中文）
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, **kwargs) -> bool:
        self.log(f"✅ 买入确认: {pair} 数量={amount} 价格={rate}")
        return True

    def confirm_trade_exit(self, pair: str, order_type: str, amount: float, rate: float,
                           reason: str, **kwargs) -> bool:
        self.log(f"🔵 卖出确认: {pair} 数量={amount} 价格={rate} 原因={reason}")
        return True
```

---

## 4. WebUI 覆盖策略（中文化）

### 4.1 需要覆盖的模板文件

| 原文件（freqtrade） | 覆盖位置（custom-ui） | 修改内容 |
|-------------------|---------------------|----------|
| `freqtrade/web/templates/layout.html` | `custom-ui/templates/layout.html` | 标题、导航菜单中文化 |
| `freqtrade/web/templates/navbar.html` | `custom-ui/templates/navbar.html` | 导航链接文字翻译 |
| `freqtrade/web/templates/overview.html` | `custom-ui/templates/overview.html` | 概览页面所有标签、按钮 |
| `freqtrade/web/templates/trades.html` | `custom-ui/templates/trades.html` | 持仓/交易记录表格标题 |
| `freqtrade/web/templates/strategies.html` | `custom-ui/templates/strategies.html` | 策略列表、配置表单 |
| `freqtrade/web/templates/backtesting.html` | `custom-ui/templates/backtesting.html` | 回测页面 |
| `freqtrade/web/templates/config.html` | `custom-ui/templates/config.html` | 配置页面 |
| `freqtrade/web/templates/logs.html` | `custom-ui/templates/logs.html` | 日志页面 |

### 4.2 中文字符串映射表（部分）

| 英文 | 中文 |
|------|------|
| Open Trades | 持仓明细 |
| Closed Trades | 平仓记录 |
| Profit | 盈亏 |
| Win / Loss | 盈利 / 亏损 |
| Drawdown | 回撤 |
| ROI | 收益率 |
| Backtesting | 回测 |
| Hyperopt | 参数优化 |
| Strategy | 策略 |
| Configuration | 配置 |
| Logs | 日志 |
| Dashboard | 看板 |
| Exchange | 交易所 |
| Notifications | 通知 |
| Telegram | 电报 |
| Dry-run | 模拟运行 |
| Start | 开始 |
| Stop | 停止 |
| Save | 保存 |
| Cancel | 取消 |
| Loading... | 加载中... |
| No data available | 暂无数据 |
| Success | 成功 |
| Error | 错误 |

### 4.3 覆盖机制

在 `docker-compose.yml` 中设置 `FLASK_TEMPLATE_DIR` 和 `FLASK_STATIC_DIR` 环境变量，让 freqtrade 优先从 `custom-ui/` 加载模板和静态文件。

```yaml
environment:
  - FLASK_TEMPLATE_DIR=/freqtrade/user_data/ui/templates
  - FLASK_STATIC_DIR=/freqtrade/user_data/ui/static
```

---

## 5. 移动端适配方案

### 5.1 响应式 CSS `custom-ui/static/css/mobile.css`

```css
/* 移动端优先 */
@media (max-width: 768px) {
    .container {
        padding: 10px !important;
    }

    /* 表格横向滚动 */
    .table-responsive {
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
    }

    /* 简化导航 */
    .navbar-nav {
        flex-direction: column;
        width: 100%;
    }

    .nav-link {
        padding: 12px 16px;
        font-size: 16px;
    }

    /* 按钮加大 */
    .btn {
        min-height: 44px;
        min-width: 44px;
        padding: 10px 16px;
        font-size: 16px;
    }

    /* 图表自适应 */
    .js-plotly-plot {
        width: 100% !important;
        height: 300px !important;
    }

    /* 隐藏非核心列 */
    .hide-mobile {
        display: none !important;
    }
}

/* 触摸友好 */
button, a, input, select {
    min-height: 44px;
}
```

### 5.2 移动端导航模板 `custom-ui/templates/mobile_navbar.html`

```html
<nav class="navbar navbar-expand-md navbar-dark bg-dark fixed-top">
    <div class="container-fluid">
        <a class="navbar-brand" href="/">🤖 交易机器人</a>
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse"
                data-bs-target="#mobile-navbar" aria-controls="mobile-navbar"
                aria-expanded="false" aria-label="切换导航">
            <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="mobile-navbar">
            <ul class="navbar-nav me-auto mb-2 mb-md-0">
                <li class="nav-item">
                    <a class="nav-link" href="/">📊 看板</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="/trades">💱 持仓</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="/strategies">🧠 策略</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="/backtesting">📈 回测</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="/config">⚙️ 配置</a>
                </li>
            </ul>
        </div>
    </div>
</nav>
```

在 `layout.html` 中根据 User-Agent 动态加载：

```html
{% if request.user_agent.mobile %}
    {% include "mobile_navbar.html" %}
{% else %}
    {% include "navbar.html" %}
{% endif %}
```

---

## 6. Docker 部署方案

### 6.1 `docker-compose.yml`

```yaml
version: '3.8'

services:
  freqtrade:
    image: freqtradeorg/freqtrade:latest
    container_name: crypto-trader
    restart: unless-stopped
    volumes:
      # 配置持久化
      - ./custom-config:/freqtrade/user_data/config
      # UI 定制覆盖
      - ./custom-ui:/freqtrade/user_data/ui
      # 数据持久化
      - ./data:/freqtrade/user_data/data
      - ./logs:/freqtrade/user_data/logs
    environment:
      - TZ=Asia/Shanghai
      # 交易所 API（通过 .env 注入）
      - OKX_API_KEY=${OKX_API_KEY}
      - OKX_SECRET=${OKX_SECRET}
      - OKX_PASSPHRASE=${OKX_PASSPHRASE}
      # Telegram 通知（可选）
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
      # Flask 配置（指向 custom-ui）
      - FLASK_TEMPLATE_DIR=/freqtrade/user_data/ui/templates
      - FLASK_STATIC_DIR=/freqtrade/user_data/ui/static
    command: >
      trade
      --strategy MA交叉策略
      --config /freqtrade/user_data/config/config.json
      --userdir /freqtrade/user_data
      --db-url sqlite:///user_data/tradesv3.sqlite
    ports:
      - "8080:8080"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### 6.2 启动步骤

```bash
# 1. 克隆项目结构
mkdir -p custom-config/strategies
mkdir -p custom-ui/templates
mkdir -p custom-ui/static/css
mkdir -p data logs

# 2. 复制默认配置（参考）
docker run --rm freqtradeorg/freqtrade:latest config --export > custom-config/config.json
# 然后编辑 custom-config/config.json，中文化并调整参数

# 3. 复制官方模板（作为修改基础）
# 先启动一次容器，复制模板出来
docker run --rm -v $(pwd)/custom-ui:/tmp/ui freqtradeorg/freqtrade:latest \
    bash -c "cp -r /freqtrade/freqtrade/web/templates/* /tmp/ui/templates/ && cp -r /freqtrade/freqtrade/web/static/* /tmp/ui/static/"

# 4. 修改 custom-ui/ 下的模板和样式（中文化、移动端适配）

# 5. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 OKX_API_KEY 等

# 6. 启动
docker-compose up -d

# 7. 访问
# http://localhost:8080
# 默认无认证（可在 config.json 配置 webadmin 或通过 Nginx 加一层 Basic Auth）
```

---

## 7. 升级维护策略

### 7.1 升级 freqtrade 版本

```bash
# 1. 拉取新镜像
docker-compose pull

# 2. 重启服务
docker-compose up -d
```

**注意**：
- 因为核心代码在镜像内，升级镜像即升级 freqtrade
- `custom-config/` 和 `custom-ui/` 保持不变
- 如果新版本 freqtrade 有模板变更，需对比新旧模板，合并到 `custom-ui/`（使用 diff 工具）

### 7.2 模板变更检查脚本

```bash
#!/bin/bash
# 生成模板差异报告
docker run --rm freqtradeorg/freqtrade:latest bash -c "ls /freqtrade/freqtrade/web/templates/" > /tmp/new_templates.txt
ls custom-ui/templates/ > /tmp/old_templates.txt

echo "=== 新增模板（需要复制并定制）==="
comm -13 /tmp/old_templates.txt /tmp/new_templates.txt

echo "=== 删除模板（可移除自定义）==="
comm -23 /tmp/old_templates.txt /tmp/new_templates.txt

echo "=== 修改模板（需 diff 对比）==="
comm -12 /tmp/old_templates.txt /tmp/new_templates.txt | while read tpl; do
    echo "--- $tpl ---"
    docker run --rm freqtrade freqtrade cat /freqtrade/freqtrade/web/templates/$tpl > /tmp/new.tpl
    diff -u custom-ui/templates/$tpl /tmp/new.tpl || true
done
```

---

## 8. 风险提示与回滚

### 8.1 风险

| 风险 | 说明 | 缓解措施 |
|------|------|----------|
| 模板兼容性 | freqtrade 升级可能改变模板变量 | 升级前 diff 检查，保留旧版本备份 |
| 配置迁移 | 新版本可能新增/删除配置项 | 阅读官方 CHANGELOG，逐步迁移 |
| 数据格式 | 数据库 schema 可能变更 | 使用官方 `freqtrade migrate` 工具 |
| 自定义覆盖失效 | 某些功能可能绕过模板系统 | 测试所有关键页面，必要时补丁 |

### 8.2 回滚方案

1. **快速回退到原版**：
   ```bash
   # 停止定制容器
   docker-compose down
   # 使用官方配置启动纯原版
   docker run -d \
     -v $(pwd)/data:/freqtrade/user_data/data \
     -e OKX_API_KEY=... \
     freqtradeorg/freqtrade:latest trade --config /freqtrade/user_data/config/config.json
   ```

2. **保留旧版定制**：
   - `custom-config/` 和 `custom-ui/` 使用 Git 版本控制
   - 任何修改前先提交，可随时回退

---

## 9. 测试验收标准

见 `docs/test_report_freqtrade_custom.md` 模板。

---

## 10. 后续优化方向

- 实时 WebSocket 价格推送（原版已有，可增强）
- 多策略并行（原版支持，配置即可）
- 自定义通知渠道（钉钉、企业微信）
- 性能监控（Prometheus 指标导出）

---

**文档版本**: v1.0  
**最后更新**: 2025-03-05  
**作者**: 产品经理 (PM)
