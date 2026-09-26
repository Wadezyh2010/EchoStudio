"""
设置页面
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QSpinBox,
    QComboBox, QPushButton, QGroupBox, QFormLayout, QMessageBox,
    QFileDialog, QCheckBox
)

from ..config import get_settings, get_models_dir


class SettingsPage(QWidget):
    """设置页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = get_settings()
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 标题
        title = QLabel("设置")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        subtitle = QLabel("自定义 API 端口、默认参数和运行行为")
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)

        # API 设置
        api_group = QGroupBox("API 设置")
        api_form = QFormLayout(api_group)
        api_form.setSpacing(12)

        self.host_edit = QLineEdit()
        self.host_edit.setPlaceholderText("127.0.0.1")
        api_form.addRow("监听地址:", self.host_edit)

        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        api_form.addRow("监听端口:", self.port_spin)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("llmstudio-local-key")
        api_form.addRow("API Key:", self.api_key_edit)

        note = QLabel("⚠️ 更改 API 端口或 Key 需要重启模型才能生效")
        note.setStyleSheet("color: #e0af68; font-size: 11px;")
        note.setWordWrap(True)
        api_form.addRow(note)

        layout.addWidget(api_group)

        # 默认参数
        param_group = QGroupBox("默认运行参数")
        param_form = QFormLayout(param_group)
        param_form.setSpacing(12)

        self.def_threads_spin = QSpinBox()
        self.def_threads_spin.setRange(0, 256)
        self.def_threads_spin.setSpecialValueText("自动")
        param_form.addRow("默认 CPU 线程:", self.def_threads_spin)

        self.def_ctx_spin = QSpinBox()
        self.def_ctx_spin.setRange(512, 131072)
        self.def_ctx_spin.setSingleStep(512)
        param_form.addRow("默认上下文大小:", self.def_ctx_spin)

        self.def_backend_combo = QComboBox()
        self.def_backend_combo.addItem("自动检测", "auto")
        self.def_backend_combo.addItem("CPU", "cpu")
        self.def_backend_combo.addItem("CUDA (NVIDIA GPU)", "cuda")
        self.def_backend_combo.addItem("Vulkan", "vulkan")
        self.def_backend_combo.addItem("OpenCL", "opencl")
        param_form.addRow("首选后端:", self.def_backend_combo)

        layout.addWidget(param_group)

        # 数据目录
        dir_group = QGroupBox("数据存储")
        dir_form = QFormLayout(dir_group)
        dir_form.setSpacing(12)

        model_dir = get_models_dir()
        self.dir_label = QLabel(str(model_dir))
        self.dir_label.setStyleSheet("font-family: Consolas, monospace; color: #7aa2f7;")
        self.dir_label.setWordWrap(True)
        dir_form.addRow("模型目录:", self.dir_label)

        open_dir_btn = QPushButton("📂 打开目录")
        open_dir_btn.clicked.connect(self._open_models_dir)
        dir_form.addRow(open_dir_btn)

        layout.addWidget(dir_group)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        reset_btn = QPushButton("重置")
        reset_btn.clicked.connect(self._reset_settings)
        btn_layout.addWidget(reset_btn)

        save_btn = QPushButton("💾 保存设置")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save_settings)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

    def _load_settings(self):
        s = self._settings
        self.host_edit.setText(str(s.get('api_host', '127.0.0.1')))
        self.port_spin.setValue(int(s.get('api_port', 11434)))
        self.api_key_edit.setText(str(s.get('api_key', 'llmstudio-local-key')))
        self.def_threads_spin.setValue(int(s.get('default_threads', 0)))
        self.def_ctx_spin.setValue(int(s.get('default_ctx_size', 4096)))

        backend = s.get('preferred_backend', 'auto')
        idx = self.def_backend_combo.findData(backend)
        if idx >= 0:
            self.def_backend_combo.setCurrentIndex(idx)

    def _save_settings(self):
        self._settings.set('api_host', self.host_edit.text().strip() or '127.0.0.1')
        self._settings.set('api_port', self.port_spin.value())
        self._settings.set('api_key', self.api_key_edit.text().strip() or 'llmstudio-local-key')
        self._settings.set('default_threads', self.def_threads_spin.value())
        self._settings.set('default_ctx_size', self.def_ctx_spin.value())
        self._settings.set('preferred_backend', self.def_backend_combo.currentData())

        QMessageBox.information(self, "保存成功", "设置已保存。部分更改需要重启模型才能生效。")

    def _reset_settings(self):
        reply = QMessageBox.question(self, "确认重置", "确定要重置为默认设置吗？")
        if reply == QMessageBox.Yes:
            import json
            from pathlib import Path
            settings_file = Path.home() / '.config' / 'EchoStudio' / 'settings.json'
            if settings_file.exists():
                settings_file.unlink()
            # 重新加载
            from ..config import _settings_instance
            if _settings_instance:
                _settings_instance._settings = _settings_instance.DEFAULT_SETTINGS.copy()
            self._load_settings()

    def _open_models_dir(self):
        import subprocess
        import os
        model_dir = get_models_dir()
        if os.path.exists(str(model_dir)):
            subprocess.Popen(['explorer', str(model_dir)])
