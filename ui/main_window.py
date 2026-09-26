"""
主窗口 - 包含侧边栏和多页面切换
"""
import os
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QFontDatabase
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QStatusBar, QLabel
)

from .sidebar import Sidebar
from .dashboard_page import DashboardPage
from .models_page import ModelsPage
from .monitor_page import MonitorPage
from .logs_page import LogsPage
from .settings_page import SettingsPage

from ..core.inference_engine import InferenceEngine
from ..core.model_manager import ModelManager
from ..core.api_server import APIServer
from ..core.monitor import PerformanceMonitor
from ..config import get_settings


class MainWindow(QMainWindow):
    """EchoStudio 主窗口"""

    def __init__(self):
        super().__init__()

        self._settings = get_settings()

        # 核心组件
        self.engine = InferenceEngine(self)
        self.model_manager = ModelManager()
        self.monitor = PerformanceMonitor(self.engine, self)
        self.api_server = APIServer(self.engine, self.model_manager)

        # UI 组件
        self.sidebar = None
        self.content_stack = None
        self.pages = {}

        self._setup_window()
        self._setup_ui()
        self._setup_connections()

        # 启动后台服务
        self.monitor.start(1000)
        self.api_server.start(self._settings.get('api_host', '127.0.0.1'), 11435)

        # 初始状态
        self.sidebar.update_engine_status(False)
        self.logs_page.append_log("🚀 EchoStudio 已启动", "system")
        self.logs_page.append_log(f"📂 模型目录: {self.model_manager.models_dir}", "system")
        self.logs_page.append_log(f"🔧 llama-server 路径: {self.engine.status.model_path or '(待加载)'}", "info")
        self.logs_page.append_log(f"🌐 管理 API: http://127.0.0.1:11435/api/health", "info")
        self.logs_page.append_log(f"📊 性能监控已开启", "success")

    def _setup_window(self):
        self.setWindowTitle("EchoStudio - 本地 LLM 运行平台")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)

        # 设置应用图标（如果有的话）
        # self.setWindowIcon(QIcon("path/to/icon.png"))

    def _setup_ui(self):
        # 中央容器
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 侧边栏
        self.sidebar = Sidebar(self)
        main_layout.addWidget(self.sidebar)

        # 分割线
        divider = QWidget()
        divider.setFixedWidth(1)
        divider.setStyleSheet("background-color: #2a2b3d;")
        main_layout.addWidget(divider)

        # 内容区
        content = QWidget()
        content.setObjectName("contentArea")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.content_stack = QStackedWidget()
        content_layout.addWidget(self.content_stack)

        main_layout.addWidget(content, 1)

        # 创建各页面
        self.dashboard_page = DashboardPage(self.engine, self.model_manager, self.monitor)
        self.models_page = ModelsPage(self.model_manager)
        self.monitor_page = MonitorPage(self.engine, self.monitor)
        self.logs_page = LogsPage()
        self.settings_page = SettingsPage()

        # 添加到栈
        self.content_stack.addWidget(self.dashboard_page)  # 0: dashboard
        self.content_stack.addWidget(self.models_page)     # 1: models
        self.content_stack.addWidget(self.monitor_page)    # 2: monitor
        self.content_stack.addWidget(self.logs_page)       # 3: logs
        self.content_stack.addWidget(self.settings_page)   # 4: settings

        # 映射
        self.pages = {
            "dashboard": 0,
            "models": 1,
            "monitor": 2,
            "logs": 3,
            "settings": 4,
        }

        # 状态栏
        self.statusBar().showMessage("就绪")
        self.statusBar().setStyleSheet(
            "QStatusBar { background-color: #161721; color: #565f89; border-top: 1px solid #2a2b3d; }"
        )

    def _setup_connections(self):
        # 侧边栏导航
        self.sidebar.page_changed.connect(self._on_page_changed)

        # 引擎日志 -> 日志页面
        self.engine.log_message.connect(self.logs_page.append_log)

        # 引擎状态 -> 侧边栏 & 状态栏
        self.engine.model_loaded.connect(self._on_model_loaded)
        self.engine.model_unloaded.connect(self._on_model_unloaded)
        self.engine.error_occurred.connect(self._on_engine_error)

        # 模型管理页面的"使用"请求 -> 切换到概览
        self.models_page.launch_model.connect(self._on_launch_from_models)

    def _on_page_changed(self, page_name: str):
        idx = self.pages.get(page_name, 0)
        self.content_stack.setCurrentIndex(idx)

        # 切换到模型页面时刷新列表
        if page_name == "models":
            self.models_page._filter_categories()

    def _on_model_loaded(self, model_name: str):
        self.statusBar().showMessage(f"模型运行中: {model_name} | {self._settings.api_full_url}")
        self.sidebar.update_engine_status(True, model_name)

    def _on_model_unloaded(self):
        self.statusBar().showMessage("就绪")
        self.sidebar.update_engine_status(False)

    def _on_engine_error(self, error_msg: str):
        self.statusBar().showMessage(f"❌ 错误: {error_msg}")

    def _on_launch_from_models(self, model):
        """从模型页面切换到概览并选中该模型"""
        self.content_stack.setCurrentIndex(0)  # dashboard
        self.sidebar._select_page("dashboard")
        self.dashboard_page.refresh()

        # 尝试选中该模型
        for i in range(self.dashboard_page.model_combo.count()):
            data = self.dashboard_page.model_combo.itemData(i)
            if data and data.filename == model.filename:
                self.dashboard_page.model_combo.setCurrentIndex(i)
                break

    def closeEvent(self, event):
        """关闭窗口时清理资源"""
        try:
            self.monitor.stop()
            self.api_server.stop()
            self.engine.stop()
        except Exception:
            pass
        event.accept()

    def load_stylesheet(self):
        """加载 QSS 样式表"""
        qss_path = Path(__file__).parent / "styles.qss"
        if qss_path.exists():
            with open(qss_path, 'r', encoding='utf-8') as f:
                self.setStyleSheet(f.read())
