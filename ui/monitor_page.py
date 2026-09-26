"""
性能监控页面 - 实时显示系统和引擎资源使用
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QColor, QPen, QLinearGradient, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QSizePolicy
)

from ..core.inference_engine import InferenceEngine
from ..core.monitor import PerformanceMonitor, SystemMetrics, EngineMetrics


class MetricCard(QFrame):
    """单个指标卡片"""

    def __init__(self, title: str, unit: str = "", color: str = "#7aa2f7", parent=None):
        super().__init__(parent)
        self.setObjectName("metricCard")

        self._color = color
        self._value = 0
        self._unit = unit

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("metricLabel")
        layout.addWidget(self.title_label)

        value_row = QHBoxLayout()
        self.value_label = QLabel("0")
        self.value_label.setObjectName("metricValue")
        self.value_label.setStyleSheet(f"color: {color};")
        value_row.addWidget(self.value_label)

        if unit:
            self.unit_label = QLabel(unit)
            self.unit_label.setObjectName("metricUnit")
            value_row.addWidget(self.unit_label)

        value_row.addStretch()
        layout.addLayout(value_row)

    def set_value(self, value, suffix: str = ""):
        if isinstance(value, float):
            self.value_label.setText(f"{value:.1f}{suffix}")
        else:
            self.value_label.setText(f"{value}{suffix}")


class _ChartArea(QWidget):
    """自带 paintEvent 的图表区域（避免 installEventFilter 在 PySide6 6.11 的 bug）"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._chart_color = "#7aa2f7"
        self._chart_data = []
        self._max_points = 120

    def set_color(self, color: str):
        self._chart_color = color

    def add_value(self, value: float):
        self._chart_data.append(max(0, value))
        if len(self._chart_data) > self._max_points:
            self._chart_data = self._chart_data[-self._max_points:]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self._draw_chart(painter)

    def _draw_chart(self, painter: QPainter):
        from PySide6.QtGui import QPen, QColor, QPolygonF, QLinearGradient, QBrush
        from PySide6.QtCore import Qt, QPointF

        w = self.width()
        h = self.height()
        padding = 8

        # 背景网格
        painter.setPen(QPen(QColor("#2a2b3d"), 1))
        for i in range(1, 4):
            y = int(h * i / 4)
            painter.drawLine(padding, y, w - padding, y)

        if len(self._chart_data) < 2:
            return

        data_max = max(self._chart_data) if self._chart_data else 100
        data_max = max(data_max, 1)
        data_min = min(self._chart_data)
        data_range = data_max - data_min if data_max > data_min else 100

        # 折线点
        path_points = []
        for i, val in enumerate(self._chart_data):
            x = padding + (w - 2 * padding) * i / (len(self._chart_data) - 1)
            normalized = (val - data_min) / data_range if data_range > 0 else 0.5
            y = h - padding - (h - 2 * padding) * normalized
            path_points.append((x, y))

        # 填充区域
        if path_points:
            polygon = QPolygonF([QPointF(padding, h - padding)] +
                               [QPointF(x, y) for x, y in path_points] +
                               [QPointF(w - padding, h - padding)])

            gradient = QLinearGradient(0, 0, 0, h)
            base_color = QColor(self._chart_color)
            gradient.setColorAt(0, base_color.lighter(150))
            gradient.setColorAt(1, QColor("#1e2030"))
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(polygon)

        # 折线
        painter.setPen(QPen(QColor(self._chart_color), 2))
        painter.setBrush(Qt.NoBrush)
        for i in range(len(path_points) - 1):
            painter.drawLine(
                int(path_points[i][0]), int(path_points[i][1]),
                int(path_points[i + 1][0]), int(path_points[i + 1][1])
            )

        # 数据点
        painter.setBrush(QColor(self._chart_color))
        step = max(1, len(path_points) // 20)
        for i in range(0, len(path_points), step):
            painter.drawEllipse(
                int(path_points[i][0]) - 2, int(path_points[i][1]) - 2,
                4, 4
            )


class MiniChart(QFrame):
    """迷你折线图"""

    def __init__(self, title: str, color: str = "#7aa2f7", max_points: int = 120, parent=None):
        super().__init__(parent)
        self.setObjectName("metricCard")
        self.setFixedHeight(140)

        self._color = color

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setObjectName("metricLabel")
        layout.addWidget(title_label)

        # 使用自定义 QWidget 子类避免 eventFilter crash
        self._chart_area = _ChartArea()
        self._chart_area.set_color(color)
        self._chart_area.setMinimumHeight(80)
        self._chart_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self._chart_area, 1)

    def add_value(self, value: float):
        self._chart_area.add_value(value)


