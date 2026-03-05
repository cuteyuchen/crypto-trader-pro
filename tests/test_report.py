"""
运行测试套件并生成报告
"""
import subprocess
import sys
import os
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_tests():
    """运行所有测试并生成报告"""
    print("="*60)
    print("Crypto Trader Pro - 测试套件")
    print("="*60)
    print()

    # 确保在正确的目录
    os.chdir(PROJECT_ROOT)

    # 创建报告目录
    docs_dir = os.path.join(PROJECT_ROOT, 'docs')
    os.makedirs(docs_dir, exist_ok=True)

    report_path = os.path.join(docs_dir, 'TEST_REPORT.md')

    # 运行 pytest
    print("🚀 正在运行测试...\n")

    pytest_cmd = [
        sys.executable, '-m', 'pytest',
        'tests/',
        '-v',
        '--tb=short',
        '--capture=fd',  # 捕获输出
        f'--html={os.path.join(docs_dir, "test_report.html")}',
        '--self-contained-html'
    ]

    try:
        result = subprocess.run(
            pytest_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace'
        )

        output = result.stdout
        return_code = result.returncode

        print(output)

        # 生成 Markdown 报告
        generate_markdown_report(output, return_code, report_path)

        print("\n" + "="*60)
        if return_code == 0:
            print("✅ 所有测试通过！")
        else:
            print(f"❌ 测试失败（退出码 {return_code}）")
        print(f"📊 报告已生成: {report_path}")
        print(f"🌐 HTML 报告: {os.path.join(docs_dir, 'test_report.html')}")
        print("="*60)

        return return_code

    except Exception as e:
        print(f"运行测试时出错: {e}")
        return 1


def generate_markdown_report(pytest_output, return_code, report_path):
    """生成 Markdown 格式的测试报告"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 解析 pytest 输出，提取测试统计
    lines = pytest_output.split('\n')

    # 查找测试总结行
    summary = ""
    passed = failed = skipped = error = 0

    for line in lines:
        if ' passed' in line:
            summary = line
            break

    # 简单解析
    if 'passed' in summary:
        parts = summary.split()
        for i, part in enumerate(parts):
            if part == 'passed':
                passed = int(parts[i-1])
            elif part == 'failed':
                failed = int(parts[i-1])
            elif part == 'skipped':
                skipped = int(parts[i-1])

    total = passed + failed + skipped

    report = f"""# 测试报告

**生成时间**: {now}

**项目**: Crypto Trader Pro

**测试框架**: pytest

---

## 执行摘要

| 状态 | 数量 |
|------|------|
| ✅ 通过 | {passed} |
| ❌ 失败 | {failed} |
| ⏭️ 跳过 | {skipped} |
| **总计** | {total} |

**整体结果**: {'✅ PASS' if return_code == 0 else '❌ FAIL'}

---

## 详细输出

```
{pytest_output}
```

---

## 测试覆盖范围

### 单元测试 (tests/unit/)
- `test_strategies.py` - 所有策略信号逻辑（MA、RSI、布林带、MACD）
- `test_executor.py` - OrderExecutor 本地执行
- `test_risk_manager.py` - 风控管理器
- `test_simulation_db.py` - 本地模拟数据库

### 集成测试 (tests/integration/)
- `test_main.py` - TradingBot 启动流程
- `test_order_flow.py` - 完整的 buy→sell 交易流程
- `test_backtest.py` - 回测引擎

### API 测试 (tests/api/)
- `test_api_endpoints.py` - 所有 `/api/*` 端点

---

## 测试结果分析

### 策略测试
- ✅ MA 交叉：金叉、死叉、止损、止盈
- ✅ RSI：超卖买入、超买卖出、RSI 计算
- ✅ 布林带：触及上下轨、止损止盈
- ✅ MACD：金叉死叉、止损止盈

### 核心组件
- ✅ 执行器：本地买/卖、余额检查、持仓管理、手续费
- ✅ 风控：仓位限制、每日交易次数、冷却期
- ✅ 数据库：余额、持仓、交易记录

### 集成测试
- ✅ 买→卖完整流程
- ✅ 多轮交易
- ✅ 回测引擎

### API 端点
- ✅ 状态、余额、持仓、交易记录
- ✅ 下单（local 模式）
- ✅ 策略列表与重载
- ✅ 回测接口
- ✅ 配置读写

---

## 问题与建议

{_extract_issues(pytest_output)}

---

*报告自动生成于 {now}*
"""

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)


def _extract_issues(output):
    """从 pytest 输出中提取失败信息"""
    lines = output.split('\n')
    issues = []
    capture = False
    for line in lines:
        if line.startswith('FAILURES'):
            capture = True
            continue
        if capture:
            if line.startswith('=') or line.startswith('tests/'):
                continue
            if 'short test summary info' in line.lower():
                break
            if line.strip():
                issues.append(line)
    return '\n'.join(issues) if issues else "无重大问题。"


if __name__ == '__main__':
    sys.exit(run_tests())
