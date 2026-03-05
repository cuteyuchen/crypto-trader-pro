"""
参数网格搜索优化引擎
Grid Search Optimization Engine for Backtesting
"""

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from itertools import product
from dataclasses import dataclass, asdict


@dataclass
class OptimizationMetrics:
    """回测指标数据类"""
    sharpe_ratio: float
    total_return: float
    max_drawdown: float
    win_rate: float
    # 可扩展其他指标
    profit_factor: Optional[float] = None
    total_trades: Optional[int] = None

    def to_dict(self):
        return asdict(self)


@dataclass
class OptimizationJob:
    """优化任务状态"""
    job_id: str
    status: str  # "running", "completed", "cancelled", "error"
    total_combinations: int
    completed: int
    best_result: Optional[Dict[str, Any]]
    logs: List[str]
    start_time: str
    end_time: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self):
        return asdict(self)

    def save(self, filepath: Path):
        """保存状态到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, filepath: Path) -> 'OptimizationJob':
        """从文件加载状态"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(**data)


class GridOptimizer:
    """
    网格搜索优化器

    功能：
    - 生成参数组合网格
    - 异步执行回测
    - 跟踪进度和最佳结果
    - 支持中断和状态持久化
    """

    def __init__(
        self,
        strategy_config_template: Dict[str, Any],
        param_ranges: Dict[str, List[Any]],
        backtest_engine: Any,
        sort_metric: str = "sharpe_ratio",
        state_dir: str = "data/optimization_jobs"
    ):
        """
        初始化网格优化器

        Args:
            strategy_config_template: 策略配置模板（基础配置）
            param_ranges: 参数范围字典，格式如：
                {"rsi_period": [10, 20, 2]}  # start, end, step
                或 {"rsi_period": [10, 15, 20]}  # 具体值列表
            backtest_engine: 回测引擎实例（需提供 run_backtest 方法）
            sort_metric: 排序指标（默认 Sharpe 比率）
            state_dir: 状态存储目录
        """
        self.strategy_config_template = strategy_config_template
        self.param_ranges = param_ranges
        self.backtest_engine = backtest_engine
        self.sort_metric = sort_metric
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # 运行时状态
        self._job: Optional[OptimizationJob] = None
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

        # 生成参数组合
        self.param_combinations = self._generate_param_grid()

    def _parse_range(self, range_value: List[Any]) -> List[Any]:
        """解析参数范围，支持 [start, end, step] 或值列表"""
        if len(range_value) == 3 and all(isinstance(v, (int, float)) for v in range_value):
            start, end, step = range_value
            # 生成范围（包含 end，如果是整数）
            if isinstance(start, int) and isinstance(end, int):
                return list(range(start, end + 1, step))
            else:
                # 浮点数使用 numpy-like arange
                values = []
                current = start
                while current <= end:
                    values.append(round(current, 10))  # 避免浮点误差
                    current += step
                return values
        else:
            # 直接返回值列表
            return list(range_value)

    def _generate_param_grid(self) -> List[Dict[str, Any]]:
        """生成所有参数组合的列表"""
        param_names = list(self.param_ranges.keys())
        param_values = []

        for name in param_names:
            values = self._parse_range(self.param_ranges[name])
            param_values.append(values)

        # 使用 itertools.product 生成笛卡尔积
        combinations = []
        for combo in product(*param_values):
            param_dict = dict(zip(param_names, combo))
            combinations.append(param_dict)

        return combinations

    def create_job(self, job_id: Optional[str] = None) -> str:
        """创建新的优化任务"""
        import uuid
        job_id = job_id or str(uuid.uuid4())

        self._job = OptimizationJob(
            job_id=job_id,
            status="running",
            total_combinations=len(self.param_combinations),
            completed=0,
            best_result=None,
            logs=[],
            start_time=datetime.now().isoformat()
        )
        self._stop_event.clear()

        # 保存初始状态
        state_file = self.state_dir / f"{job_id}.json"
        self._job.save(state_file)

        return job_id

    def start_async(self, job_id: Optional[str] = None, callback: Optional[Callable] = None) -> str:
        """
        在后台线程启动优化任务

        Returns:
            job_id
        """
        if self._thread and self._thread.is_alive():
            raise RuntimeError("优化任务已在运行")

        job_id = self.create_job(job_id)

        def run():
            try:
                self._run_optimization()
                if callback:
                    callback(job_id, self._job)
            except Exception as e:
                self._log(f"优化任务异常: {e}", level="error")
                if self._job:
                    self._job.status = "error"
                    self._job.error_message = str(e)
                    self._save_state()

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

        return job_id

    def _run_optimization(self):
        """执行网格搜索"""
        self._log(f"开始优化，共 {len(self.param_combinations)} 个参数组合")

        best_metrics = None
        best_params = None
        best_config = None

        for idx, params in enumerate(self.param_combinations, 1):
            # 检查是否应该停止
            if self._stop_event.is_set():
                self._log("优化任务被用户取消")
                if self._job:
                    self._job.status = "cancelled"
                break

            try:
                # 合并策略配置模板和当前参数
                config = self.strategy_config_template.copy()
                config.update(params)

                # 执行回测
                self._log(f"[{idx}/{len(self.param_combinations)}] 测试参数: {params}")
                metrics = self.backtest_engine.run_backtest(config)

                # 记录结果
                self._log(
                    f"   Sharpe: {metrics.sharpe_ratio:.3f}, "
                    f"总收益: {metrics.total_return:.2%}, "
                    f"最大回撤: {metrics.max_drawdown:.2%}, "
                    f"胜率: {metrics.win_rate:.2%}"
                )

                # 更新最佳结果
                if self._is_better(metrics, best_metrics):
                    best_metrics = metrics
                    best_params = params.copy()
                    best_config = config.copy()
                    self._log(f"   ★ 新的最佳组合！")

                # 更新进度
                if self._job:
                    self._job.completed = idx
                    if best_metrics:
                        self._job.best_result = {
                            "params": best_params,
                            "config": best_config,
                            "metrics": best_metrics.to_dict()
                        }
                    self._save_state()

            except Exception as e:
                self._log(f"参数组合 {params} 回测失败: {e}", level="error")
                continue

        # 完成
        if self._job and self._job.status == "running":
            self._job.status = "completed"
        if self._job:
            self._job.end_time = datetime.now().isoformat()
            self._save_state()

        self._log(f"优化完成！最佳参数：{best_params}, {self.sort_metric}={getattr(best_metrics, self.sort_metric):.3f}")

    def _is_better(self, metrics: OptimizationMetrics, best_metrics: Optional[OptimizationMetrics]) -> bool:
        """
        判断当前指标是否更好
        注意：最大回撤是越小越好，其他指标通常是越大越好
        """
        if best_metrics is None:
            return True

        current_value = getattr(metrics, self.sort_metric)
        best_value = getattr(best_metrics, self.sort_metric)

        # 特殊处理最大回撤（越小越好）
        if self.sort_metric == "max_drawdown":
            return current_value < best_value
        else:
            return current_value > best_value

    def _log(self, message: str, level: str = "info"):
        """记录日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)  # 同时输出到控制台

        if self._job:
            with self._lock:
                self._job.logs.append(log_entry)

    def _save_state(self):
        """保存当前任务状态"""
        if not self._job:
            return
        state_file = self.state_dir / f"{self._job.job_id}.json"
        self._job.save(state_file)

    def stop(self):
        """停止优化任务"""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def get_job_status(self, job_id: str) -> Optional[OptimizationJob]:
        """获取任务状态"""
        state_file = self.state_dir / f"{job_id}.json"
        if state_file.exists():
            return OptimizationJob.load(state_file)
        return None

    def cancel_job(self, job_id: str) -> bool:
        """取消指定任务"""
        job = self.get_job_status(job_id)
        if job and job.status in ["running", "pending"]:
            # 如果是当前任务，直接停止
            if self._job and self._job.job_id == job_id:
                self.stop()
            # 更新状态文件
            job.status = "cancelled"
            job.end_time = datetime.now().isoformat()
            job.save(self.state_dir / f"{job_id}.json")
            return True
        return False


# 示例：简单的 Mock 回测引擎（实际项目中需替换为真实实现）
class MockBacktestEngine:
    """模拟回测引擎，用于测试"""

    def run_backtest(self, config: Dict[str, Any]) -> OptimizationMetrics:
        """
        执行回测并返回指标

        这里只是模拟，实际应该运行真实的回测逻辑
        """
        # 模拟计算（实际应该基于 config 运行回测）
        import random
        # 使用可哈希的种子（只使用数值参数）
        numeric_values = [v for v in config.values() if isinstance(v, (int, float))]
        seed = sum(numeric_values) if numeric_values else 0
        random.seed(seed)

        sharpe = random.uniform(0.5, 2.5)
        total_return = random.uniform(-0.1, 0.5)
        max_dd = random.uniform(0.05, 0.3)
        win_rate = random.uniform(0.4, 0.7)

        time.sleep(0.1)  # 模拟计算耗时

        return OptimizationMetrics(
            sharpe_ratio=sharpe,
            total_return=total_return,
            max_drawdown=max_dd,
            win_rate=win_rate
        )


if __name__ == "__main__":
    # 使用示例
    strategy_template = {
        "strategy": "rsi_macd",
        "initial_capital": 10000,
        "commission": 0.001
    }

    param_ranges = {
        "rsi_period": [10, 20, 2],  # 10, 12, 14, 16, 18, 20
        "rsi_overbought": [70, 80, 5],  # 70, 75, 80
        "macd_fast": [12],
        "macd_slow": [26]
    }

    optimizer = GridOptimizer(
        strategy_config_template=strategy_template,
        param_ranges=param_ranges,
        backtest_engine=MockBacktestEngine(),
        sort_metric="sharpe_ratio"
    )

    print(f"总参数组合数: {len(optimizer.param_combinations)}")
    print("前5个组合:")
    for i, combo in enumerate(optimizer.param_combinations[:5]):
        print(f"  {i+1}: {combo}")

    # 启动异步优化
    job_id = optimizer.start_async()
    print(f"\n任务ID: {job_id}")

    # 等待完成（实际应在后台运行）
    while optimizer.get_job_status(job_id).completed < len(optimizer.param_combinations):
        status = optimizer.get_job_status(job_id)
        print(f"进度: {status.completed}/{status.total_combinations}, 最佳: {status.best_result}")
        time.sleep(0.5)

    print("\n优化完成！")