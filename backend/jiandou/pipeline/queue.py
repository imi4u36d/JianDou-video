"""异步任务队列 — 优先级队列 + 多 Worker 并发调度。

架构：
    asyncio.PriorityQueue → N Workers → WeightManager → InferenceSession

支持：
- 任务优先级（priority 数值越大越优先，取负入队）
- 可配置并发 Worker 数
- 权重共享（通过 engine/batch.py 的 WeightManager）
- 任务暂停/取消
- SQLite 持久化回写
"""

import asyncio
import subprocess
import tempfile
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional

from jiandou.engine.batch import WeightManager
from jiandou.pipeline.task import Task, TaskStatus
from jiandou.pipeline.progress import ProgressTracker, ProgressPhase


@dataclass(order=True)
class _QueueItem:
    """asyncio.PriorityQueue 的内部条目。"""

    priority: int  # lower = higher priority (negated task.priority)
    enqueue_time: float = field(compare=False)
    task_id: str = field(compare=False)
    task: Task = field(compare=False)


class TaskQueue:
    """异步优先任务队列。

    Usage:
        queue = TaskQueue(max_workers=2)
        await queue.start()
        task_id = await queue.enqueue(task)
        # ... queue processes tasks automatically
        await queue.stop()
    """

    def __init__(
        self,
        max_workers: int = 1,
        weight_manager: Optional[WeightManager] = None,
        on_status_change: Optional[Callable[[Task, TaskStatus], None]] = None,
    ):
        self._max_workers = max_workers
        self._queue: asyncio.PriorityQueue[_QueueItem] = asyncio.PriorityQueue()
        self._wm = weight_manager or WeightManager()
        self._on_status_change = on_status_change

        self._workers: list[asyncio.Task] = []
        self._running = False
        self._paused = False
        self._active_tasks: dict[str, asyncio.Task] = {}
        self._cancel_requested: set[str] = set()

        # Statistics
        self._completed_count = 0
        self._failed_count = 0

    # ── public API ────────────────────────────────────────────────────

    async def start(self):
        """启动 Worker 协程。"""
        if self._running:
            return
        self._running = True
        self._workers = [
            asyncio.create_task(self._worker_loop(i))
            for i in range(self._max_workers)
        ]

    async def stop(self, graceful: bool = True):
        """停止所有 Worker。"""
        self._running = False

        if graceful:
            # Wait for active tasks to finish
            if self._active_tasks:
                await asyncio.gather(*self._active_tasks.values(), return_exceptions=True)

        for w in self._workers:
            w.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def enqueue(self, task: Task) -> str:
        """将任务加入队列。

        Args:
            task: Task 实例

        Returns:
            task.id
        """
        item = _QueueItem(
            priority=-task.priority,  # negate: higher priority → smaller number
            enqueue_time=time.time(),
            task_id=task.id,
            task=task,
        )
        await self._queue.put(item)
        return task.id

    async def enqueue_batch(self, tasks: list[Task]) -> list[str]:
        """批量入队。"""
        ids = []
        for task in tasks:
            ids.append(await self.enqueue(task))
        return ids

    def cancel(self, task_id: str) -> bool:
        """请求取消任务。"""
        self._cancel_requested.add(task_id)
        if task_id in self._active_tasks:
            self._active_tasks[task_id].cancel()
            return True
        return False

    def pause(self):
        """暂停调度（不影响已在运行的任务）。"""
        self._paused = True

    def resume(self):
        """恢复调度。"""
        self._paused = False

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    @property
    def active_count(self) -> int:
        return len(self._active_tasks)

    @property
    def stats(self) -> dict:
        return {
            "queue_size": self._queue.qsize(),
            "active_count": len(self._active_tasks),
            "completed": self._completed_count,
            "failed": self._failed_count,
            "workers": self._max_workers,
            "paused": self._paused,
        }

    # ── internal worker ───────────────────────────────────────────────

    async def _worker_loop(self, worker_id: int):
        """Worker 主循环：从队列取任务 → 在线程中执行（避免阻塞 event loop）。"""
        while self._running:
            if self._paused:
                await asyncio.sleep(0.5)
                continue

            try:
                # Wait for a task with timeout (allows checking _running)
                item = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            task = item.task
            task_id = task.id

            # Check if already cancelled
            if task_id in self._cancel_requested:
                task.status = TaskStatus.CANCELLED
                self._notify_status(task, TaskStatus.CANCELLED)
                self._cancel_requested.discard(task_id)
                continue

            # Execute
            task.status = TaskStatus.RUNNING
            task.started_at = __import__("datetime").datetime.now()
            self._notify_status(task, TaskStatus.RUNNING)

            try:
                # Offload sync work (download + MLX inference) to a thread
                # so the event loop stays responsive for API requests
                await asyncio.to_thread(self._execute_task_sync, task)
                task.status = TaskStatus.DONE
                self._completed_count += 1
            except asyncio.CancelledError:
                task.status = TaskStatus.CANCELLED
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error_message = str(e)
                self._failed_count += 1

            task.completed_at = __import__("datetime").datetime.now()
            self._notify_status(task, task.status)

    def _execute_task_sync(self, task: Task):
        """执行单个任务的完整流程（同步方法，在线程中调用）。

        这是从队列到推理的桥接层。实际的 MLX 推理在 engine/session.py 中。
        """
        from jiandou.engine.session import InferenceSession, SessionConfig
        from jiandou.manager.registry import ModelRegistry
        from jiandou.storage.config import load_config
        import os as _os

        # Resolve model paths
        registry = ModelRegistry(db_path=_os.path.expanduser("~/.jiandou/models/video/registry.db"))
        checkpoint_path = _resolve_checkpoint_path(registry)
        gemma_path = _os.path.expanduser("~/.jiandou/models/video/models--google--gemma-3-12b-it/snapshots/main")
        spatial_up_path = _resolve_upscaler_path(registry, "spatial")

        # Open job store for progress writes
        config = load_config()
        from jiandou.storage.job_store import JobStore
        job_store = JobStore(_os.path.expanduser(config.paths.logs + "/jobs.db"))

        tracker = ProgressTracker(total_steps=task.steps)

        # Phase: Loading
        tracker.set_phase(ProgressPhase.LOADING)
        session_config = SessionConfig(
            checkpoint_path=checkpoint_path,
            gemma_path=gemma_path if _os.path.isdir(gemma_path) else "",
            spatial_upscaler_path=spatial_up_path,
            checkpoint_filename="ltx-2.3-22b-distilled-1.1.safetensors",
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
            audio_prompt=task.audio_prompt,
            fp16=task.fp16,
            low_memory=task.low_memory,
            pipeline=task.pipeline,
            model_version=task.model_version,
            on_step=lambda step, total: (
                setattr(task, "current_step", step),
                setattr(task, "total_steps", total),
                setattr(task, "progress", step / max(total, 1)),
                tracker.step(step),
                job_store.update_progress(task.id, task.progress, step, total),
            ),
        )

        session = InferenceSession(session_config)

        if task.id in self._cancel_requested:
            return

        with session:
            tracker.set_phase(ProgressPhase.DENOISING, total_steps=task.steps)
            result = session.run()

            if isinstance(result, tuple):
                video, audio = result
            else:
                video, audio = result, None

            # Save output as mp4 video
            _os.makedirs("outputs", exist_ok=True)
            output_path = f"outputs/{task.id}.mp4"

            if video is not None:
                import numpy as np
                from PIL import Image

                # 转换为 numpy 数组
                video_array = np.array(video)

                print(f"[DEBUG] Original video shape: {video_array.shape}, dtype: {video_array.dtype}")
                print(f"[DEBUG] Value range: min={video_array.min()}, max={video_array.max()}")

                # decode_latent 返回 (T, H, W, 3) uint8 [0, 255]
                # 但是 MLX 数组可能还没有完成转换，需要检查
                if video_array.ndim == 4 and video_array.shape[-1] == 3:
                    if video_array.dtype == np.uint8:
                        # 已经是正确的格式
                        print("[DEBUG] Video is already uint8 (T, H, W, 3)")
                    elif video_array.dtype in (np.float32, np.float16):
                        # 可能是 [-1, 1] 或 [0, 1] 范围的浮点数
                        print(f"[DEBUG] Video is float, converting from [{video_array.min()}, {video_array.max()}]")
                        if video_array.min() >= -1.0 and video_array.max() <= 1.0:
                            # [-1, 1] -> [0, 255]
                            video_array = np.clip((video_array + 1) / 2, 0, 1) * 255
                        elif video_array.min() >= 0.0 and video_array.max() <= 1.0:
                            # [0, 1] -> [0, 255]
                            video_array = video_array * 255
                        video_array = video_array.astype(np.uint8)
                    else:
                        video_array = video_array.astype(np.uint8)
                else:
                    # 需要处理其他格式
                    print(f"[DEBUG] Unexpected format, trying to fix...")
                    if video_array.ndim == 5:
                        video_array = video_array[0]  # 移除 batch

                    if video_array.ndim == 4:
                        # 可能是 (C, T, H, W) 或 (T, C, H, W)
                        if video_array.shape[0] <= 4 and video_array.shape[-1] > 4:
                            video_array = np.transpose(video_array, (1, 2, 3, 0))
                        elif video_array.shape[1] <= 4 and video_array.shape[-1] > 4:
                            video_array = np.transpose(video_array, (0, 2, 3, 1))

                    # 转换数据类型
                    if video_array.dtype != np.uint8:
                        if video_array.min() >= -1.0 and video_array.max() <= 1.0:
                            video_array = np.clip((video_array + 1) / 2, 0, 1) * 255
                        elif video_array.min() >= 0.0 and video_array.max() <= 1.0:
                            video_array = video_array * 255
                        video_array = video_array.astype(np.uint8)

                    # 如果是灰度图，转换为 RGB
                    if video_array.ndim == 4 and video_array.shape[-1] == 1:
                        video_array = np.concatenate([video_array] * 3, axis=-1)

                print(f"[DEBUG] Final video shape: {video_array.shape}, dtype: {video_array.dtype}")
                print(f"[DEBUG] Final value range: min={video_array.min()}, max={video_array.max()}")

                # 确保最终格式是 (T, H, W, 3) uint8
                if video_array.ndim != 4 or video_array.shape[-1] != 3 or video_array.dtype != np.uint8:
                    raise ValueError(f"Unexpected video format: shape={video_array.shape}, dtype={video_array.dtype}")

                # 保存第一帧用于调试
                debug_frame_path = f"outputs/{task.id}_debug_frame0.png"
                Image.fromarray(video_array[0]).save(debug_frame_path)
                print(f"[DEBUG] Saved debug frame to {debug_frame_path}")

                # 使用 ffmpeg 保存视频
                with tempfile.TemporaryDirectory() as tmpdir:
                    for i, frame in enumerate(video_array):
                        frame_path = _os.path.join(tmpdir, f"frame_{i:05d}.png")
                        img = Image.fromarray(frame)
                        img.save(frame_path)

                    cmd = [
                        "ffmpeg", "-y",
                        "-framerate", str(task.fps),
                        "-i", _os.path.join(tmpdir, "frame_%05d.png"),
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
            else:
                task.output_path = None

            task.total_steps = task.steps
            task.current_step = task.steps
            task.progress = 1.0

        tracker.set_phase(ProgressPhase.DONE)

    def _notify_status(self, task: Task, status: TaskStatus):
        task.status = status
        if self._on_status_change:
            try:
                self._on_status_change(task, status)
            except Exception:
                pass


def _resolve_checkpoint_path(registry) -> str:
    """从注册表中查找主模型（transformer）的本地路径。"""
    import os
    entries = registry.list_by_type("transformer")
    if entries:
        path = os.path.expanduser(entries[0].local_path)
        if os.path.exists(path):
            return path
    base = os.path.expanduser("~/.jiandou/models/video/models--Lightricks--LTX-2/snapshots/main")
    for f in os.listdir(base) if os.path.isdir(base) else []:
        if f.endswith(".safetensors") and "distilled" in f and "upscaler" not in f:
            return os.path.join(base, f)
    return ""


def _resolve_upscaler_path(registry, kind: str = "spatial") -> str:
    """从注册表查找 upscaler 路径。"""
    import os
    base = os.path.expanduser("~/.jiandou/models/video/models--Lightricks--LTX-2/snapshots/main")
    if os.path.isdir(base):
        for f in os.listdir(base):
            if f.endswith(".safetensors") and kind in f:
                return os.path.join(base, f)
    return ""
