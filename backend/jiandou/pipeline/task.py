"""Task/Job 数据模型 — 统一的任务定义。

Task 是生成任务的核心数据模型，从创建到完成贯穿整个 pipeline。
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Optional


class TaskMode(StrEnum):
    T2V = "t2v"
    I2V = "i2v"
    FFLF = "fflf"
    EXTEND = "extend"
    A2V = "a2v"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class UpscaleMode(StrEnum):
    NONE = "none"
    PIPER = "piper"
    MODEL = "model"
    BOTH = "both"


class PresetName(StrEnum):
    FAST = "fast"
    BALANCED = "balanced"
    QUALITY = "quality"


class Task:
    """生成任务的核心数据模型。

    包含输入参数、引擎配置、后处理选项、输出结果和时间戳。
    """

    __slots__ = (
        "id", "mode", "status", "priority",
        "prompt", "negative_prompt", "image_path", "audio_path", "keyframes",
        "duration", "width", "height", "fps", "steps", "cfg", "seed", "preset",
        "model_version", "pipeline", "fp16", "low_memory",
        "upscale", "upscale_factor", "generate_audio", "audio_prompt",
        "output_path", "preview_path", "metadata",
        "created_at", "started_at", "completed_at",
        "progress", "stage", "current_step", "total_steps", "eta_seconds", "error_message",
    )

    def __init__(
        self,
        mode: TaskMode = TaskMode.T2V,
        prompt: str = "",
        negative_prompt: str = "",
        priority: int = 0,
        task_id: Optional[str] = None,
        image_path: Optional[str] = None,
        audio_path: Optional[str] = None,
        keyframes: Optional[list] = None,
        duration: float = 5.0,
        width: int = 768,
        height: int = 512,
        fps: int = 24,
        steps: int = 8,
        cfg: float = 2.0,
        seed: int = -1,
        preset: str = "balanced",
        model_version: str = "2.3",
        pipeline: str = "auto",
        fp16: bool = True,
        low_memory: bool = False,
        upscale: str = "none",
        upscale_factor: float = 2.0,
        generate_audio: bool = False,
        audio_prompt: str = "",
    ):
        self.id = task_id or str(uuid.uuid4())
        self.mode = mode if isinstance(mode, TaskMode) else TaskMode(mode)
        self.status = TaskStatus.PENDING
        self.priority = priority

        # Input
        self.prompt = prompt
        self.negative_prompt = negative_prompt
        self.image_path = image_path
        self.audio_path = audio_path
        self.keyframes = keyframes or []

        # Params
        self.duration = duration
        self.width = width
        self.height = height
        self.fps = fps
        self.steps = steps
        self.cfg = cfg
        self.seed = seed
        self.preset = preset

        # Engine
        self.model_version = model_version
        self.pipeline = pipeline
        self.fp16 = fp16
        self.low_memory = low_memory

        # Post
        self.upscale = upscale
        self.upscale_factor = upscale_factor
        self.generate_audio = generate_audio
        self.audio_prompt = audio_prompt

        # Output
        self.output_path: Optional[str] = None
        self.preview_path: Optional[str] = None
        self.metadata: dict = {}

        # Timestamps
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None

        # Progress
        self.progress: float = 0.0
        self.stage: str = ""
        self.current_step: int = 0
        self.total_steps: int = 0
        self.eta_seconds: Optional[float] = None
        self.error_message: Optional[str] = None

    @property
    def num_frames(self) -> int:
        """计算 8k+1 格式的帧数。"""
        raw = int(self.duration * self.fps)
        return raw + 1

    @property
    def is_terminal(self) -> bool:
        return self.status in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED)

    @property
    def elapsed_seconds(self) -> Optional[float]:
        """已运行时间（秒）。"""
        if self.started_at is None:
            return None
        end = self.completed_at or datetime.now()
        return (end - self.started_at).total_seconds()

    def to_dict(self) -> dict:
        """转换为可序列化的字典（用于 SQLite / JSON API）。"""
        return {
            "id": self.id,
            "mode": self.mode.value,
            "status": self.status.value,
            "priority": self.priority,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "image_path": self.image_path,
            "audio_path": self.audio_path,
            "keyframes": self.keyframes,
            "duration": self.duration,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "steps": self.steps,
            "cfg": self.cfg,
            "seed": self.seed,
            "preset": self.preset,
            "model_version": self.model_version,
            "pipeline": self.pipeline,
            "fp16": self.fp16,
            "low_memory": self.low_memory,
            "upscale": self.upscale,
            "upscale_factor": self.upscale_factor,
            "generate_audio": self.generate_audio,
            "audio_prompt": self.audio_prompt,
            "output_path": self.output_path,
            "preview_path": self.preview_path,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.progress,
            "stage": self.stage,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "eta_seconds": self.eta_seconds,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """从字典恢复 Task 实例。"""
        task = cls(
            mode=data.get("mode", "t2v"),
            prompt=data.get("prompt", ""),
            negative_prompt=data.get("negative_prompt", ""),
            priority=data.get("priority", 0),
            task_id=data["id"],
            image_path=data.get("image_path"),
            audio_path=data.get("audio_path"),
            keyframes=data.get("keyframes", []),
            duration=data.get("duration", 5.0),
            width=data.get("width", 768),
            height=data.get("height", 512),
            fps=data.get("fps", 24),
            steps=data.get("steps", 8),
            cfg=data.get("cfg", 2.0),
            seed=data.get("seed", -1),
            preset=data.get("preset", "balanced"),
            model_version=data.get("model_version", "2.3"),
            pipeline=data.get("pipeline", "auto"),
            fp16=data.get("fp16", True),
            low_memory=data.get("low_memory", False),
            upscale=data.get("upscale", "none"),
            upscale_factor=data.get("upscale_factor", 2.0),
            generate_audio=data.get("generate_audio", False),
            audio_prompt=data.get("audio_prompt", ""),
        )
        task.status = TaskStatus(data.get("status", "pending"))
        task.output_path = data.get("output_path")
        task.preview_path = data.get("preview_path")
        task.metadata = data.get("metadata", {})
        task.progress = data.get("progress", 0.0)
        task.stage = data.get("stage", "")
        task.current_step = data.get("current_step", 0)
        task.total_steps = data.get("total_steps", 0)
        task.eta_seconds = data.get("eta_seconds")
        task.error_message = data.get("error_message")

        created = data.get("created_at")
        if created:
            task.created_at = datetime.fromisoformat(created) if isinstance(created, str) else created
        started = data.get("started_at")
        if started:
            task.started_at = datetime.fromisoformat(started) if isinstance(started, str) else started
        completed = data.get("completed_at")
        if completed:
            task.completed_at = datetime.fromisoformat(completed) if isinstance(completed, str) else completed

        return task
