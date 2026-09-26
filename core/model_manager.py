"""
模型管理器 - 从 HuggingFace 下载 GGUF 模型并管理本地模型库
"""
import os
import json
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, asdict
from PySide6.QtCore import QThread, Signal

from huggingface_hub import hf_hub_download, scan_cache_dir, HfApi

from ..config import get_models_dir


@dataclass
class ModelInfo:
    """模型信息"""
    name: str                    # 显示名称如 "Llama 3.1 8B Instruct"
    repo_id: str                 # HuggingFace repo id 如 "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF"
    filename: str                # GGUF 文件名如 "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"
    size_category: str           # 规模分类: "1-3B", "3-7B", "7-13B", "13-30B", "30B+"
    model_type: str              # 模型类型: "chat", "base", "code", "vision"
    quantization: str            # 量化级别: Q2_K, Q3_K_S, Q4_K_M, Q5_K_M, Q6_K, Q8_0
    description: str = ""
    tags: List[str] = None
    local_path: Optional[str] = None
    file_size: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'ModelInfo':
        return cls(**data)


# 预设模型目录（精选的高质量 GGUF 模型）
PRESET_MODELS = [
    # 小模型 1-3B
    ModelInfo("Qwen2.5 1.5B Instruct (Q4)", "bartowski/Qwen2.5-1.5B-Instruct-GGUF",
              "Qwen2.5-1.5B-Instruct-Q4_K_M.gguf", "1-3B", "chat", "Q4_K_M",
              "轻量级中文/英文双语助手，适合嵌入式设备"),
    ModelInfo("Phi-3-mini 4K (Q4)", "bartowski/Phi-3-mini-4k-instruct-GGUF",
              "Phi-3-mini-4k-instruct-Q4_K_M.gguf", "1-3B", "chat", "Q4_K_M",
              "微软出品，小身材大智慧的对话模型"),
    ModelInfo("Gemma 2 2B IT (Q4)", "bartowski/gemma-2-2b-it-GGUF",
              "gemma-2-2b-it-Q4_K_M.gguf", "1-3B", "chat", "Q4_K_M",
              "Google 轻量级指令微调模型"),

    # 3-7B 模型
    ModelInfo("Llama 3.2 3B Instruct (Q4)", "bartowski/Llama-3.2-3B-Instruct-GGUF",
              "Llama-3.2-3B-Instruct-Q4_K_M.gguf", "3-7B", "chat", "Q4_K_M",
              "Meta 最新小参数指令模型"),
    ModelInfo("Mistral 7B Instruct v0.3 (Q4)", "bartowski/mistral-7b-instruct-v0.3-GGUF",
              "mistral-7b-instruct-v0.3.Q4_K_M.gguf", "3-7B", "chat", "Q4_K_M",
              "法国 Mistral AI 出品的经典指令模型"),
    ModelInfo("Qwen2.5 7B Instruct (Q4)", "bartowski/Qwen2.5-7B-Instruct-GGUF",
              "Qwen2.5-7B-Instruct-Q4_K_M.gguf", "3-7B", "chat", "Q4_K_M",
              "阿里通义千问，中文能力优秀"),

    # 7-13B 模型
    ModelInfo("Llama 3.1 8B Instruct (Q4)", "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
              "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf", "7-13B", "chat", "Q4_K_M",
              "Meta 主力 8B 指令模型，综合能力强"),
    ModelInfo("Gemma 2 9B IT (Q4)", "bartowski/gemma-2-9b-it-GGUF",
              "gemma-2-9b-it-Q4_K_M.gguf", "7-13B", "chat", "Q4_K_M",
              "Google 最新 9B 指令模型"),
    ModelInfo("DeepSeek-Coder V2 16B (Q4)", "bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF",
              "DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M.gguf", "13-30B", "code", "Q4_K_M",
              "深度求索代码模型，编程能力卓越"),

    # 13-30B 模型
    ModelInfo("Llama 3.1 13B Instruct (Q4)", "bartowski/Meta-Llama-3.1-13B-Instruct-GGUF",
              "Meta-Llama-3.1-13B-Instruct-Q4_K_M.gguf", "13-30B", "chat", "Q4_K_M",
              "Meta 中等规模旗舰模型"),
    ModelInfo("Qwen2.5 14B Instruct (Q4)", "bartowski/Qwen2.5-14B-Instruct-GGUF",
              "Qwen2.5-14B-Instruct-Q4_K_M.gguf", "13-30B", "chat", "Q4_K_M",
              "阿里通义千问 14B 中文旗舰"),

    # 30B+ 模型
    ModelInfo("Llama 3.1 70B Instruct (Q4)", "bartowski/Meta-Llama-3.1-70B-Instruct-GGUF",
              "Meta-Llama-3.1-70B-Instruct-Q4_K_M.gguf", "30B+", "chat", "Q4_K_M",
              "Meta 顶级旗舰模型（需要大内存）"),
]


