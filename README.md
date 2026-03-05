# Crypto Trader Pro 🦀

> 基于 OpenClaw 自改进理念的 Pro 级加密货币自动交易系统

## ✨ 特性

- ✅ **双模式模拟交易**：本地模拟 + 币安 Testnet（可无缝切换到 Live）
- ✅ **实时 WebSocket 价格**：低延迟，多交易所支持
- ✅ **中文友好**：所有日志、错误提示、文档均为中文
- ✅ **一键部署**：Docker + docker-compose，30 秒启动
- ✅ **策略热更新**：修改 JSON 配置无需重启
- ✅ **内置策略**：MA5/MA20 交叉、RSI、布林带（持续增加）
- ✅ **风控完备**：仓位限制、止损熔断、每日限额
- ✅ **Web 看板**：实时持仓、盈亏、交易记录
- ✅ **QQ/Telegram 通知**：开仓/平仓/报警实时推送
- ✅ **自改进学习**：记录策略表现，持续优化参数

---

## 🚀 快速开始

### 1. 克隆项目（蟹老板创建仓库后 pull 下来）

```bash
cd ~/.openclaw/workspace/PROJECTS
git clone <你的仓库URL> crypto-trader-pro
cd crypto-trader-pro
cp .env.example .env  # 编辑 .env 填入配置
```

### 2. 配置

编辑 `config/modes.json`：

```json
{
  "mode": "local",         // local | testnet | live
  "exchange": "binance",   // 数据源交易所：binance | okx (仅影响 WS 行情)
  "initial_balance": 10000,
  "symbols": ["BTC/USDT"]
}
```

编辑 `.env` 文件（testnet/live 模式需填写 API Key）：

```bash
# Binance Testnet/Live
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_secret_here
BINANCE_TESTNET=true   # testnet 模式设为 true，live 设为 false

# OKX Testnet/Live
OKX_API_KEY=your_api_key_here
OKX_API_SECRET=your_secret_here
OKX_PASSPHRASE=your_passphrase   # OKX 需要
OKX_TESTNET=true

# 代理配置（如需要）
# HTTP_PROXY=http://127.0.0.1:7890
# HTTPS_PROXY=http://127.0.0.1:7890
# ALL_PROXY=http://127.0.0.1:7890
```

### 策略配置

编辑 `config/modes.json` 选择策略：

```json
{
  "strategy": "ma_cross"   // ma_cross | rsi
}
```

**MA 交叉策略** (`config/strategies/ma_cross.json`)：
```json
{
  "name": "MA5_MA20_Cross",
  "symbol": "BTC/USDT",
  "timeframe": "1m",
  "type": "ma_cross",
  "params": {
    "fast_period": 5,
    "slow_period": 20
  },
  "position_size": 0.2,
  "stop_loss_pct": 0.05,
  "take_profit_pct": 0.10
}
```

**RSI 策略** (`config/strategies/rsi.json`)：
```json
{
  "name": "RSI_14_70_30",
  "symbol": "BTC/USDT",
  "timeframe": "1m",
  "type": "rsi",
  "rsi_period": 14,
  "oversold": 30,
  "overbought": 70,
  "position_size": 0.2
}
```

### 3. 启动（Docker）

```bash
docker-compose up -d
```

查看日志：
```bash
docker logs -f crypto-trader-pro
```

### 4. 访问看板

打开浏览器：http://localhost:5000

看板特点：
- **响应式设计**：支持电脑、平板、手机访问（自动适配小屏幕）
- **实时数据**：每 5 秒自动刷新
- **显示内容**：
  - 运行状态（模式、策略状态、K线数量）
  - 账户余额（USDT）
  - 今日盈亏
  - 当前持仓（交易对、方向、数量、入场价、当前价、未实现盈亏）
  - 最近交易记录（时间、方向、数量、价格、手续费、盈亏）
  - 余额走势图（基于最近交易）

> 💡 **移动端访问**：界面已针对小屏幕优化，直接手机浏览器输入 `http://你的IP:5000` 即可访问（确保容器端口映射正确）。

---

## 📊 运行效果（本地模拟）

启动后你会看到：

```
INFO - 连接到 Binance WS: wss://stream.binance.com:9443/ws/btcusdt@kline_1m
INFO - Binance WS 已连接
INFO - 收到价格: BTCUSDT = $50320.50
INFO - [状态] USDT余额: $10000.00, 未实现盈亏: $0.00, 持仓数: 0
...
INFO - 策略信号: {'action': 'buy', 'reason': 'MA金叉'}
INFO - 买入成功: 数量 0.039682, 均价 $50320.50
INFO - 通知已记录: open_position - 开仓买入
INFO - [状态] USDT余额: $8000.00, 未实现盈亏: $0.00, 持仓数: 1
...
INFO - 策略信号: {'action': 'sell', 'reason': 'MA死叉'}
INFO - 卖出成功: 数量 0.039682, 盈亏 $123.45
INFO - 通知已记录: close_position - 平仓卖出
INFO - [状态] USDT余额: $8123.45, 未实现盈亏: $0.00, 持仓数: 0
```

