"""批量推理 — 相同模型的 job 共享权重，减少重复加载/卸载开销。"""

import asyncio
import time
from dataclasses import dataclass
from typing import Optional

from jiandou.engine.session import InferenceSession, SessionConfig, SessionError


@dataclass
class BatchJob:
    """批量推理中的单个任务。"""

    id: str
    config: SessionConfig
    created_at: float = 0.0
    result: Optional[tuple] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()


class WeightManager:
    """权重引用计数管理器。

    多个相同模型的 job 共享一份权重，refcount 降到 0 时才卸载。
    """

    def __init__(self):
        self._sessions: dict[str, dict] = {}  # key -> {session, refcount, last_used}

    def acquire(self, checkpoint_path: str, gemma_path: str = "") -> InferenceSession:
        """获取或创建共享 session。"""
        key = f"{checkpoint_path}::{gemma_path}"
        if key in self._sessions:
            entry = self._sessions[key]
            entry["refcount"] += 1
            entry["last_used"] = time.time()
            return entry["session"]

        session = InferenceSession(SessionConfig(
            checkpoint_path=checkpoint_path,
            gemma_path=gemma_path,
        ))
        session.load()
        self._sessions[key] = {"session": session, "refcount": 1, "last_used": time.time()}
        return session

    def release(self, session: InferenceSession) -> None:
        """释放 session 引用，refcount 归零时卸载。"""
        for key, entry in list(self._sessions.items()):
            if entry["session"] is session:
                entry["refcount"] -= 1
                if entry["refcount"] <= 0:
                    session.unload()
                    del self._sessions[key]
                return

    def cleanup_expired(self, ttl: float = 600) -> int:
        """清理超过 TTL 未使用的 session。"""
        now = time.time()
        removed = 0
        for key, entry in list(self._sessions.items()):
            if now - entry["last_used"] > ttl:
                entry["session"].unload()
                del self._sessions[key]
                removed += 1
        return removed


class BatchRunner:
    """批量推理执行器。

    按 checkpoint_path 分组，同组 job 共享权重依次执行。
    """

    def __init__(self, weight_manager: Optional[WeightManager] = None):
        self._wm = weight_manager or WeightManager()

    async def run_batch(self, jobs: list[BatchJob]) -> list[BatchJob]:
        """执行一组 job，共享权重优化。"""
        # Group by checkpoint path
        groups: dict[str, list[BatchJob]] = {}
        for job in jobs:
            key = f"{job.config.checkpoint_path}::{job.config.gemma_path}"
            groups.setdefault(key, []).append(job)

        all_jobs = []
        for key, group in groups.items():
            session = None
            try:
                checkpoint_path, gemma_path = key.split("::", 1)
                session = self._wm.acquire(checkpoint_path, gemma_path)
                for job in group:
                    try:
                        job.config.checkpoint_path = checkpoint_path
                        job.config.gemma_path = gemma_path
                        # Reuse session weights, but apply job-specific config
                        session.config = job.config
                        job.result = session.run()
                    except SessionError as e:
                        job.error = str(e)
                    all_jobs.append(job)
            finally:
                if session:
                    self._wm.release(session)

        return all_jobs

    async def run_single(self, config: SessionConfig) -> tuple:
        """执行单个推理任务。"""
        session = InferenceSession(config)
        with session:
            return session.run()
