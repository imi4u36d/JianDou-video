"""进度事件系统 — 推理过程中的进度更新。

支持：
- 步级进度回调 (step/total + ETA)
- 中间帧预览 (base64 JPEG)
- 阶段变更通知 (encoding → denoising → decoding)
- WebSocket 事件序列化
"""

import base64
import io
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Optional


class ProgressPhase(StrEnum):
    """生成阶段。"""

    QUEUED = "queued"
    LOADING = "loading"  # 模型加载
    ENCODING = "encoding"  # 文本/图像编码
    DENOISING = "denoising"  # 扩散去噪
    DECODING = "decoding"  # VAE 解码
    UPSCALING = "upscaling"  # 超分
    COMPOSING = "composing"  # 合成
    DONE = "done"


@dataclass
class StepProgress:
    """单步进度快照。"""

    phase: ProgressPhase = ProgressPhase.QUEUED
    current_step: int = 0
    total_steps: int = 0
    progress: float = 0.0  # 0.0 - 1.0
    eta_seconds: Optional[float] = None
    preview_frame: Optional[str] = None  # base64 JPEG
    message: str = ""
    timestamp: float = field(default_factory=time.time)


class ProgressTracker:
    """进度跟踪器 — 负责计算进度、ETA 和事件分发。

    Usage:
        tracker = ProgressTracker(total_steps=8)
        tracker.set_phase(ProgressPhase.DENOISING)
        for i in range(steps):
            tracker.step(i)
            await tracker.emit()  # or callback
    """

    def __init__(
        self,
        total_steps: int = 8,
        on_update: Optional[Callable[[StepProgress], Any]] = None,
    ):
        self._total_steps = max(total_steps, 1)
        self._phase = ProgressPhase.QUEUED
        self._current_step = 0
        self._start_time = time.time()
        self._step_times: list[float] = []
        self._listeners: list[Callable[[StepProgress], Any]] = []
        if on_update:
            self._listeners.append(on_update)

        # Phase weights for overall progress calculation
        self._phase_weights = {
            ProgressPhase.LOADING: 0.10,
            ProgressPhase.ENCODING: 0.10,
            ProgressPhase.DENOISING: 0.50,
            ProgressPhase.DECODING: 0.20,
            ProgressPhase.UPSCALING: 0.05,
            ProgressPhase.COMPOSING: 0.05,
        }

    @property
    def current_step(self) -> int:
        return self._current_step

    @property
    def total_steps(self) -> int:
        return self._total_steps

    @property
    def phase(self) -> ProgressPhase:
        return self._phase

    def set_total_steps(self, n: int):
        self._total_steps = max(n, 1)

    def set_phase(self, phase: ProgressPhase, total_steps: Optional[int] = None):
        self._phase = phase
        self._current_step = 0
        if total_steps is not None:
            self._total_steps = total_steps
        self._notify()

    def step(self, step: Optional[int] = None, message: str = ""):
        """记录一步进度。"""
        if step is not None:
            self._current_step = step
        else:
            self._current_step += 1

        now = time.time()
        self._step_times.append(now)

        # Keep only last 10 for ETA smoothing
        if len(self._step_times) > 10:
            self._step_times.pop(0)

        self._notify(message)

    def set_preview(self, frame_array) -> Optional[str]:
        """将 MLX array 编码为 base64 JPEG 预览帧。"""
        try:
            import numpy as np
            from PIL import Image

            if hasattr(frame_array, "tolist"):
                frame_array = np.array(frame_array.tolist(), dtype=np.uint8)
            elif isinstance(frame_array, np.ndarray):
                pass
            else:
                return None

            img = Image.fromarray(frame_array)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=75)
            return base64.b64encode(buf.getvalue()).decode("ascii")
        except Exception:
            return None

    # ── computed ──────────────────────────────────────────────────────

    def compute_progress(self) -> float:
        """计算整体进度 (0.0 - 1.0)。"""
        # Phase already passed → 100% of its weight
        phase_order = [
            ProgressPhase.QUEUED,
            ProgressPhase.LOADING,
            ProgressPhase.ENCODING,
            ProgressPhase.DENOISING,
            ProgressPhase.DECODING,
            ProgressPhase.UPSCALING,
            ProgressPhase.COMPOSING,
            ProgressPhase.DONE,
        ]
        current_idx = phase_order.index(self._phase) if self._phase in phase_order else 0

        progress = 0.0
        for idx, p in enumerate(phase_order):
            weight = self._phase_weights.get(p, 0.0)
            if idx < current_idx:
                progress += weight
            elif idx == current_idx and p == ProgressPhase.DONE:
                progress += weight
            elif idx == current_idx:
                progress += weight * (self._current_step / max(self._total_steps, 1))

        return min(progress, 1.0)

    def compute_eta(self) -> Optional[float]:
        """计算预计剩余时间（秒）。"""
        if len(self._step_times) < 2 or self._current_step == 0:
            return None

        remaining = self._total_steps - self._current_step
        if remaining <= 0:
            return 0.0

        # Average time per step from recent samples
        step_deltas = [
            self._step_times[i] - self._step_times[i - 1]
            for i in range(1, len(self._step_times))
        ]
        avg_step_time = sum(step_deltas) / len(step_deltas)
        return avg_step_time * remaining

    def snapshot(self) -> StepProgress:
        """创建当前进度的快照。"""
        return StepProgress(
            phase=self._phase,
            current_step=self._current_step,
            total_steps=self._total_steps,
            progress=self.compute_progress(),
            eta_seconds=self.compute_eta(),
        )

    # ── internal ──────────────────────────────────────────────────────

    def _notify(self, message: str = ""):
        snapshot = self.snapshot()
        snapshot.message = message
        for listener in self._listeners:
            try:
                listener(snapshot)
            except Exception:
                pass

    def add_listener(self, listener: Callable[[StepProgress], Any]):
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[StepProgress], Any]):
        self._listeners = [l for l in self._listeners if l is not listener]
