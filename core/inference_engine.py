"""
推理引擎 - 通过 subprocess 管理 llama-server 进程
llama-server 自带 OpenAI 兼容的 HTTP API
"""
import os
import sys
import time
import socket
import subprocess
import threading
from pathlib import Path
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from ..config import get_llama_server_path, get_settings


@dataclass
class EngineStatus:
    """引擎状态"""
    running: bool = False
    model_name: str = ""
    model_path: str = ""
    port: int = 11434
    host: str = "127.0.0.1"
    pid: int = 0
    started_at: float = 0.0
    total_tokens: int = 0
    tokens_per_sec: float = 0.0
    gpu_layers: int = 0
    ctx_size: int = 4096
    threads: int = 0


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """检查端口是否被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def wait_for_port(port: int, host: str = "127.0.0.1", timeout: float = 30.0) -> bool:
    """等待端口可用"""
    start = time.time()
    while time.time() - start < timeout:
        if is_port_in_use(port, host):
            return True
        time.sleep(0.5)
    return False


class InferenceEngine(QObject):
    """
    推理引擎 - 管理 llama-server 进程
    """
    status_changed = Signal(object)   # EngineStatus
    log_message = Signal(str)         # 日志消息
    model_loaded = Signal(str)        # 模型名称
    model_unloaded = Signal()
    error_occurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process: Optional[subprocess.Popen] = None
        self._status = EngineStatus()
        self._log_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._settings = get_settings()

    @property
    def status(self) -> EngineStatus:
        return self._status

    def is_running(self) -> bool:
        if self._process is None or self._process.poll() is not None:
            return False
        return True

    def load_model(self, model_path: str, model_name: str = "",
                   gpu_layers: int = 0, ctx_size: int = 4096,
                   threads: int = 0, batch_size: int = 2048,
                   extra_args: Optional[List[str]] = None) -> bool:
        """
        加载模型并启动 llama-server

        Args:
            model_path: GGUF 模型文件路径
            model_name: 模型显示名称（用于 API 中标识）
            gpu_layers: GPU 层数，0 = 全 CPU，-1 = 全 GPU
            ctx_size: 上下文大小
            threads: CPU 线程数，0 = auto
            batch_size: 批处理大小
            extra_args: 额外命令行参数
        """
        # 如果已有模型在运行，先停止
        if self.is_running():
            self.stop()
            time.sleep(1)

        server_path = get_llama_server_path()
        if not server_path.exists():
            self.error_occurred.emit(f"找不到 llama-server: {server_path}")
            return False

        model_file = Path(model_path)
        if not model_file.exists():
            self.error_occurred.emit(f"找不到模型文件: {model_path}")
            return False

        host = self._settings.get('api_host', '127.0.0.1')
        port = self._settings.get('api_port', 11434)

        # 检查端口
        if is_port_in_use(port, host):
            self.error_occurred.emit(f"端口 {port} 已被占用")
            return False

        # 构建命令行参数
        cmd = [
            str(server_path),
            '-m', str(model_file),
            '--host', host,
            '--port', str(port),
            '-c', str(ctx_size),
            '-b', str(batch_size),
            '--api-key', self._settings.get('api_key', 'llmstudio-local-key'),
            '--metrics',  # 启用性能指标
            '--no-webui', # 禁用内置 webui
        ]

        if threads > 0:
            cmd.extend(['-t', str(threads)])

        if gpu_layers != 0:
            cmd.extend(['-ngl', str(gpu_layers)])

        # 设置模型别名（用于 API 的 model 参数）
        if model_name:
            cmd.extend(['--alias', model_name])

        if extra_args:
            cmd.extend(extra_args)

        self.log_message.emit(f"启动命令: {' '.join(cmd)}")

        try:
            # 设置启动参数
            startupinfo = None
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=os.environ.copy(),
                startupinfo=startupinfo,
            )

            # 启动日志读取线程
            self._stop_event.clear()
            self._log_thread = threading.Thread(target=self._read_logs, daemon=True)
            self._log_thread.start()

            # 等待服务器启动
            self.log_message.emit("等待 llama-server 启动...")
            if not wait_for_port(port, host, timeout=60):
                self.error_occurred.emit("llama-server 启动超时")
                self._force_kill()
                return False

            # 更新状态
            self._status = EngineStatus(
                running=True,
                model_name=model_name or model_file.stem,
                model_path=str(model_file),
                port=port,
                host=host,
                pid=self._process.pid,
                started_at=time.time(),
                gpu_layers=gpu_layers,
                ctx_size=ctx_size,
                threads=threads,
            )
            self.status_changed.emit(self._status)
            self.model_loaded.emit(self._status.model_name)

            self.log_message.emit(
                f"✓ 模型已加载: {self._status.model_name}\n"
                f"  API 地址: http://{host}:{port}/v1\n"
                f"  API Key: {self._settings.get('api_key')}"
            )
            return True

        except Exception as e:
            self.error_occurred.emit(f"启动失败: {str(e)}")
            self._process = None
            return False

    def _read_logs(self):
        """读取 llama-server 输出"""
        try:
            if self._process and self._process.stdout:
                for line in self._process.stdout:
                    if self._stop_event.is_set():
                        break
                    line = line.strip()
                    if line:
                        self.log_message.emit(line)
        except Exception:
            pass

    def stop(self):
        """停止推理引擎"""
        self._stop_event.set()

        if self._process is not None:
            try:
                # 优雅终止
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._force_kill()
            except Exception:
                self._force_kill()

            self._process = None

        self._status = EngineStatus()
        self.status_changed.emit(self._status)
        self.model_unloaded.emit()
        self.log_message.emit("模型已停止")

    def _force_kill(self):
        """强制终止进程"""
        if self._process is not None:
            try:
                if sys.platform == 'win32':
                    import subprocess as sp
                    sp.run(['taskkill', '/F', '/T', '/PID', str(self._process.pid)],
                           capture_output=True)
                else:
                    import signal
                    os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass

    def restart(self) -> bool:
        """重启引擎"""
        if self._status.model_path:
            path = self._status.model_path
            name = self._status.model_name
            gpu = self._status.gpu_layers
            ctx = self._status.ctx_size
            threads = self._status.threads
            self.stop()
            time.sleep(1)
            return self.load_model(path, name, gpu, ctx, threads)
        return False

    def poll_status(self) -> Optional[Dict]:
        """查询 llama-server 状态 API"""
        try:
            import urllib.request
            import json

            url = f"http://{self._status.host}:{self._status.port}/health"
            req = urllib.request.Request(url)
            req.add_header('Authorization', f"Bearer {self._settings.get('api_key')}")

            with urllib.request.urlopen(req, timeout=2) as resp:
                return json.loads(resp.read())
        except Exception:
            return None