class ModelDownloadThread(QThread):
    """异步模型下载线程"""
    progress = Signal(int, str)     # 进度百分比, 状态消息
    finished_download = Signal(str)  # 下载完成后的本地路径
    error = Signal(str)              # 错误信息

    def __init__(self, model: ModelInfo, parent=None):
        super().__init__(parent)
        self.model = model
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            self.progress.emit(0, "正在准备下载...")

            save_dir = get_models_dir()
            local_path = save_dir / self.model.filename

            if local_path.exists():
                self.progress.emit(100, "模型已存在")
                self.finished_download.emit(str(local_path))
                return

            # 使用 huggingface_hub 下载
            os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

            def hf_progress_cb(chunk_number, chunk_size, file_size):
                if self._cancelled:
                    raise Exception("下载已取消")
                if file_size > 0:
                    pct = int(min(100, chunk_number * chunk_size / file_size * 100))
                    downloaded_mb = chunk_number * chunk_size / (1024 * 1024)
                    total_mb = file_size / (1024 * 1024)
                    self.progress.emit(pct, f"下载中: {downloaded_mb:.1f} / {total_mb:.1f} MB ({pct}%)")

            self.progress.emit(5, "正在连接 HuggingFace...")

            downloaded_path = hf_hub_download(
                repo_id=self.model.repo_id,
                filename=self.model.filename,
                local_dir=str(save_dir),
                local_dir_use_symlinks=False,
                resume_download=True,
            )

            # 确保文件在正确位置
            downloaded_path = Path(downloaded_path)
            if downloaded_path != local_path:
                if local_path.exists():
                    local_path.unlink()
                shutil.move(str(downloaded_path), str(local_path))

            self.progress.emit(100, "下载完成！")
            self.finished_download.emit(str(local_path))

        except Exception as e:
            if self._cancelled:
                self.error.emit("下载已取消")
            else:
                self.error.emit(f"下载失败: {str(e)}")


class ModelManager:
    """模型管理器"""

    def __init__(self):
        self.models_dir = get_models_dir()
        self.index_file = self.models_dir / 'index.json'
        self._local_models: Dict[str, dict] = {}
        self._load_index()

    def _load_index(self):
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    self._local_models = json.load(f)
            except Exception:
                self._local_models = {}

    def _save_index(self):
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(self._local_models, f, indent=2, ensure_ascii=False)

    def get_preset_models(self) -> List[ModelInfo]:
        """获取预设模型列表"""
        return PRESET_MODELS

    def search_hf_models(self, query: str, limit: int = 20) -> List[Dict]:
        """搜索 HuggingFace 上的 GGUF 模型"""
        try:
            api = HfApi()
            results = api.list_models(
                search=query,
                filter='gguf',
                limit=limit,
                full=True
            )
            models = []
            for m in results:
                # 找到 GGUF 文件
                siblings = getattr(m, 'siblings', []) or []
                gguf_files = [s.rfilename for s in siblings if s.rfilename.endswith('.gguf')]
                if gguf_files:
                    models.append({
                        'repo_id': m.id,
                        'name': getattr(m, 'modelId', m.id),
                        'tags': getattr(m, 'tags', []),
                        'gguf_files': gguf_files[:10],  # 最多显示 10 个
                    })
            return models
        except Exception as e:
            print(f"搜索 HF 模型失败: {e}")
            return []

    def add_local_model(self, model: ModelInfo, local_path: str):
        """添加已下载的本地模型"""
        path = Path(local_path)
        model.local_path = local_path
        model.file_size = path.stat().st_size if path.exists() else 0
        self._local_models[model.filename] = model.to_dict()
        self._save_index()

    def get_local_models(self) -> List[ModelInfo]:
        """获取所有本地已下载模型"""
        result = []
        for data in self._local_models.values():
            info = ModelInfo.from_dict(data)
            path = Path(info.local_path) if info.local_path else None
            if path and path.exists():
                info.file_size = path.stat().st_size
                result.append(info)
        return result

    def is_model_downloaded(self, model: ModelInfo) -> bool:
        """检查模型是否已下载"""
        local_path = self.models_dir / model.filename
        return local_path.exists()

    def get_model_local_path(self, model: ModelInfo) -> Optional[Path]:
        """获取模型本地路径"""
        local_path = self.models_dir / model.filename
        return local_path if local_path.exists() else None

    def delete_model(self, model: ModelInfo) -> bool:
        """删除本地模型"""
        try:
            local_path = self.get_model_local_path(model)
            if local_path:
                local_path.unlink()
            if model.filename in self._local_models:
                del self._local_models[model.filename]
            self._save_index()
            return True
        except Exception as e:
            print(f"删除模型失败: {e}")
            return False

    def get_total_size(self) -> int:
        """获取所有本地模型总大小"""
        total = 0
        for model in self.get_local_models():
            total += model.file_size
        return total

    @staticmethod
    def format_size(size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"