class MonitorPage(QWidget):
    """性能监控页面"""

    def __init__(self, engine: InferenceEngine, monitor: PerformanceMonitor, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.monitor = monitor
        self._setup_ui()

        self.monitor.metrics_updated.connect(self._on_metrics_updated)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 页面标题
        title_row = QVBoxLayout()
        title = QLabel("性能监控")
        title.setObjectName("pageTitle")
        title_row.addWidget(title)

        subtitle = QLabel("实时查看系统资源和推理引擎运行状态")
        subtitle.setObjectName("pageSubtitle")
        title_row.addWidget(subtitle)
        layout.addLayout(title_row)

        # 实时指标卡片
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        self.cpu_card = MetricCard("CPU 使用率", "%", "#7aa2f7")
        self.cpu_card.set_value(0)
        cards_layout.addWidget(self.cpu_card)

        self.mem_card = MetricCard("内存使用率", "%", "#9ece6a")
        self.mem_card.set_value(0)
        cards_layout.addWidget(self.mem_card)

        self.gpu_card = MetricCard("GPU 使用率", "%", "#bb9af7")
        self.gpu_card.set_value(0 if self.monitor.has_gpu else "N/A")
        if not self.monitor.has_gpu:
            self.gpu_card.value_label.setStyleSheet("color: #565f89;")
        cards_layout.addWidget(self.gpu_card)

        self.eng_cpu_card = MetricCard("引擎 CPU", "%", "#e0af68")
        self.eng_cpu_card.set_value("—")
        cards_layout.addWidget(self.eng_cpu_card)

        self.eng_mem_card = MetricCard("引擎内存", "MB", "#f7768e")
        self.eng_mem_card.set_value("—")
        cards_layout.addWidget(self.eng_mem_card)

        layout.addLayout(cards_layout)

        # 图表区域
        charts_layout = QHBoxLayout()
        charts_layout.setSpacing(12)

        self.cpu_chart = MiniChart("CPU 历史 (%)", "#7aa2f7")
        charts_layout.addWidget(self.cpu_chart, 1)

        self.mem_chart = MiniChart("内存历史 (%)", "#9ece6a")
        charts_layout.addWidget(self.mem_chart, 1)

        if self.monitor.has_gpu:
            self.gpu_chart = MiniChart("GPU 历史 (%)", "#bb9af7")
            charts_layout.addWidget(self.gpu_chart, 1)

        layout.addLayout(charts_layout)

        # 引擎详情
        eng_group = QFrame()
        eng_group.setObjectName("metricCard")
        eng_layout = QVBoxLayout(eng_group)
        eng_layout.setContentsMargins(16, 12, 16, 12)

        eng_title = QLabel("推理引擎详情")
        eng_title.setObjectName("metricLabel")
        eng_layout.addWidget(eng_title)

        self.eng_detail_label = QLabel("引擎未启动")
        self.eng_detail_label.setStyleSheet("color: #565f89; padding: 8px;")
        self.eng_detail_label.setWordWrap(True)
        eng_layout.addWidget(self.eng_detail_label)

        layout.addWidget(eng_group)

        layout.addStretch()

    def _on_metrics_updated(self, sys_metrics: SystemMetrics, eng_metrics: EngineMetrics):
        """指标更新回调"""
        # 更新卡片
        self.cpu_card.set_value(sys_metrics.cpu_percent)
        self.mem_card.set_value(sys_metrics.memory_percent)

        if self.monitor.has_gpu and sys_metrics.gpu_percent is not None:
            self.gpu_card.set_value(sys_metrics.gpu_percent)

        if eng_metrics.running:
            self.eng_cpu_card.set_value(eng_metrics.process_cpu_percent)
            self.eng_mem_card.set_value(eng_metrics.process_memory_mb)
        else:
            self.eng_cpu_card.set_value("—")
            self.eng_mem_card.set_value("—")

        # 更新图表
        self.cpu_chart.add_value(sys_metrics.cpu_percent)
        self.mem_chart.add_value(sys_metrics.memory_percent)
        if self.monitor.has_gpu and sys_metrics.gpu_percent is not None:
            self.gpu_chart.add_value(sys_metrics.gpu_percent)

        # 更新引擎详情
        if eng_metrics.running:
            s = self.engine.status
            uptime = self._format_uptime(eng_metrics.uptime)
            detail = (
                f"<b style='color:#9ece6a'>运行中</b><br>"
                f"模型: {s.model_name}<br>"
                f"PID: {s.pid} | 运行时长: {uptime}<br>"
                f"上下文: {s.ctx_size} | GPU 层: {s.gpu_layers} | 线程: {s.threads or '自动'}<br>"
                f"引擎进程: CPU {eng_metrics.process_cpu_percent:.1f}% | 内存 {eng_metrics.process_memory_mb:.1f} MB"
            )
            self.eng_detail_label.setText(detail)
            self.eng_detail_label.setStyleSheet("color: #c0caf5; padding: 8px;")
        else:
            self.eng_detail_label.setText("引擎未启动")
            self.eng_detail_label.setStyleSheet("color: #565f89; padding: 8px;")

    @staticmethod
    def _format_uptime(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0:
            return f"{h}h {m}m {s}s"
        elif m > 0:
            return f"{m}m {s}s"
        else:
            return f"{s}s"
