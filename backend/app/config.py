from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置，从环境变量或 .env 文件加载"""

    # Database
    database_url: str = "postgresql+asyncpg://slice:slice_dev@localhost:5433/ai_slice"

    # LLM：支持任意 OpenAI 兼容接口，当前项目默认使用阿里云百炼千问
    llm_api_key: str = ""
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen-plus"

    # ASR provider：默认复用百炼 API Key 调用千问录音文件转写
    asr_provider: str = "dashscope"
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/api/v1"
    dashscope_asr_model: str = "qwen-audio-3.0-asr-flash-filetrans"
    dashscope_asr_poll_interval_seconds: float = 3.0
    dashscope_asr_timeout_seconds: int = 7200

    # Groq ASR（可选回退）
    groq_api_key: str = ""
    groq_asr_model: str = "whisper-large-v3-turbo"
    groq_asr_chunk_minutes: int = 25

    # 本地文件存储
    storage_dir: str = "./storage"

    # Pipeline
    temp_dir: str = "/tmp/ai-slice"

    # 本机 FFmpeg 可执行文件目录（大文件本地导出及历史任务时长补救需要）
    ffmpeg_bin_dir: str = ""

    # Worker 后台协程池大小：同一时刻最多并行处理的任务数
    # 纯前端 FFmpeg 架构下服务端只做 ASR + LLM（纯网络 I/O），无 CPU 抢核
    # 真正瓶颈是 ASR / LLM 的 API 并发限制，可放心调高
    worker_concurrency: int = 10

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
