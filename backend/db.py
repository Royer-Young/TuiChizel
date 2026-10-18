"""SQLite 读写模块（人三 · 后端与数据）

负责把每次评价的过程数据落库，并给成长曲线提供查询。

表结构见《初步模型 Demo 实施指南》5.4：
    sessions(id, student_id, essay_text, score_json,
             think_seconds, revision_count, adopt_count, created_at)
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id     TEXT    NOT NULL,
    essay_text     TEXT    NOT NULL,
    score_json     TEXT    NOT NULL,   -- 三维分数、评语、引用等完整结果
    think_seconds  INTEGER NOT NULL DEFAULT 0,
    revision_count INTEGER NOT NULL DEFAULT 0,
    adopt_count    INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_student
    ON sessions(student_id, id);
"""


def get_db_path() -> Path:
    """数据库路径。测试时可用环境变量 APP_DB_PATH 指到临时文件。"""
    env_path = os.getenv("APP_DB_PATH")
    path = Path(env_path) if env_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    # 并发写入时更稳；WAL 模式对本地小应用足够
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """建表。服务启动时调用一次，可重复执行。"""
    with closing(get_conn()) as conn, conn:
        conn.executescript(SCHEMA)


def save_session(
    student_id: str,
    essay_text: str,
    result: dict[str, Any],
    think_seconds: int = 0,
    revision_count: int = 0,
    adopt_count: int = 0,
) -> int:
    """保存一次评价，返回新记录的 id。"""
    created_at = datetime.now().isoformat(timespec="seconds")
    score_json = json.dumps(result, ensure_ascii=False)

    with closing(get_conn()) as conn, conn:
        cur = conn.execute(
            """
            INSERT INTO sessions
                (student_id, essay_text, score_json,
                 think_seconds, revision_count, adopt_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                student_id,
                essay_text,
                score_json,
                max(0, int(think_seconds or 0)),
                max(0, int(revision_count or 0)),
                max(0, int(adopt_count or 0)),
                created_at,
            ),
        )
        return int(cur.lastrowid)


def get_history(student_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """按时间正序返回某学生的历史记录（最多最近 limit 条）。

    返回字段与前端约定一致，其中 score_json 是 JSON 字符串。
    """
    limit = max(1, min(int(limit or 100), 500))
    with closing(get_conn()) as conn, conn:
        rows = conn.execute(
            """
            SELECT * FROM (
                SELECT * FROM sessions
                WHERE student_id = ?
                ORDER BY id DESC
                LIMIT ?
            ) ORDER BY id ASC
            """,
            (student_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_session(session_id: int) -> dict[str, Any] | None:
    """按 id 查一条记录（调试 / 详情页备用）。"""
    with closing(get_conn()) as conn, conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
    return dict(row) if row else None


if __name__ == "__main__":
    init_db()
    print(f"数据库已就绪：{get_db_path()}")
