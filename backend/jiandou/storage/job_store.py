"""SQLite 任务持久化 — 保存/查询/更新任务记录。

支持：
- 完整 Task 字段的 SQLite 存储
- 分页查询（offset/limit）
- 按状态过滤
- 批量清理过期任务
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from jiandou.pipeline.task import Task, TaskStatus, TaskMode


CREATE_TASKS_TABLE = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    mode TEXT NOT NULL DEFAULT 't2v',
    status TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER DEFAULT 0,
    prompt TEXT DEFAULT '',
    negative_prompt TEXT DEFAULT '',
    image_path TEXT,
    audio_path TEXT,
    keyframes TEXT DEFAULT '[]',
    duration REAL DEFAULT 5.0,
    width INTEGER DEFAULT 768,
    height INTEGER DEFAULT 512,
    fps INTEGER DEFAULT 24,
    steps INTEGER DEFAULT 8,
    cfg REAL DEFAULT 2.0,
    seed INTEGER DEFAULT -1,
    preset TEXT DEFAULT 'balanced',
    model_version TEXT DEFAULT '2.3',
    pipeline TEXT DEFAULT 'auto',
    fp16 INTEGER DEFAULT 1,
    low_memory INTEGER DEFAULT 0,
    upscale TEXT DEFAULT 'none',
    upscale_factor REAL DEFAULT 2.0,
    generate_audio INTEGER DEFAULT 0,
    audio_prompt TEXT DEFAULT '',
    output_path TEXT,
    preview_path TEXT,
    metadata TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    progress REAL DEFAULT 0.0,
    current_step INTEGER DEFAULT 0,
    total_steps INTEGER DEFAULT 0,
    eta_seconds REAL,
    error_message TEXT
)
"""


