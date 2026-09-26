"""
API 服务器 - FastAPI 提供额外的管理 API
OpenAI 兼容的推理 API 由 llama-server 提供
"""
import time
import threading
import uvicorn
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .inference_engine import InferenceEngine
from .model_manager import ModelManager
from ..config import get_settings


class APIServer:
    """
    管理 API 服务器
    提供模型管理、状态查询等 REST API
    推理 API 由 llama-server 直接提供（OpenAI 兼容格式）
    """

    def __init__(self, engine: InferenceEngine, model_manager: ModelManager):
        self.engine = engine
        self.model_manager = model_manager
        self.settings = get_settings()
        self.app = FastAPI(title="EchoStudio Management API", version="1.0.0")
        self._server_thread: Optional[threading.Thread] = None
        self._server: Optional[uvicorn.Server] = None
        self._setup_routes()
        self._setup_middleware()

    def _setup_middleware(self):
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_routes(self):
        @self.app.get("/api/health")
        async def health():
            """健康检查"""
            return {
                "status": "ok",
                "engine_running": self.engine.is_running(),
                "api_url": self.settings.api_full_url,
            }

        @self.app.get("/api/status")
        async def status():
            """获取引擎状态"""
            s = self.engine.status
            return {
                "running": s.running,
                "model_name": s.model_name,
                "model_path": s.model_path,
                "host": s.host,
                "port": s.port,
                "pid": s.pid,
                "uptime": time.time() - s.started_at if s.running else 0,
                "ctx_size": s.ctx_size,
                "gpu_layers": s.gpu_layers,
                "engine_api_url": f"http://{s.host}:{s.port}/v1" if s.running else None,
                "api_key": self.settings.get('api_key'),
            }

        @self.app.get("/api/models")
        async def list_models():
            """列出本地模型"""
            models = self.model_manager.get_local_models()
            return {
                "models": [
                    {
                        "name": m.name,
                        "filename": m.filename,
                        "size_category": m.size_category,
                        "quantization": m.quantization,
                        "local_path": m.local_path,
                        "file_size_mb": round(m.file_size / (1024 * 1024), 1),
                    }
                    for m in models
                ]
            }

        @self.app.get("/api/presets")
        async def list_presets():
            """列出预设模型"""
            models = self.model_manager.get_preset_models()
            downloaded = {m.filename for m in self.model_manager.get_local_models()}
            return {
                "models": [
                    {
                        "name": m.name,
                        "repo_id": m.repo_id,
                        "filename": m.filename,
                        "size_category": m.size_category,
                        "quantization": m.quantization,
                        "description": m.description,
                        "downloaded": m.filename in downloaded,
                    }
                    for m in models
                ]
            }

        @self.app.post("/api/engine/start")
        async def start_engine(req: Dict[str, Any]):
            """启动引擎"""
            model_path = req.get('model_path')
            model_name = req.get('model_name', '')
            gpu_layers = req.get('gpu_layers', 0)
            ctx_size = req.get('ctx_size', 4096)
            threads = req.get('threads', 0)

            if not model_path:
                raise HTTPException(400, "model_path is required")

            success = self.engine.load_model(
                model_path=model_path,
                model_name=model_name,
                gpu_layers=gpu_layers,
                ctx_size=ctx_size,
                threads=threads,
            )
            return {"success": success}

        @self.app.post("/api/engine/stop")
        async def stop_engine():
            """停止引擎"""
            self.engine.stop()
            return {"success": True}

    def start(self, host: str = "127.0.0.1", port: int = 11435):
        """在后台线程启动管理 API"""
        if self._server_thread and self._server_thread.is_alive():
            return

        def run_server():
            config = uvicorn.Config(self.app, host=host, port=port, log_level="warning")
            self._server = uvicorn.Server(config)
            self._server.run()

        self._server_thread = threading.Thread(target=run_server, daemon=True)
        self._server_thread.start()

    def stop(self):
        """停止管理 API"""
        if self._server:
            try:
                self._server.should_exit = True
            except Exception:
                pass
        self._server_thread = None
