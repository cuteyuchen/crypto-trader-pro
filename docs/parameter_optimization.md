# 参数网格搜索教程

## 1. 什么是参数优化？

量化策略的表现高度依赖参数配置。参数优化就是**自动寻找最优参数组合**的过程。

**示例：**
- RSI 策略的 `rsi_period` 通常取 14，但 10、12、16 也可能更好
- MA 交叉策略的 `fast_period` 和 `slow_period` 有很多组合
- 布林带的 `bb_period` 和 `bb_std` 需要根据品种调整

网格搜索（Grid Search）是穷举所有参数组合，找到在历史数据上表现最佳的配置。

---

## 2. 系统已集成的 ParameterOptimizer

### 2.1 功能定位

当前 `src/learning/performance_analyzer.py` 中的 `ParameterOptimizer` 提供**基于规则的参数建议**，而非全网格搜索。

**运行逻辑：**
1. 分析近期交易表现（过去 7 天）
2. 根据预设规则判断参数是否合理
3. 输出建议的新参数值

**适用场景：**
- 快速微调（± 少量参数）
- 无需等待大量回测
- 适合策略维护场景

### 2.2 使用示例

```python
from src.learning.performance_analyzer import ParameterOptimizer, PerformanceAnalyzer

# 初始化
analyzer = PerformanceAnalyzer("data/simulation.db")
optimizer = ParameterOptimizer(analyzer)

# 分析 RSI 策略
strategy_name = "RSI_14_70_30"
config = {
    "type": "rsi",
    "rsi_period": 14,
    "oversold": 30,
    "overbought": 70
}

suggestion = optimizer.suggest_improvements(strategy_name, config)

print("近期表现:", suggestion['performance'])
# {
#   'strategy': 'RSI_14_70_30',
#   'period_days': 7,
#   'total_trades': 15,
#   'win_rate': 33.3,
#   'avg_pnl': -5.23,
#   'total_pnl': -78.45,
#   'sharpe': -0.45,
#   'max_drawdown': 120.5
# }

print("改进建议:", suggestion['suggestions'])
# ['RSI 胜率偏低，扩大超买超卖阈值至 25/75']

print("推荐新配置:", suggestion['new_config'])
# {
#   'type': 'rsi',
#   'rsi_period': 14,
#   'oversold': 25,
#   'overbought': 75
# }
```

### 2.3 规则说明

当前规则（可根据需要扩展）：

**RSI 策略：**
- 胜率 < 40% → 扩大超买超卖阈值（如 30/70 → 25/75），减少信号频率
- 平均盈亏为负 → 建议切换策略

**MA 交叉策略：**
- 交易频率低（<10笔/7天） → 缩小 MA 周期（如 5/20 → 4/18）
- 胜率 < 40% → 建议切换策略

**布林带策略：**
- 回撤过大（>200） → 增加 `bb_std`（如 2.0 → 2.2）
- 交易频率低 → 缩小 `bb_period`（如 20 → 18）

**MACD 策略：**
- 胜率 < 40% → 增加 `signal_period`（平滑参数，减少噪声）

---

## 3. 完整网格搜索实现（自定义）

如需遍历所有参数组合进行系统化优化，需要自建框架。

### 3.1 核心流程

```python
from src.backtest.engine import BacktestEngine
from src.backtest.metrics import BacktestMetrics
import itertools

def grid_search(strategy_base_cfg, param_grid, days=30):
    """
    网格搜索主函数

    Args:
        strategy_base_cfg: 基础策略配置（不含待优化参数）
        param_grid: 参数网格，如 {'rsi_period': [10,14,20], 'oversold': [25,30,35]}
        days: 回测天数

    Returns:
        排序后的结果列表
    """
    # 生成所有参数组合
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    combinations = list(itertools.product(*values))

    results = []
    for combo in combinations:
        # 构建本次回测的配置
        cfg = strategy_base_cfg.copy()
        params = dict(zip(keys, combo))
        cfg['params'] = params if 'params' in strategy_base_cfg else {}
        cfg.update(params)  # 对于 RSI 策略，rsi_period 等是顶层字段

        # 运行回测
        engine = BacktestEngine(cfg, initial_balance=10000)
        result = engine.run(days=days)

        # 计算指标
        metrics = BacktestMetrics.calculate(
            result['equity_curve'],
            result['trades']
        )

        results.append({
            'config': cfg,
            'metrics': metrics,
            'total_return': metrics['total_return_pct'],
            'sharpe': metrics['sharpe_ratio'],
            'max_dd': metrics['max_drawdown_pct'],
            'win_rate': metrics['win_rate_pct'],
            'total_trades': metrics['total_trades']
        })

    # 按指定指标排序（默认 Sharpe 降序）
    sorted_results = sorted(results, key=lambda x: x['sharpe'], reverse=True)
    return sorted_results
```

