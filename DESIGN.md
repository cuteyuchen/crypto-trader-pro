# Pro 版自动交易系统设计文档

## 概述

基于 Freqtrade 核心功能，但更简洁、中文友好、错误清晰。目标是：
- ✅ 支持 Freqtrade 90% 核心功能
- ✅ 中文文档和错误提示
- ✅ 一次部署，稳定运行
- ✅ 易于监控和管理

---

## 核心功能模块

### 1. 交易所网关 (Exchange Gateway)

**职责**：统一对接多个交易所，屏蔽差异

**支持交易所**：
- Binance (现货/永续)
- OKX (现货/永续)
- Bybit (现货/永续)
- 扩展：Coinbase, Kraken, Huobi

**功能**：
- 自动重连机制
- 速率限制管理
- 订单状态追踪
- 账户余额同步
- 手续费计算

**技术**：CCXT（100+ 交易所支持）

---

### 2. 策略引擎 (Strategy Engine)

**策略类型**：

| 策略 | 描述 | 参数 |
|------|------|------|
| 均线交叉 | MA5/MA20 金叉死叉 | fast, slow |
| RSI 超买超卖 | RSI < 30 买入, > 70 卖出 | rsi_period, oversold, overbought |
| 布林带突破 | 价格突破上轨/下轨 | bb_period, bb_std |
| MACD 信号 | MACD 金叉/死叉 + 柱状图 | fast, slow, signal |
| 多因子组合 | 多个指标加权打分 | weights={} |

**策略配置**（JSON）：
```json
{
  "name": "均线RSI组合",
  "type": "multi",
  "rules": [
    {
      "indicator": "ma_cross",
      "params": {"fast": 5, "slow": 20},
      "action": "buy"
    },
    {
      "indicator": "rsi",
      "params": {"period": 14},
      "condition": "<30",
      "action": "buy"
    },
    {
      "indicator": "ma_cross",
      "params": {"fast": 5, "slow": 20},
      "action": "sell"
    },
    {
      "indicator": "rsi",
      "params": {"period": 14},
      "condition": ">70",
      "action": "sell"
    }
  ]
}
```

**自定义策略**：支持 Python 脚本，继承 `BaseStrategy` 类，实现 `on_bar()` 方法。

---

### 3. 风险管理 (Risk Manager)

**仓位控制**：
- 固定比例（每次交易总资产的 2%）
- 固定金额（每次买入 $100）
- 凯利公式（优化赔率）

**止损止盈**：
- 固定百分比止损（-5%）
- 移动止损（最高点回撤 3%）
- 跟踪止盈（ATR 倍数）

**全局风控**：
- 日内最大亏损限额（-10% 暂停交易）
- 单日交易次数限制
- 交易所等级限制（避免影响正常交易）

---

### 4. 订单执行 (Order Executor)

**订单类型**：
- 限价单（LIMIT）
- 市价单（MARKET）
- 冰山订单（ICEberg）
- 隐藏订单（POST_ONLY）

**执行策略**：
- 立即成交（市价）
- 逐步建仓（分单）
- 订单簿分析（最优价格）
- 滑点控制（最大滑点 0.1%）

**状态追踪**：
- pending → partially_filled → filled
- canceled → rejected
- timeout 自动取消

---

### 5. 数据层 (Data Layer)

**数据源**：
- CCXT 实时 K 线（1m, 5m, 15m, 1h, 4h, 1d）
- 交易历史（通过 CCXT fetch_my_trades）
- 实时 Ticker（价格推送）

**本地缓存**：
- SQLite 数据库
- 缓存 30 天 K 线（可配置）
- 自动清理旧数据

**数据质量**：
- 缺失数据检测（自动重拉）
- 异常值过滤（价格突变 > 50% 报警）
- 时间对齐（统一时区 UTC）

---

### 6. 回测引擎 (Backtesting)

**功能**：
- 历史数据加载
- 策略逐 bar 执行
- 模拟撮合（考虑滑点、手续费）
- 性能统计（总收益、夏普、最大回撤、胜率）

**优化**：
- 网格搜索（参数优化）
- 随机搜索（快速测试）
- WAFA（Walk-Forward Analysis）

**输出**：
- 收益曲线图（matplotlib）
- 交易记录（CSV）
- 性能指标（JSON）

---

### 7. Web 看板 (Dashboard)

**实时数据**：
- 当前持仓、成本、盈亏
- 账户总资产、可用余额
- 最近 10 笔交易
- 策略信号（实时 K 线图）

**监控**：
- 运行状态（在线/离线）
- 错误日志（滚动显示）
- QQ/Telegram 通知历史
- 今日交易统计

**管理**：
- 暂停/恢复交易
- 手动平仓
- 修改策略参数（热更新）
- 导出数据

**技术**：
- Flask (后端 API)
- Chart.js (前端图表)
- WebSocket (实时推送)

---

### 8. 通知系统 (Notifications)

**渠道**：
- QQ Bot（私聊）
- Telegram Bot
- 邮件（可选）
- Webhook（企业微信/钉钉）

**事件**：
- 🟢 开仓：买入 BTC，价格 $50,000，数量 0.01
- 🔴 平仓：卖出 BTC，盈利 $50
- ⚠️ 报警：连接交易所失败
- 📊 日报：今日收益 +2.3%

**频率控制**：
- 重要事件立即通知
- 非重要事件聚合（每 30 分钟一次）
- 勿扰模式（深夜不打扰）

---

### 9. 自改进模块 (Self-Improving)

