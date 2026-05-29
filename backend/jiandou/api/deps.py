"""API 依赖注入 — 管理共享的 service 实例。

通过 FastAPI Depends() 提供：
- AppConfig（全局配置）
- JobStore（任务持久化）
- TaskQueue（异步队列）
- DownloadManager（模型下载）
- ModelRegistry（模型注册表）
"""

from functools import lru_cache
from typing import Optional

from jiandou.storage.config import AppConfig, load_config


# ── singletons (module-level, created once) ──────────────────────────

_config: Optional[AppConfig] = None
_job_store = None
_task_queue = None
_download_manager = None
_model_registry = None


def _get_config() -> AppConfig:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def get_config() -> AppConfig:
    """获取全局 AppConfig。"""
    return _get_config()


def get_job_store():
    """获取全局 JobStore 实例。"""
    global _job_store
    if _job_store is None:
        from jiandou.storage.job_store import JobStore

        config = _get_config()
        db_path = config.paths.logs + "/jobs.db"
        _job_store = JobStore(db_path)
    return _job_store


def get_task_queue():
    """获取全局 TaskQueue 实例。"""
    global _task_queue
    if _task_queue is None:
        from jiandou.pipeline.queue import TaskQueue
        from jiandou.hardware.detect import recommended_workers

        config = _get_config()
        max_workers = max(1, config.queue.max_workers)
        # Auto-detect if still default
        if max_workers == 1:
            max_workers = recommended_workers()
        _task_queue = TaskQueue(
            max_workers=max_workers,
            on_status_change=_on_task_status_change,
        )
    return _task_queue


def get_download_manager():
    """获取全局 DownloadManager 实例。"""
    global _download_manager
    if _download_manager is None:
        from jiandou.manager.download import DownloadManager

        config = _get_config()
        _download_manager = DownloadManager(
            cache_dir=config.models.cache_dir,
            hf_endpoint=config.models.hf_endpoint,
            max_concurrent=config.models.hf_max_concurrent,
        )
    return _download_manager


def get_model_registry():
    """获取全局 ModelRegistry 实例。"""
    global _model_registry
    if _model_registry is None:
        from jiandou.manager.registry import ModelRegistry

        config = _get_config()
        db_path = config.models.cache_dir + "/registry.db"
        _model_registry = ModelRegistry(db_path)
    return _model_registry


def _on_task_status_change(task, status):
    """队列状态变化回调 — 同步写入 JobStore。"""
    try:
        store = get_job_store()
        if status.value in ("done", "failed", "cancelled"):
            # Full save on terminal status
            store.save(task)
        else:
            store.update_status(task.id, status)
            store.update_progress(
                task.id, task.progress, task.current_step,
                task.total_steps, task.eta_seconds,
            )
    except Exception:
        pass
