"""
全局配置管理
"""
import os
import sys
import json
import uuid
from pathlib import Path
from typing import Optional


def get_app_base_dir() -> Path:
    """获取应用基础目录（区分开发模式和打包模式）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的路径
        return Path(sys.executable).parent
    else:
        # 开发模式
        return Path(__file__).parent.parent.parent


def get_user_data_dir() -> Path:
    """获取用户数据目录"""
    if sys.platform == 'win32':
        base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
    else:
        base = Path.home() / '.config'
    data_dir = base / 'EchoStudio'
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_models_dir() -> Path:
    """获取模型存储目录"""
    models_dir = get_user_data_dir() / 'models'
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def get_llama_cpp_dir() -> Path:
    """获取 llama.cpp 可执行文件目录"""
    if getattr(sys, 'frozen', False):
        # PyInstaller onedir 模式下 _MEIPASS 指向 _internal 目录
        # 资源被打包为 _internal/EchoStudio/resources/llama-cpp/
        base = Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent))
        return base / 'EchoStudio' / 'resources' / 'llama-cpp'
    else:
        return Path(__file__).parent / 'resources' / 'llama-cpp'


def get_llama_server_path() -> Path:
    """获取 llama-server.exe 路径"""
    return get_llama_cpp_dir() / ('llama-server.exe' if sys.platform == 'win32' else 'llama-server')


class Settings:
    """应用设置管理"""

    DEFAULT_SETTINGS = {
        'api_port': 11434,
        'api_host': '127.0.0.1',
        'api_key': 'llmstudio-local-key',
        'default_threads': 0,  # 0 = auto
        'default_ctx_size': 4096,
        'default_batch_size': 2048,
        'preferred_backend': 'cpu',  # cpu, cuda, vulkan, opencl
        'theme': 'dark',
    }

    def __init__(self):
        self.settings_file = get_user_data_dir() / 'settings.json'
        self._settings = self._load()

    def _load(self) -> dict:
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 合并默认值
                    merged = {**self.DEFAULT_SETTINGS, **data}
                    return merged
            except Exception:
                pass
        return dict(self.DEFAULT_SETTINGS)

    def save(self):
        with open(self.settings_file, 'w', encoding='utf-8') as f:
            json.dump(self._settings, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default=None):
        return self._settings.get(key, default)

    def set(self, key: str, value):
        self._settings[key] = value
        self.save()

    @property
    def api_url(self) -> str:
        return f"http://{self.get('api_host')}:{self.get('api_port')}"

    @property
    def api_full_url(self) -> str:
        return f"{self.api_url}/v1"


# 全局单例
_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
