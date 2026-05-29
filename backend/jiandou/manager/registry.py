"""本地模型注册表 — SQLite 持久化的已下载模型信息。

记录模型名称、路径、大小、版本、下载时间等元数据。
"""

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class ModelEntry:
    """模型注册表条目。"""

    name: str
    repo: str
    filename: str
    local_path: str
    size_bytes: int = 0
    version: str = "2.3"
    model_type: str = "transformer"  # transformer | text_encoder | upscaler | vae
    downloaded: bool = False
    downloaded_at: Optional[datetime] = None
    sha256: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "repo": self.repo,
            "filename": self.filename,
            "local_path": self.local_path,
            "size_bytes": self.size_bytes,
            "version": self.version,
            "model_type": self.model_type,
            "downloaded": self.downloaded,
            "downloaded_at": self.downloaded_at.isoformat() if self.downloaded_at else None,
            "sha256": self.sha256,
        }

    @classmethod
    def from_row(cls, row: tuple) -> "ModelEntry":
        """从 DB 行创建 ModelEntry。"""
        return cls(
            name=row[0],
            repo=row[1],
            filename=row[2],
            local_path=row[3],
            size_bytes=row[4],
            version=row[5],
            model_type=row[6],
            downloaded=bool(row[7]),
            downloaded_at=datetime.fromisoformat(row[8]) if row[8] else None,
            sha256=row[9],
        )


class ModelRegistry:
    """本地模型注册表。

    基于 SQLite 持久化，记录所有已下载模型的状态。
    """

    def __init__(self, db_path: str = "~/.cache/jiandou/registry.db"):
        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS models (
                    name TEXT PRIMARY KEY,
                    repo TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    local_path TEXT NOT NULL,
                    size_bytes INTEGER DEFAULT 0,
                    version TEXT DEFAULT '2.3',
                    model_type TEXT DEFAULT 'transformer',
                    downloaded INTEGER DEFAULT 0,
                    downloaded_at TEXT,
                    sha256 TEXT
                )
            """)
            conn.commit()

    # ── CRUD ──────────────────────────────────────────────────────────

    def register(
        self,
        name: str,
        repo: str,
        filename: str,
        local_path: str,
        size_bytes: int = 0,
        version: str = "2.3",
        model_type: str = "transformer",
        sha256: Optional[str] = None,
    ) -> ModelEntry:
        """注册一个模型条目。"""
        entry = ModelEntry(
            name=name,
            repo=repo,
            filename=filename,
            local_path=local_path,
            size_bytes=size_bytes,
            version=version,
            model_type=model_type,
            downloaded=True,
            downloaded_at=datetime.now(),
            sha256=sha256,
        )
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO models
                   (name, repo, filename, local_path, size_bytes, version,
                    model_type, downloaded, downloaded_at, sha256)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.name, entry.repo, entry.filename, entry.local_path,
                    entry.size_bytes, entry.version, entry.model_type,
                    int(entry.downloaded),
                    entry.downloaded_at.isoformat() if entry.downloaded_at else None,
                    entry.sha256,
                ),
            )
            conn.commit()
        return entry

    def get(self, name: str) -> Optional[ModelEntry]:
        """获取一个模型条目。"""
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM models WHERE name = ?", (name,)).fetchone()
            return ModelEntry.from_row(row) if row else None

    def list_all(self) -> list[ModelEntry]:
        """列出所有已注册的模型。"""
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM models ORDER BY name").fetchall()
            return [ModelEntry.from_row(r) for r in rows]

    def list_by_type(self, model_type: str) -> list[ModelEntry]:
        """按类型过滤模型。"""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM models WHERE model_type = ? ORDER BY name",
                (model_type,),
            ).fetchall()
            return [ModelEntry.from_row(r) for r in rows]

    def remove(self, name: str) -> bool:
        """移除一个模型条目。"""
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM models WHERE name = ?", (name,))
            conn.commit()
            return cursor.rowcount > 0

    def exists(self, name: str) -> bool:
        """检查模型是否已注册。"""
        with self._get_conn() as conn:
            row = conn.execute("SELECT 1 FROM models WHERE name = ?", (name,)).fetchone()
            return row is not None

    def total_size_bytes(self) -> int:
        """所有已下载模型的总大小。"""
        with self._get_conn() as conn:
            row = conn.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM models WHERE downloaded = 1").fetchone()
            return row[0]

    def find_by_repo_file(self, repo: str, filename: str) -> Optional[ModelEntry]:
        """通过仓库和文件名查找模型。"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM models WHERE repo = ? AND filename = ?",
                (repo, filename),
            ).fetchone()
            return ModelEntry.from_row(row) if row else None

    # ── file utilities ────────────────────────────────────────────────

    @staticmethod
    def compute_sha256(file_path: str) -> str:
        """计算文件的 SHA256 哈希。"""
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)
        return sha.hexdigest()

    @staticmethod
    def get_file_size(file_path: str) -> int:
        """获取文件大小（bytes）。"""
        return Path(file_path).stat().st_size
