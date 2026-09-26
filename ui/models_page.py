"""
模型管理页面 - 浏览、下载、删除模型
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QComboBox, QLineEdit, QScrollArea, QGridLayout, QMessageBox,
    QProgressBar, QSizePolicy, QSpacerItem, QGroupBox, QFileDialog
)

from ..core.model_manager import ModelManager, ModelInfo, ModelDownloadThread


class ModelCard(QFrame):
    """单个模型卡片"""

    download_requested = Signal(object)   # ModelInfo
    delete_requested = Signal(object)     # ModelInfo
    launch_requested = Signal(object)     # ModelInfo

    def __init__(self, model: ModelInfo, downloaded: bool = False, parent=None):
        super().__init__(parent)
        self.model = model
        self.downloaded = downloaded
        self.setObjectName("modelCard")

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # 顶部：名称和标签
        top_row = QHBoxLayout()

        name_col = QVBoxLayout()
        name = QLabel(self.model.name)
        name.setObjectName("modelName")
        name.setWordWrap(True)
        name_col.addWidget(name)

        # 标签行
        tag_row = QHBoxLayout()
        size_tag = QLabel(f"📏 {self.model.size_category}")
        size_tag.setObjectName("modelSize")
        tag_row.addWidget(size_tag)

        quant_tag = QLabel(f"🔖 {self.model.quantization}")
        quant_tag.setObjectName("modelSize")
        tag_row.addWidget(quant_tag)

        type_tag_text = {
            "chat": "💬 对话",
            "base": "📚 基础",
            "code": "💻 代码",
            "vision": "👁️ 多模态",
        }.get(self.model.model_type, self.model.model_type)
        type_tag = QLabel(type_tag_text)
        type_tag.setObjectName("tagLabel")
        tag_row.addWidget(type_tag)

        if self.downloaded:
            dl_tag = QLabel("✓ 已下载")
            dl_tag.setObjectName("downloadedTag")
            tag_row.addWidget(dl_tag)

        tag_row.addStretch()
        name_col.addLayout(tag_row)
        top_row.addLayout(name_col, 1)

        layout.addLayout(top_row)

        # 描述
        if self.model.description:
            desc = QLabel(self.model.description)
            desc.setObjectName("modelDesc")
            desc.setWordWrap(True)
            layout.addWidget(desc)

        # Repo ID
        repo_label = QLabel(f"📂 {self.model.repo_id}")
        repo_label.setStyleSheet("font-family: Consolas, monospace; font-size: 11px; color: #565f89;")
        repo_label.setWordWrap(True)
        layout.addWidget(repo_label)

        # 文件信息
        file_label = QLabel(f"📄 {self.model.filename}")
        file_label.setStyleSheet("font-family: Consolas, monospace; font-size: 11px; color: #565f89;")
        file_label.setWordWrap(True)
        layout.addWidget(file_label)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        if self.downloaded:
            launch_btn = QPushButton("▶ 使用")
            launch_btn.setObjectName("primaryButton")
            launch_btn.clicked.connect(lambda: self.launch_requested.emit(self.model))
            btn_row.addWidget(launch_btn)

            delete_btn = QPushButton("🗑 删除")
            delete_btn.setObjectName("copyButton")
            delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.model))
            btn_row.addWidget(delete_btn)
        else:
            download_btn = QPushButton("⬇ 下载")
            download_btn.setObjectName("primaryButton")
            download_btn.clicked.connect(lambda: self.download_requested.emit(self.model))
            btn_row.addWidget(download_btn)

        layout.addLayout(btn_row)

        # 下载进度条（隐藏）
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("")
        self.progress_label.setObjectName("pageSubtitle")
        self.progress_label.hide()
        layout.addWidget(self.progress_label)


class ModelsPage(QWidget):
    """模型管理页面"""

    launch_model = Signal(object)  # 请求切换到概览并加载模型

    def __init__(self, model_manager: ModelManager, parent=None):
        super().__init__(parent)
        self.model_manager = model_manager
        self._download_threads = {}  # filename -> ModelDownloadThread
        self._setup_ui()
        self._filter_categories()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 页面标题
        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title = QLabel("模型管理")
        title.setObjectName("pageTitle")
        title_col.addWidget(title)

        local_count = len(self.model_manager.get_local_models())
        total_size = ModelManager.format_size(self.model_manager.get_total_size())
        subtitle = QLabel(f"已下载 {local_count} 个模型 | 总占用 {total_size}")
        subtitle.setObjectName("pageSubtitle")
        self.subtitle_label = subtitle
        title_col.addWidget(subtitle)
        header.addLayout(title_col)
        header.addStretch()
        layout.addLayout(header)

        # 筛选和搜索
        filter_row = QHBoxLayout()
        filter_row.setSpacing(12)

        filter_row.addWidget(QLabel("规模:"))
        self.category_combo = QComboBox()
        self.category_combo.addItem("全部", None)
        self.category_combo.addItem("1-3B", "1-3B")
        self.category_combo.addItem("3-7B", "3-7B")
        self.category_combo.addItem("7-13B", "7-13B")
        self.category_combo.addItem("13-30B", "13-30B")
        self.category_combo.addItem("30B+", "30B+")
        self.category_combo.currentIndexChanged.connect(self._filter_categories)
        filter_row.addWidget(self.category_combo)

        filter_row.addWidget(QLabel("类型:"))
        self.type_combo = QComboBox()
        self.type_combo.addItem("全部", None)
        self.type_combo.addItem("对话模型", "chat")
        self.type_combo.addItem("基础模型", "base")
        self.type_combo.addItem("代码模型", "code")
        self.type_combo.currentIndexChanged.connect(self._filter_categories)
        filter_row.addWidget(self.type_combo)

        filter_row.addStretch()

        # 导入本地 GGUF
        import_btn = QPushButton("📂 导入 GGUF 文件")
        import_btn.clicked.connect(self._import_local_gguf)
        filter_row.addWidget(import_btn)

        layout.addLayout(filter_row)

        # 滚动区
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        self.cards_container = QWidget()
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(12)
        scroll.setWidget(self.cards_container)

        layout.addWidget(scroll, 1)

    def _filter_categories(self):
        """根据筛选条件显示模型"""
        # 清空现有卡片
        while self.cards_layout.count():
            child = self.cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        preset_models = self.model_manager.get_preset_models()
        local_filenames = {m.filename for m in self.model_manager.get_local_models()}

        cat_filter = self.category_combo.currentData()
        type_filter = self.type_combo.currentData()

        filtered = []
        for m in preset_models:
            if cat_filter and m.size_category != cat_filter:
                continue
            if type_filter and m.model_type != type_filter:
                continue
            filtered.append(m)

        # 添加已下载但不在预设中的模型
        for m in self.model_manager.get_local_models():
            if m.filename not in {pm.filename for pm in preset_models}:
                filtered.append(m)

        # 按列布局
        cols = 2
        for i, model in enumerate(filtered):
            downloaded = model.filename in local_filenames
            card = ModelCard(model, downloaded)
            card.download_requested.connect(self._on_download_requested)
            card.delete_requested.connect(self._on_delete_requested)
            card.launch_requested.connect(self._on_launch_requested)

            row = i // cols
            col = i % cols
            self.cards_layout.addWidget(card, row, col)

        if not filtered:
            empty_label = QLabel("暂无符合条件的模型")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #565f89; padding: 60px;")
            self.cards_layout.addWidget(empty_label, 0, 0, 1, cols)

        self._update_subtitle()

    def _update_subtitle(self):
        local_count = len(self.model_manager.get_local_models())
        total_size = ModelManager.format_size(self.model_manager.get_total_size())
        self.subtitle_label.setText(f"已下载 {local_count} 个模型 | 总占用 {total_size}")

    def _on_download_requested(self, model: ModelInfo):
        """开始下载模型"""
        if model.filename in self._download_threads:
            QMessageBox.information(self, "下载中", "该模型正在下载中...")
            return

        thread = ModelDownloadThread(model)
        self._download_threads[model.filename] = thread

        # 找到对应的卡片并更新进度
        def progress_cb(pct, msg):
            for i in range(self.cards_layout.count()):
                item = self.cards_layout.itemAt(i)
                if item and item.widget():
                    card = item.widget()
                    if isinstance(card, ModelCard) and card.model.filename == model.filename:
                        card.progress_bar.show()
                        card.progress_bar.setValue(pct)
                        card.progress_label.show()
                        card.progress_label.setText(msg)
                        card.progress_label.setStyleSheet(
                            "font-size: 11px; color: #7aa2f7;" if pct < 100
                            else "font-size: 11px; color: #9ece6a;"
                        )
                        break

        thread.progress.connect(progress_cb)
        thread.finished_download.connect(lambda path: self._on_download_finished(model, path))
        thread.error.connect(lambda err: self._on_download_error(model, err))
        thread.start()

    def _on_download_finished(self, model: ModelInfo, local_path: str):
        """下载完成"""
        self.model_manager.add_local_model(model, local_path)
        self._download_threads.pop(model.filename, None)

        # 移除进度条
        for i in range(self.cards_layout.count()):
            item = self.cards_layout.itemAt(i)
            if item and item.widget():
                card = item.widget()
                if isinstance(card, ModelCard) and card.model.filename == model.filename:
                    card.progress_bar.hide()
                    card.progress_label.hide()
                    break

        # 刷新列表显示下载状态
        self._filter_categories()

        QMessageBox.information(self, "下载完成",
            f"模型下载成功！\n\n{model.name}\n{local_path}")

    def _on_download_error(self, model: ModelInfo, error_msg: str):
        """下载出错"""
        self._download_threads.pop(model.filename, None)

        for i in range(self.cards_layout.count()):
            item = self.cards_layout.itemAt(i)
            if item and item.widget():
                card = item.widget()
                if isinstance(card, ModelCard) and card.model.filename == model.filename:
                    card.progress_bar.hide()
                    card.progress_label.setText(f"❌ {error_msg}")
                    card.progress_label.show()
                    break

        QMessageBox.warning(self, "下载失败", error_msg)

    def _on_delete_requested(self, model: ModelInfo):
        """删除模型"""
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除以下模型吗？\n\n{model.name}\n\n此操作不可恢复。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if self.model_manager.delete_model(model):
                self._filter_categories()
                QMessageBox.information(self, "已删除", "模型已成功删除")
            else:
                QMessageBox.critical(self, "删除失败", "无法删除模型文件")

    def _on_launch_requested(self, model: ModelInfo):
        """切换到概览页并加载模型"""
        self.launch_model.emit(model)

    def _import_local_gguf(self):
        """导入本地 GGUF 文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 GGUF 模型文件", "",
            "GGUF 文件 (*.gguf);;所有文件 (*.*)"
        )
        if path:
            model = ModelInfo(
                name=Path(path).stem,
                repo_id="local",
                filename=Path(path).name,
                size_category="本地",
                model_type="chat",
                quantization="本地",
                description="从本地导入的模型",
            )
            import shutil
            dest = self.model_manager.models_dir / Path(path).name
            if dest.exists():
                QMessageBox.warning(self, "文件已存在",
                    "同名模型已存在于本地仓库中")
            else:
                shutil.copy2(path, str(dest))
            self.model_manager.add_local_model(model, str(dest))
            self._filter_categories()
            QMessageBox.information(self, "导入成功",
                f"模型已导入到本地仓库")


from pathlib import Path
