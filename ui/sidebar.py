"""
侧边栏导航组件
包含导航按钮和 API 信息卡片
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QFont
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QPushButton, QLabel, QHBoxLayout,
    QWidget, QScrollArea, QSizePolicy, QMessageBox, QApplication
)

from ..config import get_settings


class Sidebar(QFrame):
    """左侧导航栏"""

    page_changed = Signal(str)  # 页面名称: "dashboard", "models", "monitor", "logs"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(240)
        self._settings = get_settings()
        self._current_page = "dashboard"

        self._setup_ui()
        self._update_api_info()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Logo
        logo_label = QLabel("✦ EchoStudio")
        logo_label.setObjectName("logoLabel")
        logo_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo_label)

        version_label = QLabel("v1.0.0")
        version_label.setObjectName("versionLabel")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)

        # 导航按钮
        nav_container = QWidget()
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(12, 8, 12, 8)
        nav_layout.setSpacing(4)

        self.nav_buttons = {}
        nav_items = [
            ("dashboard", "🏠 概览"),
            ("models", "📦 模型管理"),
            ("monitor", "📊 性能监控"),
            ("logs", "📝 运行日志"),
            ("settings", "⚙️ 设置"),
        ]

        for key, text in nav_items:
            btn = QPushButton(text)
            btn.setObjectName("navButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, k=key: self._on_nav_clicked(k))
            nav_layout.addWidget(btn)
            self.nav_buttons[key] = btn

        nav_layout.addStretch()
        layout.addWidget(nav_container, 1)

        # API 信息卡片
        self.api_card = QFrame()
        self.api_card.setObjectName("apiCard")
        card_layout = QVBoxLayout(self.api_card)
        card_layout.setContentsMargins(12, 12, 12, 12)
        card_layout.setSpacing(6)

        title = QLabel("OpenAI 兼容 API")
        title.setObjectName("apiTitle")
        card_layout.addWidget(title)

        # API URL
        url_row = QHBoxLayout()
        url_label = QLabel("Endpoint")
        url_label.setObjectName("apiTitle")
        url_label.setFixedWidth(60)
        url_row.addWidget(url_label)

        self.api_url_label = QLabel("—")
        self.api_url_label.setObjectName("apiValue")
        self.api_url_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.api_url_label.setWordWrap(True)
        url_row.addWidget(self.api_url_label, 1)

        copy_url_btn = QPushButton("复制")
        copy_url_btn.setObjectName("copyButton")
        copy_url_btn.clicked.connect(lambda: self._copy_to_clipboard(self.api_url_label.text()))
        url_row.addWidget(copy_url_btn)

        card_layout.addLayout(url_row)

        # API Key
        key_row = QHBoxLayout()
        key_label = QLabel("API Key")
        key_label.setObjectName("apiTitle")
        key_label.setFixedWidth(60)
        key_row.addWidget(key_label)

        self.api_key_label = QLabel("—")
        self.api_key_label.setObjectName("apiValue")
        self.api_key_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        key_row.addWidget(self.api_key_label, 1)

        copy_key_btn = QPushButton("复制")
        copy_key_btn.setObjectName("copyButton")
        copy_key_btn.clicked.connect(lambda: self._copy_to_clipboard(self.api_key_label.text()))
        key_row.addWidget(copy_key_btn)

        card_layout.addLayout(key_row)

        # 分隔线
        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFrameShape(QFrame.HLine)
        card_layout.addWidget(divider)

        # 快速测试按钮
        test_btn = QPushButton("🧪 测试连接")
        test_btn.setObjectName("copyButton")
        test_btn.clicked.connect(self._test_api_connection)
        card_layout.addWidget(test_btn)

        layout.addWidget(self.api_card)

        # 设置默认选中
        self._select_page("dashboard")

    def _on_nav_clicked(self, page_name: str):
        self._select_page(page_name)
        self.page_changed.emit(page_name)

    def _select_page(self, page_name: str):
        self._current_page = page_name
        for key, btn in self.nav_buttons.items():
            btn.setChecked(key == page_name)

    def _copy_to_clipboard(self, text: str):
        if text and text != "—":
            QApplication.clipboard().setText(text)
            # 可以加个短暂的提示

    def _test_api_connection(self):
        import urllib.request
        import json

        url = f"{self._settings.api_url}/health"
        try:
            req = urllib.request.Request(url)
            req.add_header('Authorization', f"Bearer {self._settings.get('api_key')}")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read())
                QMessageBox.information(self, "连接成功",
                    f"API 服务器正在运行！\n\n状态: {data.get('status', 'ok')}\n推理引擎: {'运行中' if data.get('engine_running') else '未启动'}")
        except urllib.error.URLError as e:
            QMessageBox.warning(self, "连接失败",
                f"无法连接到 API 服务器\n\n错误: {str(e)}\n\n请先在概览页面启动模型")
        except Exception as e:
            QMessageBox.warning(self, "连接失败", f"错误: {str(e)}")

    def _update_api_info(self, running: bool = False, model_name: str = ""):
        """更新 API 信息显示"""
        url = self._settings.api_full_url
        key = self._settings.get('api_key', '')

        if running and model_name:
            self.api_url_label.setText(url)
            self.api_key_label.setText(key)
        else:
            self.api_url_label.setText(url)
            self.api_key_label.setText(key)

    def update_engine_status(self, is_running: bool, model_name: str = ""):
        """根据引擎状态更新侧边栏显示"""
        self._update_api_info(is_running, model_name)
        # 根据运行状态调整 URL 显示颜色
        if is_running:
            self.api_url_label.setStyleSheet("color: #9ece6a;")
        else:
            self.api_url_label.setStyleSheet("color: #565f89;")
