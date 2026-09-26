"""
日志页面 - 显示 llama-server 和应用运行日志
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor, QColor, QTextCharFormat, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QCheckBox, QComboBox
)


class LogsPage(QWidget):
    """运行日志页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._auto_scroll = True
        self._max_lines = 10000
        self._lines = []

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # 标题和工具栏
        header_row = QHBoxLayout()

        title_col = QVBoxLayout()
        title = QLabel("运行日志")
        title.setObjectName("pageTitle")
        title_col.addWidget(title)

        subtitle = QLabel("llama-server 和应用的实时输出")
        subtitle.setObjectName("pageSubtitle")
        title_col.addWidget(subtitle)

        header_row.addLayout(title_col)
        header_row.addStretch()

        # 工具栏按钮
        self.auto_scroll_check = QCheckBox("自动滚动")
        self.auto_scroll_check.setChecked(True)
        self.auto_scroll_check.stateChanged.connect(self._toggle_auto_scroll)
        header_row.addWidget(self.auto_scroll_check)

        self.clear_btn = QPushButton("🗑 清空")
        self.clear_btn.clicked.connect(self.clear_logs)
        header_row.addWidget(self.clear_btn)

        layout.addLayout(header_row)

        # 日志显示
        self.log_view = QTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        self.log_view.setLineWrapMode(QTextEdit.NoWrap)
        layout.addWidget(self.log_view, 1)

    def _toggle_auto_scroll(self, state):
        self._auto_scroll = state == Qt.Checked

    def append_log(self, message: str, level: str = "info"):
        """追加一条日志"""
        if not message:
            return

        # 简单的日志级别检测
        level = level.lower()
        if 'error' in message.lower() or 'fail' in message.lower():
            level = "error"
        elif 'warn' in message.lower():
            level = "warning"
        elif any(kw in message.lower() for kw in ['success', 'loaded', 'running', 'ok', '✓']):
            level = "success"

        # 设置颜色
        colors = {
            "info": "#a9b1d6",
            "success": "#9ece6a",
            "warning": "#e0af68",
            "error": "#f7768e",
            "system": "#7aa2f7",
        }
        color = colors.get(level, "#a9b1d6")

        # 追加到 QTextEdit
        cursor = self.log_view.textCursor()
        cursor.movePosition(QTextCursor.End)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        fmt.setFontFamilies(["Consolas", "Cascadia Code", "Microsoft YaHei UI"])
        fmt.setFontPointSize(10)

        cursor.insertText(message + "\n", fmt)

        if self._auto_scroll:
            self.log_view.setTextCursor(cursor)
            self.log_view.ensureCursorVisible()

        # 限制最大行数
        if self.log_view.document().blockCount() > self._max_lines:
            self.log_view.setPlainText(
                "\n".join(self.log_view.toPlainText().split("\n")[-self._max_lines:])
            )

    def clear_logs(self):
        """清空日志"""
        self.log_view.clear()
        self.append_log("日志已清空", "system")