### 3.2 使用示例：RSI 参数优化

```python
# 基础配置（不包含要扫描的参数）
base_cfg = {
    "name": "RSI_Optimized",
    "type": "rsi",
    "symbol": "BTC/USDT",
    "timeframe": "1m",
    "position_size": 0.2
}

# 定义参数网格
param_grid = {
    "rsi_period": [10, 14, 20],
    "oversold": [25, 30, 35],
    "overbought": [65, 70, 75]
}

# 执行网格搜索
results = grid_search(base_cfg, param_grid, days=30)

# 打印 top 5
for i, r in enumerate(results[:5], 1):
    cfg = r['config']
    m = r['metrics']
    print(f"{i}. RSI({cfg.get('rsi_period')}) {cfg.get('oversold')}/{cfg.get('overbought')}")
    print(f"   Sharpe: {m['sharpe_ratio']:.3f}, 收益: {m['total_return_pct']:.2f}%, 回撤: {m['max_drawdown_pct']:.2f}%")
```

**输出示例：**
```
1. RSI(14) 25/75
   Sharpe: 1.234, 收益: 15.23%, 回撤: 6.78%
2. RSI(10) 25/75
   Sharpe: 1.102, 收益: 14.56%, 回撤: 7.23%
3. RSI(14) 30/75
   Sharpe: 0.987, 收益: 12.34%, 回撤: 8.12%
...
```

### 3.3 性能优化

网格搜索可能很耗时（组合数 × 回测时间）。优化建议：

1. **减少回测天数**：先用 7-14 天快速筛选，再用 30-90 天确认
2. **并行化**：使用 `multiprocessing.Pool` 或并发
3. **缓存历史数据**：使用 `CCXTBacktestEngine` 的缓存机制
4. **分阶段扫描**：
   - 第一轮：大范围粗搜（步长大）
   - 第二轮：在最优区域精细搜索（步长小）

**并行示例：**

```python
from multiprocessing import Pool

def run_single_combo(combo):
    cfg = base_cfg.copy()
    params = dict(zip(keys, combo))
    cfg.update(params)
    engine = BacktestEngine(cfg)
    result = engine.run(days=14)  # 先用短周期
    metrics = BacktestMetrics.calculate(result['equity_curve'], result['trades'])
    return {'config': cfg, 'metrics': metrics}

with Pool(processes=4) as pool:
    results = pool.map(run_single_combo, combinations)
```

---

## 4. Web 界面集成（前端）

### 4.1 后端 API 扩展

在 `src/dashboard/app.py` 添加：

```python
from src.backtest.engine import BacktestEngine
from src.backtest.metrics import BacktestMetrics
import itertools

@app.route('/api/optimize', methods=['POST'])
def run_optimization():
    """运行参数优化（网格搜索）"""
    bot = trading_bot
    req = request.get_json()

    strategy_type = req.get('strategy')  # 'rsi', 'ma_cross', etc.
    param_grid = req.get('param_grid')   # {'rsi_period': [10,14,20], 'oversold': [25,30,35]}
    days = int(req.get('days', 14))

    # 构建基础配置
    base_cfg = {
        "type": strategy_type,
        "symbol": bot.strategy_config['symbol'],
        "timeframe": bot.strategy_config['timeframe'],
        "position_size": bot.strategy_config.get('position_size', 0.2)
    }

    # 执行网格搜索（简化版，实际应该放在后台任务）
    results = []
    keys = list(param_grid.keys())
    combinations = list(itertools.product(*param_grid.values()))

    for combo in combinations[:10]:  # 限制最多10个，避免阻塞
        cfg = base_cfg.copy()
        for k, v in zip(keys, combo):
            cfg[k] = v
        engine = BacktestEngine(cfg, initial_balance=10000)
        result = engine.run(days=days)
        metrics = BacktestMetrics.calculate(result['equity_curve'], result['trades'])
        results.append({
            'params': dict(zip(keys, combo)),
            'sharpe': metrics['sharpe_ratio'],
            'return': metrics['total_return_pct'],
            'max_dd': metrics['max_drawdown_pct']
        })

    # 排序
    sorted_results = sorted(results, key=lambda x: x['sharpe'], reverse=True)

    return jsonify({
        'best': sorted_results[0],
        'all': sorted_results[:10]
    })
```

