"""
概览仪表盘页面
"""
import time
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QComboBox, QSpinBox, QGroupBox, QFormLayout, QScrollArea, QSizePolicy,
    QMessageBox, QProgressBar
)

from ..core.inference_engine import InferenceEngine
from ..core.model_manager import ModelManager, ModelInfo
from ..core.monitor import PerformanceMonitor
from ..config import get_settings


class DashboardPage(QWidget):
    """概览仪表盘"""

    def __init__(self, engine: InferenceEngine, model_manager: ModelManager,
                 monitor: PerformanceMonitor, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.model_manager = model_manager
        self.monitor = monitor
        self._settings = get_settings()

        self._setup_ui()
        self._refresh_local_models()

        # 定期刷新状态
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_status)
        self._timer.start(2000)

        self.engine.status_changed.connect(self._on_engine_status_changed)
        self.engine.model_loaded.connect(self._on_model_loaded)
        self.engine.model_unloaded.connect(self._on_model_unloaded)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 页面标题
        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title = QLabel("概览")
        title.setObjectName("pageTitle")
        title_col.addWidget(title)

        subtitle = QLabel("启动模型并开始使用 OpenAI 兼容的本地 API")
        subtitle.setObjectName("pageSubtitle")
        title_col.addWidget(subtitle)
        header.addLayout(title_col)
        header.addStretch()
        layout.addLayout(header)

        # 状态 + API 信息卡片
        status_layout = QHBoxLayout()
        status_layout.setSpacing(16)

        # 引擎状态卡片
        self.status_card = QFrame()
        self.status_card.setObjectName("metricCard")
        status_card_layout = QVBoxLayout(self.status_card)
        status_card_layout.setContentsMargins(20, 20, 20, 20)

        status_title = QLabel("引擎状态")
        status_title.setObjectName("metricLabel")
        status_card_layout.addWidget(status_title)

        self.status_row = QHBoxLayout()
        self.status_dot = QLabel()
        self.status_dot.setObjectName("statusDot")
        self.status_dot.setProperty("class", "stopped")
        self.status_dot.setFixedSize(14, 14)
        self.status_row.addWidget(self.status_dot)

        self.status_label = QLabel("已停止")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setProperty("class", "stopped")
        self.status_row.addWidget(self.status_label)
        self.status_row.addStretch()
        status_card_layout.addLayout(self.status_row)

        self.model_info_label = QLabel("未加载模型")
        self.model_info_label.setObjectName("pageSubtitle")
        self.model_info_label.setWordWrap(True)
        status_card_layout.addWidget(self.model_info_label)

        self.uptime_label = QLabel("运行时间: —")
        self.uptime_label.setObjectName("pageSubtitle")
        status_card_layout.addWidget(self.uptime_label)

        status_layout.addWidget(self.status_card, 1)

        # API 信息卡片
        api_card = QFrame()
        api_card.setObjectName("metricCard")
        api_layout = QVBoxLayout(api_card)
        api_layout.setContentsMargins(20, 20, 20, 20)

        api_title = QLabel("API 访问信息")
        api_title.setObjectName("metricLabel")
        api_layout.addWidget(api_title)

        from PySide6.QtCore import QUrl
        api_url_label = QLabel(f"Endpoint: {self._settings.api_full_url}")
        api_url_label.setStyleSheet("font-family: Consolas, monospace; color: #9ece6a; padding: 4px 0;")
        api_layout.addWidget(api_url_label)

        api_key_label = QLabel(f"API Key: {self._settings.get('api_key')}")
        api_key_label.setStyleSheet("font-family: Consolas, monospace; color: #9ece6a; padding: 4px 0;")
        api_layout.addWidget(api_key_label)

        hint_label = QLabel("所有 OpenAI SDK 兼容，把 base_url 指向上面的地址即可")
        hint_label.setObjectName("pageSubtitle")
        hint_label.setWordWrap(True)
        api_layout.addWidget(hint_label)
        api_layout.addStretch()

        status_layout.addWidget(api_card, 1)
        layout.addLayout(status_layout)

        # 启动/停止区域
        control_group = QGroupBox("模型控制")
        control_layout = QFormLayout(control_group)
        control_layout.setContentsMargins(20, 20, 20, 20)
        control_layout.setSpacing(12)

        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(300)
        control_layout.addRow("选择模型:", self.model_combo)

        param_layout = QHBoxLayout()

        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(0, 256)
        self.threads_spin.setValue(self._settings.get('default_threads', 0))
        self.threads_spin.setSpecialValueText("自动")
        self.threads_spin.setToolTip("0 = 使用所有可用核心")
        param_layout.addWidget(QLabel("CPU 线程:"))
        param_layout.addWidget(self.threads_spin)

        self.ctx_spin = QSpinBox()
        self.ctx_spin.setRange(512, 131072)
        self.ctx_spin.setValue(self._settings.get('default_ctx_size', 4096))
        self.ctx_spin.setSingleStep(512)
        param_layout.addWidget(QLabel("上下文大小:"))
        param_layout.addWidget(self.ctx_spin)

        self.gpu_combo = QComboBox()
        self.gpu_combo.addItem("全 CPU", 0)
        self.gpu_combo.addItem("GPU 加速 (-1)", -1)
        self.gpu_combo.addItem("GPU 前 20 层", 20)
        self.gpu_combo.addItem("GPU 前 35 层", 35)
        self.gpu_combo.addItem("GPU 前 50 层", 50)
        param_layout.addWidget(QLabel("GPU 层数:"))
        param_layout.addWidget(self.gpu_combo)

        param_layout.addStretch()
        control_layout.addRow("运行参数:", param_layout)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.stop_btn = QPushButton("⏹ 停止模型")
        self.stop_btn.setObjectName("dangerButton")
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_btn)

        self.start_btn = QPushButton("▶ 启动模型")
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.clicked.connect(self._on_start_clicked)
        btn_layout.addWidget(self.start_btn)

        control_layout.addRow(btn_layout)

        layout.addWidget(control_group)

        # 快速开始提示
        quickstart_group = QGroupBox("🚀 快速开始")
        quick_layout = QVBoxLayout(quickstart_group)

        tips = [
            "1️⃣ 前往「模型管理」下载你喜欢的 GGUF 格式模型",
            "2️⃣ 返回这里，在下拉框选择已下载的模型",
            "3️⃣ 点击「启动模型」，等待 API 就绪",
            "4️⃣ 使用任意 OpenAI 兼容的客户端连接 API",
        ]
        for tip in tips:
            lbl = QLabel(tip)
            lbl.setStyleSheet("color: #a9b1d6; padding: 4px 0;")
            quick_layout.addWidget(lbl)

        # 代码示例
        code_example = QFrame()
        code_example.setStyleSheet(
            "background-color: #0d0e16; border: 1px solid #2a2b3d; border-radius: 6px; padding: 12px;"
        )
        code_layout = QVBoxLayout(code_example)
        code_text = f'''# Python + OpenAI SDK 示例
from openai import OpenAI

client = OpenAI(
    base_url="{self._settings.api_full_url}",
    api_key="{self._settings.get('api_key')}",
)

response = client.chat.completions.create(
    model="your-model-name",
    messages=[{{"role": "user", "content": "你好"}}]
)
print(response.choices[0].message.content)'''
        code_label = QLabel(code_text)
        code_label.setStyleSheet("font-family: Consolas, monospace; color: #7aa2f7; font-size: 12px;")
        code_layout.addWidget(code_label)
        quick_layout.addWidget(code_example)

        layout.addWidget(quickstart_group)
        layout.addStretch()

    def _refresh_local_models(self):
        """刷新本地模型列表"""
        self.model_combo.clear()
        models = self.model_manager.get_local_models()
        if models:
            for m in models:
                size_str = f"{m.file_size / (1024*1024):.0f}MB" if m.file_size else "?"
                self.model_combo.addItem(f"{m.name}  ({size_str})", m)
            self.start_btn.setEnabled(True)
        else:
            self.model_combo.addItem("（还没有下载模型，前往「模型管理」下载）")
            self.start_btn.setEnabled(False)

    def _update_status(self):
        """定期更新运行状态"""
        if self.engine.is_running():
            s = self.engine.status
            uptime = time.time() - s.started_at
            hours = int(uptime // 3600)
            minutes = int((uptime % 3600) // 60)
            seconds = int(uptime % 60)
            self.uptime_label.setText(f"运行时间: {hours:02d}:{minutes:02d}:{seconds:02d}")

    def _on_engine_status_changed(self, status):
        pass  # 已通过 model_loaded/unloaded 信号处理

    def _on_model_loaded(self, model_name: str):
        self.status_dot.setProperty("class", "running")
        self.status_dot.style().unpolish(self.status_dot)
        self.status_dot.style().polish(self.status_dot)
        self.status_label.setText("运行中")
        self.status_label.setProperty("class", "running")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.model_info_label.setText(f"当前模型: {model_name}")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)

        # 通知侧边栏更新
        if self.parent():
            self.window().sidebar.update_engine_status(True, model_name)

    def _on_model_unloaded(self):
        self.status_dot.setProperty("class", "stopped")
        self.status_dot.style().unpolish(self.status_dot)
        self.status_dot.style().polish(self.status_dot)
        self.status_label.setText("已停止")
        self.status_label.setProperty("class", "stopped")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.model_info_label.setText("未加载模型")
        self.uptime_label.setText("运行时间: —")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

        if self.parent():
            self.window().sidebar.update_engine_status(False)

    def _on_start_clicked(self):
        idx = self.model_combo.currentIndex()
        if idx < 0:
            return

        model = self.model_combo.itemData(idx)
        if not model:
            return

        local_path = self.model_manager.get_model_local_path(model)
        if not local_path:
            QMessageBox.warning(self, "错误", f"找不到模型文件: {model.filename}")
            return

        model_name = model.name
        threads = self.threads_spin.value()
        ctx_size = self.ctx_spin.value()
        gpu_layers = self.gpu_combo.currentData()

        self.start_btn.setEnabled(False)
        self.start_btn.setText("⏳ 启动中...")

        # 使用定时器让 UI 响应
        from PySide6.QtCore import QMetaObject, Qt
        QTimer.singleShot(100, lambda: self._do_start(str(local_path), model_name, gpu_layers, ctx_size, threads))

    def _do_start(self, path, name, gpu, ctx, threads):
        success = self.engine.load_model(path, name, gpu, ctx, threads)
        if not success:
            self.start_btn.setEnabled(True)
            self.start_btn.setText("▶ 启动模型")
            QMessageBox.critical(self, "启动失败", "模型启动失败，请检查日志")

    def _on_stop_clicked(self):
        self.engine.stop()

    def refresh(self):
        self._refresh_local_models()
