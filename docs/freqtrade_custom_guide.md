# Freqtrade 中文化与移动端适配指南

## 概述

本指南说明如何部署和使用基于 freqtrade 的中文版加密货币交易系统，并进行移动端适配。

---

## 目录

1. [架构说明](#架构说明)
2. [目录结构](#目录结构)
3. [快速开始](#快速开始)
4. [配置说明](#配置说明)
5. [移动端 UI](#移动端-ui)
6. [自定义策略](#自定义策略)
7. [升级维护](#升级维护)
8. [故障排除](#故障排除)

---

## 架构说明

- **核心引擎**: freqtrade (官方镜像，不修改)
- **定制层**: `custom-config/` (配置 + 策略) + `custom-ui/` (模板 + 静态资源)
- **数据持久化**: `data/` (数据库), `logs/` (日志)
- **部署**: Docker Compose 一键启动

---

## 目录结构

```
PROJECTS/crypto-trader-pro/
├── custom-config/
│   ├── config.json                # 主配置（中文化）
│   └── strategies/
│       └── ma_cross_cn.py         # 中文策略示例
├── custom-ui/
│   ├── templates/
│   │   ├── layout.html            # 布局模板
│   │   ├── navbar.html            # 导航栏
│   │   ├── overview.html          # 看板
│   │   ├── trades.html            # 交易
│   │   ├── strategies.html        # 策略管理
│   │   ├── backtest.html          # 回测+优化
│   │   ├── config.html            # 配置
│   │   └── logs.html              # 日志
│   ├── static/
│   │   ├── css/
│   │   │   └── mobile.css         # 移动端样式
│   │   └── js/
│   │       └── app.js             # 交互脚本
├── data/                          # 持久化数据 (自动创建)
├── logs/                          # 日志文件 (自动创建)
├── docker-compose.freqtrade.yml   # Docker 编排
├── .env.example                   # 环境变量模板
└── README_FREQTRADE.md            # 本文档
```

---

## 快速开始

### 1. 环境准备

- Docker 20.10+
- Docker Compose 2.0+
- 可用的加密货币交易所账户（OKX/Binance）

### 2. 克隆或使用现有项目

本定制层位于 `PROJECTS/crypto-trader-pro/`。

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 API Key
```

`.env` 示例：

```bash
OKX_API_KEY=your_api_key
OKX_SECRET=your_secret
OKX_PASSPHRASE=your_passphrase
TELEGRAM_BOT_TOKEN=123:ABC  # 可选
TELEGRAM_CHAT_ID=123456789
```

### 4. 启动服务

```bash
# 启动容器
docker-compose -f docker-compose.freqtrade.yml up -d

# 查看日志
docker-compose -f docker-compose.freqtrade.yml logs -f freqtrade

# 停止服务
docker-compose -f docker-compose.freqtrade.yml down
```

### 5. 访问 Web UI

打开浏览器访问：**http://localhost:8080**

默认无需登录（生产环境建议添加 Nginx + Basic Auth）。

---

## 配置说明

### 主配置 `custom-config/config.json`

关键字段：

| 字段 | 说明 | 默认 |
|------|------|------|
| `dry_run` | 模拟模式（不真钱） | `true` |
| `dry_run_wallet` | 模拟余额 | `10000` |
| `exchange.name` | 交易所名称 | `"okx"` |
| `strategy` | 策略类名（需与文件名匹配） | `"MA交叉策略"` |
| `max_open_trades` | 最大同时持仓数 | `3` |
| `stoploss` | 止损比例（负值） | `-0.05` |
| `roi` | 阶梯止盈 | `{"0": 0.10}` |

**注意**: 生产环境请先长时间运行 dry-run 验证策略。

### 策略配置

策略文件放在 `custom-config/strategies/`，类名必须与 `config.json` 中 `strategy` 字段一致。

示例：`ma_cross_cn.py` 定义 `class MA交叉策略(IStrategy)`。

策略参数通过 `self.fast_period = 10` 等类属性定义，或在 `populate_indicators` 中动态计算。

---

## 移动端 UI

### 设计特点

- ✅ 触摸友好：按钮 ≥ 44px
- ✅ 响应式布局：横向滚动表格
- ✅ 汉堡菜单导航
- ✅ 暗色模式支持
- ✅ 安全区域适配

### 覆盖机制

`custom-ui/templates/` 中的文件会覆盖 freqtrade 默认模板（通过 `FLASK_TEMPLATE_DIR` 环境变量）。

`custom-ui/static/` 中的 CSS/JS 通过 `FLASK_STATIC_DIR` 加载。

### 页面清单

| 页面 | 模板 | 主要特性 |
|------|------|----------|
| 看板 | overview.html | 状态卡片、图表、持仓列表 |
| 交易 | trades.html | 快速下单、活跃订单 |
| 策略 | strategies.html | 参数编辑、重载 |
| 回测 | backtest.html | 回测配置、网格搜索 |
| 配置 | config.html | 系统设置 |
| 日志 | logs.html | 日志查看 |

---

## 自定义策略

### 编写策略

```python
from freqtrade.strategy import IStrategy
from talib.abstract import SMA
import pandas as pd

class 我的策略(IStrategy):
    timeframe = "5m"
    stoploss = -0.05
    minimal_roi = {"0": 0.10}

    # 自定义参数
    my_param = 20

    def populate_indicators(self, df, md):
        df['ma'] = SMA(df['close'], timeperiod=self.my_param)
        return df

    def populate_buy_trend(self, df, md):
        df.loc[df['ma'] < df['close'], 'buy'] = 1
        return df

    def populate_sell_trend(self, df, md):
        df.loc[df['ma'] > df['close'], 'sell'] = 1
        return df
```

### 启用策略

1. 将策略文件放入 `custom-config/strategies/`
2. 修改 `config.json` 的 `strategy` 字段为 `"我的策略"`（类名）
3. 重启容器或使用 API 重载策略

---

## 升级维护

### 升级 freqtrade 版本

```bash
# 编辑 docker-compose.freqtrade.yml，修改 image 标签
# 例如: image: freqtradeorg/freqtrade:2024.1

docker-compose -f docker-compose.freqtrade.yml pull
docker-compose -f docker-compose.freqtrade.yml up -d
```

**注意**：大版本升级可能带来配置变更，请先阅读官方发布说明。

### 模板冲突解决

如果新版 freqtrade 修改了模板变量，需要：
1. 启动一个临时容器，导出新模板
2. 使用 diff 工具对比 `custom-ui/templates/`
3. 手动合并修改到自定义模板

**保持自定义模板尽量简单**，只覆盖必要部分，减少冲突概率。

### 数据备份

```bash
# 备份数据库
cp data/tradesv3.sqlite ~/backup/

# 备份配置
tar czf custom-config-backup.tar.gz custom-config/
```

---

## 故障排除

### 问题：容器启动失败，提示找不到模板

**解决方案**：确认 `FLASK_TEMPLATE_DIR` 和 `FLASK_STATIC_DIR` 环境变量设置正确，且目录内文件存在。

### 问题：Web UI 样式未加载

**解决方案**：
- 检查 `custom-ui/static/css/mobile.css` 路径
- Flask 静态文件路径大小写敏感
- 清除浏览器缓存

### 问题：策略未生效

**解决方案**：
- 确认 `config.json` 中的 `strategy` 字段与类名完全一致（包含中文字符）
- 查看日志 `/logs/freqtrade.log` 是否有加载错误
- 使用 API `/api/strategy/reload` 重载

### 问题：移动端表格错位

**解决方案**：
- 确保 `.table-container` 有 `overflow-x: auto`
- 表格 `min-width` 足够大（如 600px）
- 检查 `mobile.css` 是否加载

---

## 附录

### API 参考

- `GET /api/status` - 系统状态
- `GET /api/trades` - 交易记录
- `GET /api/strategies` - 策略列表
- `POST /api/strategy/reload` - 重载策略
- `POST /api/backtest` - 运行回测
- `POST /api/backtest/optimize` - 参数优化

详见 `docs/api_reference.md`。

---

**版本**: 1.0.0  
**基于 freqtrade 版本**: latest  
**维护**: 小螃蟹 🦀
