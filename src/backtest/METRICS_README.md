# 回测指标计算功能

## 概述

本模块提供了详细、全面的回测指标计算功能，包括 10+ 项关键指标，帮助评估交易策略的绩效和风险。

## 文件结构

```
src/backtest/
├── engine.py          # 回测引擎（原有）
├── metrics.py         # 新增：指标计算器（BacktestMetrics 类）
└── example_usage.py  # 新增：使用示例
```

## API 变更

`/api/backtest` 端点现在返回增强的响应，包含 `metrics` 字段，详细指标如下：

### 基础信息
- `strategy`: 策略名称
- `initial_balance`: 初始余额
- `final_balance`: 最终余额
- `equity_curve`: 资产曲线（时间序列）
- `trades`: 交易记录列表

### 详细指标 (`metrics` 对象)

#### 1. 收益率指标
- `total_return_pct`: 总收益率（百分比）
- `annual_return_pct`: 年化收益率（百分比）
- `backtest_duration_days`: 回测天数

#### 2. 风险指标
- `max_drawdown_pct`: 最大回撤（百分比）
- `max_drawdown_days`: 最大回撤持续天数（可选）
- `sharpe_ratio`: 夏普比率（年化，无风险利率=0%）
- `sharpe_calculation`: 夏普比率计算详情，包含：
  - `method`: 计算方法（annualized）
  - `period`: 周期（daily）
  - `risk_free_rate`: 无风险利率

#### 3. 交易表现
- `total_trades`: 总交易数（卖出平仓计数）
- `win_rate_pct`: 胜率（百分比）
- `profit_loss_ratio`: 盈亏比（总盈利 / 总亏损）
- `trades_per_day`: 交易频率（日均交易次数）
- `avg_holding_days`: 平均持仓时间（天）

#### 4. 盈亏分布
- `profit_distribution`: 盈利分布
  - `count`: 盈利交易数量
  - `total`: 总盈利金额
  - `average`: 平均每笔盈利
  - `max`: 最大单笔盈利
  - `median`: 盈利中位数

- `loss_distribution`: 亏损分布（结构相同）

## 使用方法

### 1. 通过 Web API 调用

**请求：**
```http
POST /api/backtest
Content-Type: application/json

{
  "strategy": "ma_cross",
  "days": 30,
  "initial_balance": 10000
}
```

**响应：**
```json
{
  "strategy": "ma_cross",
  "initial_balance": 10000.0,
  "final_balance": 10500.0,
  "equity_curve": [...],
  "trades": [...],
  "metrics": {
    "total_return_pct": 5.0,
    "annual_return_pct": 60.0,
    "max_drawdown_pct": 2.5,
    "max_drawdown_days": 3.2,
    "sharpe_ratio": 1.85,
    "sharpe_calculation": {
      "method": "annualized",
      "period": "daily",
      "risk_free_rate": 0.0
    },
    "win_rate_pct": 55.0,
    "total_trades": 20,
    "profit_loss_ratio": 1.4,
    "profit_distribution": {...},
    "loss_distribution": {...},
    "trades_per_day": 0.67,
    "avg_holding_days": 2.5,
    "backtest_duration_days": 30.0
  }
}
```

### 2. 直接使用 Python 类

```python
from src.backtest.metrics import BacktestMetrics

# 准备数据
equity_curve = [
    {'time': '2025-01-01T00:00:00', 'equity': 10000.0},
    {'time': '2025-01-02T00:00:00', 'equity': 10100.0},
    # ... 更多数据
]

trades = [
    {'side': 'buy', 'time': '2025-01-01T10:00:00', 'price': 100, 'quantity': 1},
    {'side': 'sell', 'time': '2025-01-02T14:00:00', 'price': 105, 'quantity': 1, 'pnl': 5},
    # ... 更多交易
]

# 计算指标
metrics = BacktestMetrics.calculate(equity_curve, trades)

# 查看结果
print(f"总收益率: {metrics['total_return_pct']}%")
print(f"夏普比率: {metrics['sharpe_ratio']}")
print(f"胜率: {metrics['win_rate_pct']}%")
```

## 指标计算说明

### 年化收益率

基于回测总收益率和时间跨度，使用复利公式：

\[
\text{年化收益率} = \left(1 + \frac{\text{总收益率}}{100}\right)^{365 / \text{天数}} - 1
\]

### 最大回撤

从权益曲线计算 peak-to-trough 的最大跌幅：

```
最大回撤 = max( (峰值 - 低值) / 峰值 )
```

同时记录回撤持续时间（从峰值到恢复或结束的天数）。

### Sharpe 比率

假设无风险利率为 0%，基于资产曲线的日收益率计算：

1. 将权益曲线转换为日频（取每日最后一个值）
2. 计算日收益率序列
3. 年化 Sharpe = (mean(日收益率) / std(日收益率)) × √252

### 胜率

仅针对已平仓交易（卖出）计算：

\[
\text{胜率} = \frac{\text{盈利交易数量}}{\text{总交易数量}} \times 100\%
\]

### 盈亏比

\[
\text{盈亏比} = \frac{\text{总盈利}}{\text{总亏损}}
\]

当没有亏损交易时返回 `null`，当有盈利但无亏损时返回 `Infinity`。

### 交易频率

\[
\text{交易频率} = \frac{\text{平仓交易数量}}{\text{回测天数}}
\]

如果回测时间不足一天，按实际时间比例折算。

### 平均持仓时间

根据买卖交易配对的时间差计算，要求：
- 交易列表包含 buy 和 sell 记录
- 交易按时间顺序排列
- 买入和卖出成对出现

持仓时间 = 卖出时间 - 买入时间（以天为单位）。

## 数据要求

### equity_curve
- 列表格式，每个元素为字典
- 必须包含字段：`time` (支持 str/datatime/timestamp), `equity` (float)
- 数据应覆盖完整的回测周期

### trades
- 列表格式，每个元素为交易记录字典
- 必须包含字段：`side` ('buy' 或 'sell'), `time` (同上), `price`, `quantity`
- 平仓交易（卖出）应包含 `pnl` 字段（float）
- 时间应已排序（函数内部会重新排序）

## 示例代码

见 `example_usage.py`，包含两种使用方式：
1. 基本用法：直接调用 `BacktestMetrics.calculate()`
2. API 整合：模拟 `/api/backtest` 响应

运行示例：

```bash
cd PROJECTS/crypto-trader-pro
PYTHONPATH=. python src/backtest/example_usage.py
```

## 注意事项

1. **Python 版本兼容性**：支持 Python 3.6+（使用 datetime.strptime 而非 fromisoformat）
2. **时间格式**：支持 ISO 8601、带空格的时间字符串、时间戳等多种格式
3. **空数据保护**：当输入数据为空或不足时，返回默认值（0 或 None）
4. **盈亏比**：极端情况下可能返回 `null`（无亏损）或 `Infinity`（有盈利无亏损），JSON 中 `Infinity` 被转为 `null`

## 更新日志

- **2025-03-05**：初始版本，实现 10 项核心指标
  - 总收益率、年化收益率、最大回撤、Sharpe比率、胜率、盈亏比、盈利/亏损分布、交易频率、平均持仓时间

## 测试建议

建议使用以下场景验证指标计算的正确性：

1. **平稳策略**：收益率低、回撤小、交易频繁
2. **趋势策略**：收益率高、持仓时间长
3. **高频策略**：交易频率高、平均持仓时间短
4. **震荡策略**：胜率高但盈亏比低

可通过修改 `example_usage.py` 中的随机种子和参数生成不同的测试数据。