**集成 self-improving-agent 技能**：
- 记录每笔交易的结果
- 策略表现评估（胜率、盈亏比、夏普）
- 参数自动优化（基于历史表现）
- 异常检测（连续亏损报警）

**学习内容**：
- "RSI 参数 14 效果最好，8 太敏感"
- "BTC 波动大，止损要设 8% 而不是 5%"
- "周一早上波动高，仓位减半"

**自动调整**：
- 识别失效策略（近 10 笔全亏 → 暂停）
- 动态调整仓位（表现好时 +20%）
- 参数微调（每周一次网格搜索）

---

## 部署架构

```
┌─────────────────────────────────────────┐
│          Docker Compose                 │
├─────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐             │
│  │ Trader  │  │   DB    │  SQLite    │
│  │  Core   │◄─►│         │◄─────────►│
│  └────┬────┘  └─────────┘             │
│       │                                │
│  ┌────▼────┐  ┌─────────┐             │
│  │ Web     │  │  Redis  │  缓存      │
│  │ Dashboard│  │         │            │
│  └────┬────┘  └─────────┘             │
│       │                                │
│  ┌────▼────┐                           │
│  │  QQ     │  Notifier                  │
│  │  Bot    │                           │
│  └─────────┘                           │
└─────────────────────────────────────────┘
```

**一键启动**：
```bash
git clone https://github.com/yourname/crypto-trader-pro.git
cd crypto-trader-pro
cp .env.example .env  # 填入交易所 API Key
docker-compose up -d
```

---

## 配置文件结构

```
config/
├── exchanges/
│   ├── binance.json        # API Key, 交易对白名单
│   └── okx.json
├── strategies/
│   ├── ma_rsi.json         # 策略配置
│   └── custom.py           # 自定义策略脚本
├── risk.json               # 风控规则
├── notifications.json      # 通知设置
└── dashboard.json          # Web 看板端口
```

**示例 exchanges/binance.json**：
```json
{
  "name": "binance",
  "api_key": "your_key",
  "api_secret": "your_secret",
  "testnet": true,
  "pairs": ["BTC/USDT", "ETH/USDT"],
  "leverage": 10,
  "margin_type": "isolated"
}
```

---

## 错误处理理念（解决 Freqtrade 痛点）

| 场景 | Freqtrade | 我们的系统 |
|------|-----------|-----------|
| API Key 无效 | 复杂 stack trace | "❌ Binance API 认证失败，请检查 api_key/api_secret" |
| 网络超时 | 默默重试 10 次 | "⚠️ 连接 Binance 超时，第 3 次重连中..." |
| 余额不足 | 抛出异常 | "💰 余额不足：需要 $100，当前 $50" |
| 配置错误 | YAML 解析错误 | "📄 config/strategies/ma_rsi.json 第 12 行：缺少 'fast' 参数" |
|  crashes | 进程退出，无提示 | 自动重启 + "🔄 程序异常退出，正在重启（第 2 次）" |

**错误分级**：
- 🚨 致命：停止交易，立即通知
- ⚠️ 警告：记录日志，继续运行
- 💬 信息：调试用，无需通知

---

## 开发计划

**Week 1**：核心框架
- Day 1-2：Exchange Gateway（对接 Binance）
- Day 3-4：策略引擎（基础框架 + 2 个策略）
- Day 5：数据层（SQLite + CCXT）

**Week 2**：执行与风控
- Day 1-2：Order Executor（订单管理）
- Day 3-4：Risk Manager（仓位、止损）
- Day 5：配置文件 + 命令行参数

**Week 3**：Web 看板 + 通知
- Day 1-3：Flask Dashboard（实时图表）
- Day 4-5：通知系统（QQ + Telegram）

**Week 4**：自改进 + 优化
- Day 1-2：集成 self-improving-agent
- Day 3-4：回测引擎（简化版）
- Day 5：测试 + 文档 + Docker 镜像

---

## 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| 语言 | Python 3.11 | 库丰富，易读，CCXT 支持好 |
| 交易所API | CCXT | 100+ 交易所统一接口 |
| 数据库 | SQLite | 零配置，单文件，够用 |
| Web框架 | Flask | 轻量，快速 |
| 图表 | Chart.js | 轻量，效果好 |
| 部署 | Docker Compose | 一键启动，环境隔离 |
| 日志 | structlog + 按天轮转 | 易读，易排查 |
| 监控 | Prometheus + Grafana（可选） | 专业级 |

---

## 与 Freqtrade 对比

| Feature | Freqtrade | Our Pro |
|---------|-----------|---------|
| 语言 | 英文文档 | 全中文 📚 |
| 配置 | YAML 复杂嵌套 | JSON 简洁 ✅ |
| 错误提示 | 技术术语 | 人话 😊 |
| 部署 | 多条命令 | docker-compose up ✅ |
| 依赖 | 50+ 包 | 15 个核心包 |
| 回测 | 超强 | 简化版（够用） |
| Web UI | 需插件 | 内置 ✅ |
| 通知 | Telegram | QQ + Telegram ✅ |
| 自改进 | ❌ | ✅ 集成 |

---

## 下一步

1. 确认设计（蟹老板拍板）
2. 创建 GitHub 仓库
3. 开始 Week 1 开发
4. 每日 demo（进度同步）
5. Week 4 交付测试版

**预估时间**：2-3 周（全职开发）  
**预估代码量**：~5000 行 Python  
**测试环境**：先跑 Binance Testnet

---

**Ready to build?** 🚀
