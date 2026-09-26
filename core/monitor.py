"""
系统和模型性能监控
"""
import time
import psutil
from dataclasses import dataclass
from typing import List, Optional, Dict

from PySide6.QtCore import QObject, QTimer, Signal

from .inference_engine import InferenceEngine


@dataclass
class SystemMetrics:
    """系统指标快照"""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_total_mb: float
    gpu_percent: Optional[float] = None
    gpu_memory_percent: Optional[float] = None


@dataclass
class EngineMetrics:
    """引擎指标"""
    running: bool = False
    uptime: float = 0.0
    process_cpu_percent: float = 0.0
    process_memory_mb: float = 0.0
    tokens_per_sec: float = 0.0


class PerformanceMonitor(QObject):
    """
    性能监控器 - 定时采集系统和引擎指标
    """
    metrics_updated = Signal(object, object)  # SystemMetrics, EngineMetrics

    def __init__(self, engine: InferenceEngine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._collect_metrics)
        self._history: List[tuple] = []  # (timestamp, SystemMetrics, EngineMetrics)
        self._max_history = 300  # 保留最近 300 条记录（约 5 分钟，按 1s 间隔）

        # 获取 GPU 信息（尝试）
        self._has_gpu = False
        self._gpu_info = {}
        self._detect_gpu()

    def _detect_gpu(self):
        """检测 GPU"""
        try:
            import pynvml
            pynvml.nvmlInit()
            self._has_gpu = True
            self._nvml = pynvml
            self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self._gpu_info['name'] = pynvml.nvmlDeviceGetName(self._gpu_handle)
        except Exception:
            self._has_gpu = False

    def start(self, interval_ms: int = 1000):
        """开始监控"""
        self._timer.start(interval_ms)

    def stop(self):
        """停止监控"""
        self._timer.stop()

    def _collect_metrics(self):
        """采集一次指标"""
        try:
            # 系统指标
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()

            gpu_pct = None
            gpu_mem_pct = None
            if self._has_gpu:
                try:
                    util = self._nvml.nvmlDeviceGetUtilizationRates(self._gpu_handle)
                    gpu_pct = util.gpu
                    mem_info = self._nvml.nvmlDeviceGetMemoryInfo(self._gpu_handle)
                    gpu_mem_pct = mem_info.used / mem_info.total * 100
                except Exception:
                    pass

            sys_metrics = SystemMetrics(
                timestamp=time.time(),
                cpu_percent=cpu,
                memory_percent=mem.percent,
                memory_used_mb=mem.used / (1024 * 1024),
                memory_total_mb=mem.total / (1024 * 1024),
                gpu_percent=gpu_pct,
                gpu_memory_percent=gpu_mem_pct,
            )

            # 引擎指标
            eng_metrics = EngineMetrics()
            if self.engine.is_running():
                eng_metrics.running = True
                s = self.engine.status
                eng_metrics.uptime = time.time() - s.started_at
                try:
                    proc = psutil.Process(s.pid)
                    eng_metrics.process_cpu_percent = proc.cpu_percent(interval=None)
                    eng_metrics.process_memory_mb = proc.memory_info().rss / (1024 * 1024)
                except Exception:
                    pass

            # 保存历史
            self._history.append((time.time(), sys_metrics, eng_metrics))
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

            self.metrics_updated.emit(sys_metrics, eng_metrics)

        except Exception as e:
            print(f"采集指标失败: {e}")

    def get_history(self, last_n: int = 60) -> List[tuple]:
        """获取历史数据"""
        return self._history[-last_n:]

    def get_current(self) -> tuple:
        """获取当前数据"""
        if self._history:
            return self._history[-1]
        return None, None, None

    @property
    def has_gpu(self) -> bool:
        return self._has_gpu

    def get_gpu_info(self) -> Dict:
        return self._gpu_info.copy()