### 4.2 前端页面（示例）

在回测页面添加「参数优化」标签页：

```html
<!-- 参数优化表单 -->
<div>
  <h3>RSI 参数优化</h3>
  <label>rsi_period 范围: </label>
  <input type="number" v-model="rsi_period_min" placeholder="10">
  <input type="number" v-model="rsi_period_max" placeholder="20">
  <label>步长: </label>
  <input type="number" v-model="rsi_period_step" value="2">

  <label>oversold 范围: </label>
  <input type="number" v-model="oversold_min" placeholder="25">
  <input type="number" v-model="oversold_max" placeholder="35">
  <label>步长: </label>
  <input type="number" v-model="oversold_step" value="5">

  <button @click="runOptimization">开始优化</button>
</div>

<!-- 结果表格 -->
<table v-if="results.length">
  <tr>
    <th>参数组合</th>
    <th>Sharpe</th>
    <th>收益率</th>
    <th>最大回撤</th>
    <th>操作</th>
  </tr>
  <tr v-for="r in results" :key="r.params">
    <td>{{ r.params }}</td>
    <td>{{ r.sharpe.toFixed(3) }}</td>
    <td>{{ r.return.toFixed(2) }}%</td>
    <td>{{ r.max_dd.toFixed(2) }}%</td>
    <td><button @click="applyConfig(r.params)">应用</button></td>
  </tr>
</table>
```

**JavaScript 调用：**

```javascript
async function runOptimization() {
  const param_grid = {
    rsi_period: range(parseInt(rsi_period_min), parseInt(rsi_period_max), parseInt(rsi_period_step)),
    oversold: range(parseInt(oversold_min), parseInt(oversold_max), parseInt(oversold_step)),
    overbought: range(parseInt(overbought_min), parseInt(overbought_max), parseInt(overbought_step))
  };

  const resp = await fetch('/api/optimize', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      strategy: 'rsi',
      param_grid: param_grid,
      days: 14
    })
  });
  const data = await resp.json();
  results = data.all;
}
```

---

## 5. 高级优化技巧

### 5.1 自定义评分函数

不只看 Sharpe，可加权多指标：

```python
def score_metrics(metrics, weights=None):
    """
    综合评分
    weights = {
        'sharpe': 0.3,
        'return': 0.3,
        'max_dd': -0.2,  # 负权重，越小越好
        'win_rate': 0.2
    }
    """
    if weights is None:
        weights = {'sharpe': 0.4, 'return': 0.3, 'max_dd': -0.2, 'win_rate': 0.1}

    score = 0
    for key, w in weights.items():
        val = metrics.get(key, 0)
        if key == 'max_dd':
            val = -val  # 回撤取负
        score += w * val

    return score
```

在结果排序时使用：

```python
for r in results:
    r['score'] = score_metrics(r['metrics'])
sorted_results = sorted(results, key=lambda x: x['score'], reverse=True)
```

### 5.2 避免过拟合（样本外测试）

```python
# 将数据分为训练集和测试集
train_days = 60
test_days = 7

# 在训练集上网格搜索
train_results = grid_search(base_cfg, param_grid, days=train_days)
best_cfg = train_results[0]['config']

# 在测试集上验证
test_engine = BacktestEngine(best_cfg)
test_result = test_engine.run(days=test_days)
test_metrics = BacktestMetrics.calculate(test_result['equity_curve'], test_result['trades'])

print(f"测试集表现: Sharpe={test_metrics['sharpe_ratio']}, 收益={test_metrics['total_return_pct']}%")
```