---

## 🔧 三种模式

| 模式 | 说明 | 资金 | 订单执行 |
|------|------|------|----------|
| **local** | 本地模拟 | 虚拟 $10,000 | 仅更新数据库 |
| **testnet** | 币安测试网 | 币安提供的测试 USDT | 真实撮合但无风险 |
| **live** | 实盘 | 你的真钱 | 真实交易 |

切换只需修改 `.env` 和 `config/modes.json`。

---

## 📁 目录结构

```
crypto-trader-pro/
├── src/
│   ├── ws/binance_ws.py        # Binance WebSocket 客户端
│   ├── engine/
│   │   ├── strategy_engine.py  # 策略引擎（多策略支持）
│   │   ├── executor.py         # 订单执行器（三模式）
│   │   └── risk_manager.py     # 风控模块
│   ├── data/simulation_db.py   # 本地模拟数据库
│   ├── dashboard/
│   │   ├── app.py              # Flask Web 看板后端
│   │   ├── templates/
│   │   │   └── index.html      # 前端页面
│   │   └── static/
│   │       └── app.js          # 前端逻辑
│   └── main.py                 # 程序主入口
├── config/                     # 配置文件
│   ├── modes.json
│   ├── strategies/
│   │   └── ma_cross.json
│   ├── exchanges/
│   │   ├── binance.json
│   │   └── okx.json
│   ├── simulation/
│   │   └── local.json
│   └── risk.json
├── tests/                      # 单元测试
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

---

## 🛠️ 开发进度

- [x] 项目骨架
- [x] WebSocket Binance 客户端
- [x] WebSocket OKX 客户端（推荐使用）
- [x] 本地模拟数据库（持仓/余额/交易）
- [x] 策略引擎 + MA 交叉策略
- [x] 策略引擎 + RSI 策略
- [x] 策略引擎 + 布林带策略
- [x] 策略引擎 + MACD 策略
- [x] 订单执行器（local 模式）
- [x] 订单执行器（testnet/live 模式）✅ CCXT 集成
- [x] 风控管理器
- [x] Docker 部署
- [x] Web 看板（Flask + Chart.js）✅ 移动端适配
- [x] QQ Bot 通知集成 ✅ 通过 HEARTBEAT 自动分发
- [x] 多策略支持（配置切换）
- [x] 自改进学习集成（性能分析 + 参数建议）

✅ **核心功能全部完成！**

预计完成时间：0.5 天（已全部完成）

---

## 🔍 技术栈

- **Python 3.11** + asyncio
- **CCXT** - 交易所 API 统一层
- **websockets** - WebSocket 客户端
- **SQLite + SQLAlchemy** - 数据存储
- **Flask + Chart.js** - Web 看板
- **Docker Compose** - 部署

---

## 🧪 测试建议

1. **本地模拟**：先用 `mode="local"` 跑 24 小时，观察策略表现
2. **Testnet**：切换到 Binance Testnet，验证订单执行
3. **小额实盘**：投入少量资金，测试真网环境

---

## 🌐 网络与移动端

### 移动端访问
看板已**完全响应式**，手机浏览器可直接访问 `http://服务器IP:5000`。
- 自动适配小屏幕（单列布局）
- 数据每 5 秒刷新，保持实时
- 建议使用 Chrome/Safari 移动浏览器

### WebSocket 连接问题
如果你遇到 `HTTP 451` 或其他连接错误，说明当前网络无法直连交易所。解决方案：

1. **配置代理**（推荐）：在 `.env` 或 Docker 中设置 `HTTP_PROXY` / `HTTPS_PROXY`
2. **切换交易所**：尝试 `exchange: "okx"`（部分网络环境可能不同）
3. **本地网络**：确保服务器/容器可访问外网（443 端口）

Docker 代理设置示例（docker-compose.yml）：
```yaml
services:
  trader:
    environment:
      - HTTP_PROXY=http://127.0.0.1:7890
      - HTTPS_PROXY=http://127.0.0.1:7890
```

---

## ⚠️ 风险提示

- 交易有风险，投资需谨慎
- 本软件仅供研究和学习使用
- 使用前务必充分测试
- 不要投入无法承受损失的资金

---

## 📚 自改进学习系统

系统包含自动学习框架：

### 性能分析
- 每日自动分析策略近期表现（7天窗口）
- 指标：胜率、平均盈亏、总盈亏、夏普比率、最大回撤
- 结果写入日志并发送通知

### 参数优化建议
- 基于表现自动给出参数调整方向
- **支持策略**：
  - RSI：调整超买/超卖阈值
  - MA：调整快慢线周期
  - 布林带：调整标准差倍数和周期
  - MACD：调整信号线平滑周期

### 半自动应用
建议调整后，可手动更新策略配置文件并重启。未来计划自动 A/B 测试。

示例通知：
```
🧠 策略学习报告
策略: RSI_14_70_30
评估: 7天, 15笔交易
胜率: 53.3%, 总盈亏: $123.45
建议: RSI 胜率偏低，扩大超买超卖阈值至 25/75
```
