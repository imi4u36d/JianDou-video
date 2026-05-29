"""Pydantic 请求/响应模型 — API 数据校验和序列化。"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class TaskModeEnum(StrEnum):
    T2V = "t2v"
    I2V = "i2v"
    FFLF = "fflf"
    EXTEND = "extend"
    A2V = "a2v"


class TaskStatusEnum(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class UpscaleEnum(StrEnum):
    NONE = "none"
    PIPER = "piper"
    MODEL = "model"
    BOTH = "both"


class PresetEnum(StrEnum):
    FAST = "fast"
    BALANCED = "balanced"
    QUALITY = "quality"


# ── Request Schemas ──────────────────────────────────────────────────


class GenerateRequest(BaseModel):
    """POST /api/v1/generate 请求体。"""

    mode: TaskModeEnum = TaskModeEnum.T2V
    prompt: str = Field(..., min_length=1, max_length=4096)
    negative_prompt: str = ""
    image_path: Optional[str] = None
    audio_path: Optional[str] = None

    duration: float = Field(default=5.0, ge=1.0, le=30.0)
    width: int = Field(default=768, ge=256, le=2048)
    height: int = Field(default=512, ge=128, le=1280)
    fps: int = Field(default=24, ge=8, le=60)
    steps: int = Field(default=8, ge=1, le=50)
    cfg: float = Field(default=2.0, ge=0.0, le=20.0)
    seed: int = Field(default=-1, ge=-1)
    preset: PresetEnum = PresetEnum.BALANCED

    model_version: str = "2.3"
    pipeline: str = "auto"
    fp16: bool = True
    low_memory: bool = False

    upscale: UpscaleEnum = UpscaleEnum.NONE
    upscale_factor: float = 2.0
    generate_audio: bool = False
    audio_prompt: str = ""

    priority: int = Field(default=0, ge=-10, le=10)

    @field_validator("pipeline")
    @classmethod
    def valid_pipeline(cls, v: str) -> str:
        allowed = {"auto", "distilled", "one-stage", "two-stage"}
        if v not in allowed:
            raise ValueError(f"pipeline must be one of {allowed}")
        return v


class ModelDownloadRequest(BaseModel):
    """POST /api/v1/models/download 请求体。"""

    repo: str = Field(..., min_length=1)
    filename: str = ""
    revision: str = "main"


class ConfigUpdateRequest(BaseModel):
    """PATCH /api/v1/system/config 请求体。"""

    server: Optional[dict[str, Any]] = None
    engine: Optional[dict[str, Any]] = None
    queue: Optional[dict[str, Any]] = None
    generation: Optional[dict[str, Any]] = None
    post: Optional[dict[str, Any]] = None


class PromptEnhanceRequest(BaseModel):
    """POST /api/v1/prompt/enhance 请求体。"""

    prompt: str = Field(..., min_length=1, max_length=4096)
    style: str = "cinematic"


# ── Response Schemas ─────────────────────────────────────────────────


class TaskResponse(BaseModel):
    """任务响应（API 对外）。"""

    id: str
    mode: str
    status: str
    priority: int
    prompt: str
    negative_prompt: str = ""
    image_path: Optional[str] = None
    audio_path: Optional[str] = None
    duration: float
    width: int
    height: int
    fps: int
    steps: int
    cfg: float
    seed: int
    preset: str
    model_version: str
    pipeline: str
    fp16: bool
    low_memory: bool
    upscale: str
    upscale_factor: float
    generate_audio: bool
    audio_prompt: str = ""
    output_path: Optional[str] = None
    preview_path: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: float
    stage: str = ""
    current_step: int
    total_steps: int
    eta_seconds: Optional[float] = None
    error_message: Optional[str] = None

    @classmethod
    def from_task(cls, task) -> "TaskResponse":
        return cls(**task.to_dict())


class TaskListResponse(BaseModel):
    """任务列表响应。"""

    tasks: list[TaskResponse]
    total: int
    offset: int
    limit: int


class ModelEntryResponse(BaseModel):
    """模型条目响应。"""

    name: str
    repo: str
    filename: str
    local_path: str
    size_bytes: int
    version: str
    model_type: str
    downloaded: bool
    downloaded_at: Optional[str] = None
    sha256: Optional[str] = None


class ModelDownloadProgressResponse(BaseModel):
    """下载进度响应。"""

    name: str
    progress: float
    downloaded_bytes: int
    total_bytes: int
    speed_mbps: float
    eta_seconds: Optional[float] = None


class SystemInfoResponse(BaseModel):
    """系统信息响应。"""

    chip: str
    cpu_cores: int
    gpu_cores: int
    ram_gb: int
    ram_free_gb: int
    tier: str
    max_resolution: list[int]
    max_frames: int
    supports_fp16: bool
    supports_audio: bool
    ffmpeg_available: bool
    macos_version: str
    mlx_version: str


class ConfigResponse(BaseModel):
    """配置响应。"""

    server: dict[str, Any]
    engine: dict[str, Any]
    queue: dict[str, Any]
    generation: dict[str, Any]
    post: dict[str, Any]


class ErrorResponse(BaseModel):
    """错误响应。"""

    error: str
    detail: str = ""
    code: int = 400


class MessageResponse(BaseModel):
    """通用消息响应。"""

    message: str


class ProgressEvent(BaseModel):
    """WebSocket 进度事件。"""

    type: str = "task.progress"
    task_id: str
    data: dict[str, Any]