**过拟合警告：**
- 训练集表现极好，测试集大幅下降 → 参数过拟合
- 解决方案：扩大样本（更多历史数据）、简化参数、增加正则化

### 5.3 贝叶斯优化（替代网格搜索）

当参数维度高（>4）时，网格搜索计算量爆炸。可考虑贝叶斯优化库（如 `scikit-optimize`、`optuna`）。

**简要示例（使用 optuna）：**

```python
import optuna

def objective(trial):
    rsi_period = trial.suggest_int('rsi_period', 10, 30)
    oversold = trial.suggest_int('oversold', 20, 35)
    overbought = trial.suggest_int('overbought', 65, 80)

    cfg = {
        "type": "rsi",
        "rsi_period": rsi_period,
        "oversold": oversold,
        "overbought": overbought,
        "symbol": "BTC/USDT",
        "timeframe": "1m",
        "position_size": 0.2
    }

    engine = BacktestEngine(cfg)
    result = engine.run(days=30)
    metrics = BacktestMetrics.calculate(result['equity_curve'], result['trades'])

    # optuna 默认最大化，返回负的 sharpe 或 最大回撤
    return metrics['sharpe_ratio']

study = optuna.create_study(direction='maximize')
study.optimize(objective, n_trials=50)

print("最佳参数:", study.best_params)
print("最佳 Sharpe:", study.best_value)
```

---

## 6. 实战流程

1. **初步参数**：基于策略文档或经验设置初始参数
2. **大范围扫描**：使用 7-14 天数据，较大步长（如 period ± 5）
3. **精细搜索**：在 top 5-10 组合附近缩小范围，增加步长精度
4. **样本外验证**：用最新 7 天数据验证，剔除明显过拟合的参数
5. **实盘前测试**：在 testnet 上运行 1-2 周，观察稳定性
6. **小资金实盘**：投入少量资金，进一步验证
7. **正式部署**：确定最终参数，写入配置文件

---

## 7. 常见问题

### Q1: 网格搜索太慢，50 个组合要跑 2 小时？

**优化方案：**
1. 减少回测天数（先用 7 天筛选）
2. 并行化（4-8 核同时跑）
3. 缓存 CCXT 数据（避免重复下载）
4. 只优化关键参数（如 RSI 的 thresholds，而非 period）

### Q2: 最优参数随时间变化？

是的，市场状态会变，最优参数也会漂移。
**解决方案：**
- 定期（如每月）重新优化
- 使用滚动窗口优化（最近 90 天数据）
- ParameterOptimizer 的日报功能可以辅助监控

### Q3: 不同交易所/交易对参数是否通用？

不一定。建议：
- 每个交易对单独优化（BTC/USDT 和 ETH/USDT 可能不同）
- 交易所影响流动性、波动特征，可分别优化
- 如果参数差异大，考虑创建多个策略配置文件

### Q4: 如何保存优化结果？

**手动：** 从日志或终端复制，手动修改配置文件
**自动：** 在优化脚本中直接写入文件

```python
import json

best_cfg = results[0]['config']
with open('config/strategies/rsi_optimized.json', 'w') as f:
    json.dump(best_cfg, f, indent=2, ensure_ascii=False)

print("已保存到 config/strategies/rsi_optimized.json")
```

---

## 8. 参考

- 回测引擎：`src/backtest/engine.py`
- 指标计算：`src/backtest/metrics.py`
- 参数优化器：`src/learning/performance_analyzer.py`（ParameterOptimizer 类）
- Dashboard API：`src/dashboard/app.py`（`/api/backtest` 端点）

---

## 9. 总结

- **ParameterOptimizer**：适合快速诊断，规则化建议
- **自定义网格搜索**：适合系统化优化，需要自己实现
- **optuna 等库**：适合高维参数空间
- **Web 界面集成**：后端提供 `/api/optimize` 接口，前端展示结果

建议先使用 ParameterOptimizer 的日报功能观察策略表现，必要时再手动网格搜索。
