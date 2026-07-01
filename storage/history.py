"""
============================================================
MathAnimAI — 本地持久化存储模块
功能：
  1. SQLite 数据库记录每条生成记录
  2. 支持查询全部历史
  3. 按ID读取旧视频和动画脚本
  4. 避免重复调用大模型和重新渲染
============================================================
"""

import os
import sqlite3
import json
import logging
from typing import Optional, Any
from contextlib import contextmanager

from config import DB_PATH, ensure_dirs

logger = logging.getLogger("MathAnimAI.Storage")


# ================================================================
# 数据库管理
# ================================================================
class HistoryDB:
    """历史记录数据库管理类"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        ensure_dirs()
        self._init_db()

    def _init_db(self):
        """初始化数据库表结构"""
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    problem_text TEXT NOT NULL,
                    problem_type TEXT NOT NULL DEFAULT '',
                    grade_level TEXT NOT NULL DEFAULT '初中',
                    script_json TEXT NOT NULL,
                    animation_path TEXT DEFAULT '',
                    audio_path TEXT DEFAULT '',
                    subtitle_path TEXT DEFAULT '',
                    final_video_path TEXT DEFAULT '',
                    status TEXT DEFAULT 'pending',
                    error_message TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        logger.info("数据库初始化完成")

    @contextmanager
    def _get_conn(self):
        """获取数据库连接（上下文管理器）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 支持按列名访问
        try:
            yield conn
        finally:
            conn.close()

    # ================================================================
    # CRUD 操作
    # ================================================================
    def insert_record(
        self,
        problem_text: str,
        script_json: str,
        problem_type: str = "",
        grade_level: str = "初中",
    ) -> int:
        """
        插入新记录

        Returns:
            新记录的ID
        """
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO history (problem_text, problem_type, grade_level, script_json, status)
                VALUES (?, ?, ?, ?, 'pending')
                """,
                (problem_text, problem_type, grade_level, script_json)
            )
            conn.commit()
            record_id = cursor.lastrowid
            logger.info(f"插入记录 ID={record_id}")
            return record_id

    def update_record(
        self,
        record_id: int,
        **kwargs: Any,
    ) -> bool:
        """
        更新记录字段

        支持的字段: animation_path, audio_path, subtitle_path,
                   final_video_path, status, error_message, script_json
        """
        allowed_fields = [
            "animation_path", "audio_path", "subtitle_path",
            "final_video_path", "status", "error_message", "script_json"
        ]

        updates = {}
        for key, value in kwargs.items():
            if key in allowed_fields:
                updates[key] = value

        if not updates:
            logger.warning("无有效更新字段")
            return False

        set_clause = ", ".join([f"{k} = ?" for k in updates])
        values = list(updates.values()) + [record_id]

        with self._get_conn() as conn:
            conn.execute(
                f"UPDATE history SET {set_clause} WHERE id = ?",
                values,
            )
            conn.commit()

        logger.info(f"更新记录 ID={record_id}: {list(updates.keys())}")
        return True

    def get_record(self, record_id: int) -> Optional[dict]:
        """根据ID获取单条记录"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM history WHERE id = ?",
                (record_id,),
            ).fetchone()

            if row:
                return dict(row)
            return None

    def get_all_records(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """获取全部历史记录（分页）"""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT id, problem_text, problem_type, grade_level,
                       status, final_video_path, created_at
                FROM history
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()

            return [dict(row) for row in rows]

    def get_script_by_id(self, record_id: int) -> Optional[str]:
        """获取指定记录的动画脚本JSON"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT script_json FROM history WHERE id = ?",
                (record_id,),
            ).fetchone()

            if row:
                return row["script_json"]
            return None

    def get_video_path(self, record_id: int) -> Optional[str]:
        """获取指定记录的视频路径"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT final_video_path FROM history WHERE id = ?",
                (record_id,),
            ).fetchone()

            if row:
                return row["final_video_path"]
            return None

    def search_by_problem(self, keyword: str, limit: int = 20) -> list[dict]:
        """按题目关键字搜索历史记录"""
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT id, problem_text, problem_type, status,
                       final_video_path, created_at
                FROM history
                WHERE problem_text LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (f"%{keyword}%", limit),
            ).fetchall()

            return [dict(row) for row in rows]

    def delete_record(self, record_id: int) -> bool:
        """删除记录（软删除：仅标记状态）"""
        return self.update_record(record_id, status="deleted")

    def get_record_count(self) -> int:
        """获取总记录数"""
        with self._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) as count FROM history").fetchone()
            return row["count"]


# ================================================================
# 全局单例
# ================================================================
_history_db: Optional[HistoryDB] = None


def get_history() -> HistoryDB:
    """获取全局历史记录数据库实例"""
    global _history_db
    if _history_db is None:
        _history_db = HistoryDB()
    return _history_db
