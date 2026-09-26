# EchoStudio
简单的LLM
### 🎯 核心功能
功能 说明 模型下载 从 HuggingFace 自动下载 GGUF 模型，内置 12 个精选预设（1.5B~70B 5 档规模） 自动运行 一键启动 llama-server，自动占用端口并就绪 API 访问 OpenAI 兼容 API 地址`http://127.0.0.1:11434/v1` ，API Key 在侧边栏一键复制 性能监控 实时 CPU/内存/引擎资源 + 迷你折线图（GPU 有则自动检测） 自动启停 模型生命周期完整管理，关闭窗口自动清理

### 🔌 API 信息（默认）
Python

1
2
3
4
5
6

`# Python + OpenAI SDK
from openai import OpenAI
client = OpenAI(
    base_url="http://127.0.0.1:11434/v1",
    api_key="llmstudio-local-key",
)`

### 🚀 使用方式
开发模式运行：

Bash

1
2

`cd C:\Users\张赟豪\Desktop\AItool\source
python main.py`

打包 exe：

Bash

1
2
3

`cd C:\Users\张赟豪\Desktop\AItool\source
python build_exe.py
# 输出到 ../build/dist/LLMStudio/`

运行时数据： 模型和设置存储在`%APPDATA%\LLMStudio\` （自动创建）

### 🛠 技术栈
- GUI : PySide6 (Qt for Python) + 自定义暗色主题
- 推理引擎 : llama.cpp v0.5.0 CPU x64（内置预编译二进制）
- 模型下载 : huggingface_hub 库（支持断点续传）
- API : llama-server 提供 OpenAI 兼容接口 + FastAPI 管理接口
- 监控 : psutil + 自定义 QPainter 迷你图表
- 打包 : PyInstaller onedir 模式
