"""任务执行器 — 独立任务执行的便捷包装。

组合 Task → Session → Progress → Output 的完整流程。
"""

import asyncio
import os
import time
from pathlib import Path
from typing import Optional

import numpy as np

from jiandou.pipeline.task import Task, TaskStatus
from jiandou.pipeline.progress import ProgressTracker, ProgressPhase, StepProgress


class TaskRunner:
    """单任务执行器。

    负责从 Task 创建 Session、监控进度、保存结果。

    Usage:
        runner = TaskRunner(task)
        result = await runner.run()
    """

    def __init__(self, task: Task):
        self.task = task
        self.tracker = ProgressTracker(total_steps=task.steps)
        self._cancelled = False

    async def run(self, checkpoint_path: str = "", gemma_path: str = "") -> Task:
        """执行任务并返回更新后的 Task。"""
        if not checkpoint_path:
            checkpoint_path = _resolve_checkpoint_path()
        if not gemma_path:
            gemma_path = _resolve_gemma_path()
        task = self.task

        if task.status == TaskStatus.CANCELLED:
            return task

        task.status = TaskStatus.RUNNING
        task.started_at = __import__("datetime").datetime.now()

        try:
            from jiandou.engine.session import InferenceSession, SessionConfig

            # Phase: Loading
            self.tracker.set_phase(ProgressPhase.LOADING)
            self._sync_progress_from_tracker(task)

            if self._cancelled:
                task.status = TaskStatus.CANCELLED
                return task

            session_config = SessionConfig(
                checkpoint_path=checkpoint_path,
                gemma_path=gemma_path,
                width=task.width,
                height=task.height,
                num_frames=task.num_frames,
                fps=task.fps,
                steps=task.steps,
                cfg=task.cfg,
                seed=task.seed if task.seed >= 0 else int(time.time() * 1000),
                prompt=task.prompt,
                negative_prompt=task.negative_prompt,
                image_path=task.image_path,
                audio_enabled=task.generate_audio,
                fp16=task.fp16,
                low_memory=task.low_memory,
                pipeline=task.pipeline,
                model_version=task.model_version,
                on_step=self._on_engine_step,
            )

            session = InferenceSession(session_config)

            if self._cancelled:
                task.status = TaskStatus.CANCELLED
                return task

            with session:
                # Phase: Denoising
                self.tracker.set_phase(ProgressPhase.DENOISING, total_steps=task.steps)

                if self._cancelled:
                    task.status = TaskStatus.CANCELLED
                    return task

                result = session.run()

                # Phase: Decoding (handled by pipeline internally)
                self.tracker.set_phase(ProgressPhase.DECODING)

                # Unpack result
                if isinstance(result, tuple):
                    video_array, audio_array = result
                else:
                    video_array, audio_array = result, None

                self._save_output(task, video_array, audio_array)

            # Done
            self.tracker.set_phase(ProgressPhase.DONE)
            task.status = TaskStatus.DONE
            task.progress = 1.0
            task.current_step = task.steps

        except asyncio.CancelledError:
            task.status = TaskStatus.CANCELLED
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
        finally:
            task.completed_at = __import__("datetime").datetime.now()

        return task

    def cancel(self):
        """取消任务。"""
        self._cancelled = True

    # ── internal ──────────────────────────────────────────────────────

    def _on_engine_step(self, step: int, total: int, stage: str = ""):
        """引擎步骤回调 — 更新 Task 和 ProgressTracker。"""
        self.task.current_step = step
        self.task.total_steps = total
        self.task.progress = step / max(total, 1)
        if stage:
            self.task.stage = stage
        self.tracker.step(step)

    def _sync_progress_from_tracker(self, task: Task):
        """从 ProgressTracker 同步进度到 Task。"""
        snap = self.tracker.snapshot()
        task.progress = snap.progress
        task.current_step = snap.current_step
        task.total_steps = snap.total_steps
        task.eta_seconds = snap.eta_seconds

    def _save_output(self, task: Task, video_array, audio_array=None) -> str:
        """保存输出视频文件。"""
        os.makedirs("outputs", exist_ok=True)
        output_path = f"outputs/{task.id}.mp4"

        if video_array is None:
            raise ValueError("video_array is None, cannot save video")

        # Convert to numpy (if not already)
        if hasattr(video_array, 'numpy'):
            video_array = video_array.numpy()

        # Ensure correct data type and range [0, 255] uint8
        if video_array.dtype == np.uint8:
            # Already converted by VAE decoder — skip range conversion
            pass
        elif video_array.dtype == np.float32 or video_array.dtype == np.float16:
            vmin, vmax = float(video_array.min()), float(video_array.max())
            if vmax <= 1.01 and vmin >= -0.01:
                # Range is approximately [0, 1]
                video_array = (video_array * 255).clip(0, 255).astype(np.uint8)
            elif vmax <= 1.01 and vmin >= -1.01:
                # Range is approximately [-1, 1]
                video_array = ((video_array + 1) / 2 * 255).clip(0, 255).astype(np.uint8)
            else:
                # Unknown range — clip and convert
                video_array = video_array.clip(0, 255).astype(np.uint8)
        else:
            # Integer type but not uint8 — clip and convert
            video_array = np.clip(video_array, 0, 255).astype(np.uint8)

        # Ensure correct dimension order: (T, H, W, C)
        if video_array.ndim == 4:
            if video_array.shape[-1] == 3:
                # Already (T, H, W, C) — keep as-is
                pass
            elif video_array.shape[1] == 3:
                # (B, C, T, H, W) — remove batch, transpose to (T, H, W, C)
                video_array = video_array.squeeze(0)
                if video_array.ndim == 4:
                    video_array = np.transpose(video_array, (1, 2, 3, 0))
            elif video_array.shape[0] <= 4 and video_array.shape[-1] > 4:
                # (C, T, H, W) — transpose to (T, H, W, C)
                video_array = np.transpose(video_array, (1, 2, 3, 0))

        # 使用 ffmpeg 保存视频
        import subprocess
        import tempfile

        # 创建临时目录保存帧
        with tempfile.TemporaryDirectory() as tmpdir:
            # 保存为 PNG 帧
            for i, frame in enumerate(video_array):
                frame_path = os.path.join(tmpdir, f"frame_{i:05d}.png")
                # 使用 PIL 或直接写入
                from PIL import Image
                img = Image.fromarray(frame)
                img.save(frame_path)

            # 使用 ffmpeg 合成视频
            cmd = [
                "ffmpeg", "-y",
                "-framerate", str(task.fps),
                "-i", os.path.join(tmpdir, "frame_%05d.png"),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-crf", "18",
                output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg failed: {result.stderr}")

        task.output_path = output_path
        task.metadata["video_shape"] = str(video_array.shape)
        task.metadata["output_format"] = "mp4"

        if audio_array is not None:
            task.metadata["audio_shape"] = str(audio_array.shape)

        return output_path


def _resolve_checkpoint_path() -> str:
    """从注册表中查找主模型的本地路径。"""
    import os
    base = os.path.expanduser("~/.jiandou/models/video/models--Lightricks--LTX-2/snapshots/main")
    if os.path.isdir(base):
        for f in os.listdir(base):
            if f.endswith(".safetensors") and "distilled" in f and "upscaler" not in f:
                return os.path.join(base, f)
    return ""


def _resolve_gemma_path() -> str:
    """查找 Gemma 3 文本编码器模型的本地路径。"""
    import os
    base = os.path.expanduser("~/.jiandou/models/video/models--google--gemma-3-12b-it/snapshots/main")
    if os.path.isdir(base):
        return base
    return ""