class JobStore:
    """SQLite 任务持久化存储。"""

    def __init__(self, db_path: str = "~/.cache/jiandou/jobs.db"):
        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute(CREATE_TASKS_TABLE)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at)"
            )
            conn.commit()

    # ── CRUD ──────────────────────────────────────────────────────────

    def save(self, task: Task) -> str:
        """保存任务（INSERT OR REPLACE）。"""
        d = task.to_dict()
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO tasks
                   (id, mode, status, priority, prompt, negative_prompt,
                    image_path, audio_path, keyframes, duration, width, height,
                    fps, steps, cfg, seed, preset, model_version, pipeline,
                    fp16, low_memory, upscale, upscale_factor, generate_audio,
                    audio_prompt, output_path, preview_path, metadata,
                    created_at, started_at, completed_at,
                    progress, current_step, total_steps, eta_seconds, error_message)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    d["id"], d["mode"], d["status"], d["priority"],
                    d["prompt"], d["negative_prompt"],
                    d["image_path"], d["audio_path"],
                    json.dumps(d["keyframes"]) if d["keyframes"] else "[]",
                    d["duration"], d["width"], d["height"],
                    d["fps"], d["steps"], d["cfg"], d["seed"], d["preset"],
                    d["model_version"], d["pipeline"],
                    int(d["fp16"]), int(d["low_memory"]),
                    d["upscale"], d["upscale_factor"], int(d["generate_audio"]),
                    d["audio_prompt"], d["output_path"], d["preview_path"],
                    json.dumps(d["metadata"]) if d["metadata"] else "{}",
                    d["created_at"], d["started_at"], d["completed_at"],
                    d["progress"], d["current_step"], d["total_steps"],
                    d["eta_seconds"], d["error_message"],
                ),
            )
            conn.commit()
        return task.id

    def get(self, task_id: str) -> Optional[Task]:
        """获取单个任务。"""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return self._row_to_task(row) if row else None

    def list(
        self,
        status: Optional[str] = None,
        mode: Optional[str] = None,
        offset: int = 0,
        limit: int = 50,
        order_desc: bool = True,
    ) -> list[Task]:
        """分页查询任务列表。"""
        where = []
        params = []

        if status:
            where.append("status = ?")
            params.append(status)
        if mode:
            where.append("mode = ?")
            params.append(mode)

        query = "SELECT * FROM tasks"
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY created_at " + ("DESC" if order_desc else "ASC")
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_task(r) for r in rows]

    def update_progress(
        self,
        task_id: str,
        progress: float,
        current_step: int,
        total_steps: int,
        eta_seconds: Optional[float] = None,
    ):
        """快速更新进度字段（避免完整序列化）。"""
        with self._get_conn() as conn:
            conn.execute(
                """UPDATE tasks SET progress=?, current_step=?, total_steps=?,
                   eta_seconds=? WHERE id=?""",
                (progress, current_step, total_steps, eta_seconds, task_id),
            )
            conn.commit()

    def update_status(self, task_id: str, status: TaskStatus | str, error_message: Optional[str] = None):
        """更新任务状态。"""
        if isinstance(status, str):
            status = TaskStatus(status)
        with self._get_conn() as conn:
            now = datetime.now().isoformat()
            if status in (TaskStatus.RUNNING,):
                conn.execute(
                    "UPDATE tasks SET status=?, started_at=? WHERE id=?",
                    (status.value, now, task_id),
                )
            elif status in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED):
                conn.execute(
                    "UPDATE tasks SET status=?, completed_at=?, error_message=? WHERE id=?",
                    (status.value, now, error_message or "", task_id),
                )
            else:
                conn.execute(
                    "UPDATE tasks SET status=?, error_message=? WHERE id=?",
                    (status.value, error_message or "", task_id),
                )
            conn.commit()

    def delete(self, task_id: str) -> bool:
        """删除任务记录。"""
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
            return cursor.rowcount > 0

    def count(self, status: Optional[str] = None) -> int:
        """计数任务。"""
        with self._get_conn() as conn:
            if status:
                row = conn.execute("SELECT COUNT(*) FROM tasks WHERE status=?", (status,)).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()
            return row[0] if row else 0

    def cleanup_stale(self, max_age_hours: int = 168) -> int:
        """清理超过 max_age_hours 的已完成/失败任务。"""
        cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
        with self._get_conn() as conn:
            cursor = conn.execute(
                """DELETE FROM tasks
                   WHERE status IN ('done', 'failed', 'cancelled')
                   AND completed_at < ?""",
                (cutoff,),
            )
            conn.commit()
            return cursor.rowcount

    def get_next_pending(self) -> Optional[Task]:
        """获取优先级最高的 pending 任务。"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE status='pending' ORDER BY priority DESC, created_at ASC LIMIT 1"
            ).fetchone()
            return self._row_to_task(row) if row else None

    # ── helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> Task:
        """将 SQLite 行转换为 Task 对象。"""
        data = dict(row)
        task = Task(
            mode=data.get("mode", "t2v"),
            prompt=data.get("prompt", ""),
            negative_prompt=data.get("negative_prompt", ""),
            priority=data.get("priority", 0),
            task_id=data["id"],
            image_path=data.get("image_path"),
            audio_path=data.get("audio_path"),
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
            fp16=bool(data.get("fp16", 1)),
            low_memory=bool(data.get("low_memory", 0)),
            upscale=data.get("upscale", "none"),
            upscale_factor=data.get("upscale_factor", 2.0),
            generate_audio=bool(data.get("generate_audio", 0)),
            audio_prompt=data.get("audio_prompt", ""),
        )

        task.status = TaskStatus(data.get("status", "pending"))
        task.output_path = data.get("output_path")
        task.preview_path = data.get("preview_path")

        # Parse JSON fields
        try:
            task.keyframes = json.loads(data.get("keyframes", "[]"))
        except (json.JSONDecodeError, TypeError):
            task.keyframes = []
        try:
            task.metadata = json.loads(data.get("metadata", "{}"))
        except (json.JSONDecodeError, TypeError):
            task.metadata = {}

        # Timestamps
        created = data.get("created_at")
        if created:
            task.created_at = datetime.fromisoformat(created) if isinstance(created, str) else created
        started = data.get("started_at")
        if started:
            task.started_at = datetime.fromisoformat(started) if isinstance(started, str) else started
        completed = data.get("completed_at")
        if completed:
            task.completed_at = datetime.fromisoformat(completed) if isinstance(completed, str) else completed

        # Progress
        task.progress = data.get("progress", 0.0)
        task.current_step = data.get("current_step", 0)
        task.total_steps = data.get("total_steps", 0)
        task.eta_seconds = data.get("eta_seconds")
        task.error_message = data.get("error_message")

        return task
