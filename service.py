"""Self Manager service layer backed by SQLite.

This module provides:
- User registration/login/token authentication
- Task CRUD with per-user isolation
- Filtering, searching, sorting and statistics
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


class TaskService:
    """Service class for persistence and business rules."""

    DEFAULT_CATEGORIES = ["工作", "学习", "生活", "健康"]
    PASSWORD_ITERATIONS = 100_000
    TOKEN_TTL_HOURS = 24
    TOKEN_TTL_REMEMBER_HOURS = 24 * 7

    def __init__(self, db_path: str = "productivity_manager.db"):
        self.db_path = str(Path(db_path))
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    def _now_str() -> str:
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    def _init_db(self) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS auth_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT,
                token_hash TEXT,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT NOT NULL,
                quadrant INTEGER NOT NULL CHECK(quadrant BETWEEN 1 AND 4),
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )

        # Backward-compatible migration for older databases.
        columns = [row["name"] for row in cursor.execute("PRAGMA table_info(tasks)").fetchall()]
        if "user_id" not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN user_id INTEGER")

        token_columns = [row["name"] for row in cursor.execute("PRAGMA table_info(auth_tokens)").fetchall()]
        if "token_hash" not in token_columns:
            cursor.execute("ALTER TABLE auth_tokens ADD COLUMN token_hash TEXT")
            # One-time migration for historical plaintext token rows.
            legacy_rows = cursor.execute(
                "SELECT id, token FROM auth_tokens WHERE token IS NOT NULL AND token_hash IS NULL"
            ).fetchall()
            for row in legacy_rows:
                cursor.execute(
                    "UPDATE auth_tokens SET token_hash = ? WHERE id = ?",
                    (self._hash_token(row["token"]), row["id"]),
                )

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_category ON tasks(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_quadrant ON tasks(quadrant)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_created ON tasks(user_id, created_at DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_tokens_token ON auth_tokens(token)")
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_tokens_token_hash ON auth_tokens(token_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_tokens_user ON auth_tokens(user_id)")

        conn.commit()
        conn.close()

    # ------------------------
    # Authentication
    # ------------------------
    def register_user(self, username: str, password: str) -> Dict:
        username_norm = self._validate_username(username)
        self._validate_password(password)

        salt = os.urandom(16).hex()
        password_hash = self._hash_password(password, salt)

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO users (username, password_hash, password_salt)
                VALUES (?, ?, ?)
                """,
                (username_norm, password_hash, salt),
            )
            conn.commit()
            user_id = cursor.lastrowid
        except sqlite3.IntegrityError as exc:
            conn.close()
            raise ValueError("用户名已存在") from exc

        cursor.execute("SELECT id, username, created_at FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return {"id": row["id"], "username": row["username"], "created_at": row["created_at"]}

    def login_user(self, username: str, password: str, remember_me: bool = False) -> Optional[Dict]:
        username_norm = username.strip()
        if not username_norm or not password:
            return None

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, username, password_hash, password_salt, created_at
            FROM users
            WHERE username = ?
            """,
            (username_norm,),
        )
        user = cursor.fetchone()
        if not user:
            conn.close()
            return None

        expected_hash = self._hash_password(password, user["password_salt"])
        if not hmac.compare_digest(expected_hash, user["password_hash"]):
            conn.close()
            return None

        token = secrets.token_urlsafe(32)
        token_hash = self._hash_token(token)
        # Keep legacy token column non-sensitive and unusable for authentication.
        token_placeholder = secrets.token_urlsafe(16)
        ttl_hours = self.TOKEN_TTL_REMEMBER_HOURS if remember_me else self.TOKEN_TTL_HOURS
        expires_at = (datetime.utcnow() + timedelta(hours=ttl_hours)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        cursor.execute(
            """
            INSERT INTO auth_tokens (user_id, token, token_hash, expires_at)
            VALUES (?, ?, ?, ?)
            """,
            (user["id"], token_placeholder, token_hash, expires_at),
        )

        # Cleanup expired tokens opportunistically.
        cursor.execute("DELETE FROM auth_tokens WHERE expires_at <= ?", (self._now_str(),))
        conn.commit()
        conn.close()

        return {
            "token": token,
            "expires_at": expires_at,
            "user": {"id": user["id"], "username": user["username"], "created_at": user["created_at"]},
        }

    def verify_token(self, token: str) -> Optional[Dict]:
        if not token:
            return None

        conn = self._get_connection()
        cursor = conn.cursor()
        token_hash = self._hash_token(token)
        cursor.execute(
            """
            SELECT u.id, u.username, u.created_at, t.expires_at
            FROM auth_tokens t
            JOIN users u ON u.id = t.user_id
            WHERE t.token_hash = ? AND t.expires_at > ?
            """,
            (token_hash, self._now_str()),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None

        return {
            "id": row["id"],
            "username": row["username"],
            "created_at": row["created_at"],
            "token_expires_at": row["expires_at"],
        }

    def logout(self, token: str) -> bool:
        if not token:
            return False

        conn = self._get_connection()
        cursor = conn.cursor()
        token_hash = self._hash_token(token)
        cursor.execute("DELETE FROM auth_tokens WHERE token_hash = ?", (token_hash,))
        conn.commit()
        removed = cursor.rowcount > 0
        conn.close()
        return removed

    # ------------------------
    # Task operations
    # ------------------------
    def add_task(
        self,
        user_id: int,
        title: str,
        description: Optional[str] = "",
        category: str = "工作",
        quadrant: int = 1,
    ) -> Dict:
        uid = self._validate_user_id(user_id)
        title_trimmed = self._validate_title(title)
        category_checked = self._validate_category(category)
        quadrant_checked = self._validate_quadrant(quadrant)

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tasks (user_id, title, description, category, quadrant)
            VALUES (?, ?, ?, ?, ?)
            """,
            (uid, title_trimmed, (description or "").strip(), category_checked, quadrant_checked),
        )
        conn.commit()
        task_id = cursor.lastrowid
        conn.close()

        task = self.get_task_by_id(task_id, uid)
        if task is None:
            raise RuntimeError("任务写入后读取失败")
        return task

    def update_task(
        self,
        task_id: int,
        user_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        quadrant: Optional[int] = None,
    ) -> bool:
        uid = self._validate_user_id(user_id)

        updates: List[str] = []
        params: List = []

        if title is not None:
            updates.append("title = ?")
            params.append(self._validate_title(title))
        if description is not None:
            updates.append("description = ?")
            params.append(description.strip())
        if category is not None:
            updates.append("category = ?")
            params.append(self._validate_category(category))
        if quadrant is not None:
            updates.append("quadrant = ?")
            params.append(self._validate_quadrant(quadrant))

        updates.append("updated_at = datetime('now')")

        conn = self._get_connection()
        cursor = conn.cursor()
        sql = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND user_id = ?"
        params.extend([task_id, uid])
        cursor.execute(sql, params)
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()
        return updated

    def delete_task(self, task_id: int, user_id: int) -> bool:
        uid = self._validate_user_id(user_id)

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id, uid))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted

    def get_task_by_id(self, task_id: int, user_id: int) -> Optional[Dict]:
        uid = self._validate_user_id(user_id)

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, title, description, category, quadrant, created_at, updated_at
            FROM tasks
            WHERE id = ? AND user_id = ?
            """,
            (task_id, uid),
        )
        row = cursor.fetchone()
        conn.close()
        return self._row_to_task(row) if row else None

    def get_all_tasks(self, user_id: int) -> List[Dict]:
        uid = self._validate_user_id(user_id)

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, title, description, category, quadrant, created_at, updated_at
            FROM tasks
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (uid,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_task(row) for row in rows]

    def filter_tasks(
        self,
        user_id: int,
        category: Optional[str] = None,
        quadrant: Optional[int] = None,
    ) -> List[Dict]:
        uid = self._validate_user_id(user_id)

        conditions: List[str] = ["user_id = ?"]
        params: List = [uid]

        if category and category != "全部":
            conditions.append("category = ?")
            params.append(self._validate_category(category))

        if quadrant and str(quadrant) != "全部":
            conditions.append("quadrant = ?")
            params.append(self._validate_quadrant(int(quadrant)))

        where_sql = "WHERE " + " AND ".join(conditions)

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT id, user_id, title, description, category, quadrant, created_at, updated_at
            FROM tasks
            {where_sql}
            ORDER BY created_at DESC, id DESC
            """,
            params,
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_task(row) for row in rows]

    def search_tasks(self, user_id: int, keyword: str) -> List[Dict]:
        uid = self._validate_user_id(user_id)

        if not keyword or not keyword.strip():
            return self.get_all_tasks(uid)

        search_term = f"%{keyword.strip()}%"
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_id, title, description, category, quadrant, created_at, updated_at
            FROM tasks
            WHERE user_id = ? AND (title LIKE ? OR description LIKE ?)
            ORDER BY created_at DESC, id DESC
            """,
            (uid, search_term, search_term),
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_task(row) for row in rows]

    def get_sorted_tasks(self, user_id: int, sort_by: str = "created_desc") -> List[Dict]:
        uid = self._validate_user_id(user_id)

        sort_mapping = {
            "created_desc": "created_at DESC, id DESC",
            "created_asc": "created_at ASC, id ASC",
            "updated_desc": "updated_at DESC, id DESC",
            "updated_asc": "updated_at ASC, id ASC",
        }
        order_clause = sort_mapping.get(sort_by, sort_mapping["created_desc"])

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT id, user_id, title, description, category, quadrant, created_at, updated_at
            FROM tasks
            WHERE user_id = ?
            ORDER BY {order_clause}
            """,
            (uid,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_task(row) for row in rows]

    def get_statistics(self, user_id: int) -> Dict:
        all_tasks = self.get_all_tasks(user_id)

        category_stats = {category: 0 for category in self.DEFAULT_CATEGORIES}
        quadrant_stats = {1: 0, 2: 0, 3: 0, 4: 0}

        for task in all_tasks:
            category_stats[task["category"]] += 1
            quadrant_stats[task["quadrant"]] += 1

        return {
            "total": len(all_tasks),
            "by_category": category_stats,
            "by_quadrant": quadrant_stats,
        }

    def get_categories(self) -> List[str]:
        return self.DEFAULT_CATEGORIES.copy()

    def get_tasks_grouped_by_quadrant(self, user_id: int) -> Dict[int, List[Dict]]:
        grouped = {1: [], 2: [], 3: [], 4: []}
        for task in self.get_all_tasks(user_id):
            grouped[task["quadrant"]].append(task)
        return grouped

    def get_tasks_grouped_by_category(self, user_id: int) -> Dict[str, List[Dict]]:
        grouped = {category: [] for category in self.DEFAULT_CATEGORIES}
        for task in self.get_all_tasks(user_id):
            grouped[task["category"]].append(task)
        return grouped

    def clear_all_tasks(self, user_id: int) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        uid = self._validate_user_id(user_id)
        cursor.execute("DELETE FROM tasks WHERE user_id = ?", (uid,))
        conn.commit()
        conn.close()

    # ------------------------
    # Validation and helpers
    # ------------------------
    def _validate_user_id(self, user_id: int) -> int:
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("用户未登录或用户ID无效")
        return user_id

    def _validate_title(self, title: str) -> str:
        title_trimmed = (title or "").strip()
        if not title_trimmed:
            raise ValueError("任务标题不能为空")
        if len(title_trimmed) < 2:
            raise ValueError("任务标题太短（至少2个字符）")
        return title_trimmed

    def _validate_category(self, category: str) -> str:
        if category not in self.DEFAULT_CATEGORIES:
            raise ValueError("分类必须是 工作/学习/生活/健康 之一")
        return category

    def _validate_quadrant(self, quadrant: int) -> int:
        if quadrant not in (1, 2, 3, 4):
            raise ValueError("象限必须是 1-4 的整数")
        return quadrant

    def _validate_username(self, username: str) -> str:
        username_norm = (username or "").strip()
        if len(username_norm) < 3:
            raise ValueError("用户名至少3个字符")
        if len(username_norm) > 32:
            raise ValueError("用户名不能超过32个字符")
        return username_norm

    def _validate_password(self, password: str) -> None:
        if password is None or len(password) < 6:
            raise ValueError("密码至少6个字符")
        if len(password) > 128:
            raise ValueError("密码长度不能超过128个字符")

    def _hash_password(self, password: str, salt_hex: str) -> str:
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            self.PASSWORD_ITERATIONS,
        )
        return digest.hex()

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> Dict:
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "title": row["title"],
            "description": row["description"] or "",
            "category": row["category"],
            "quadrant": row["quadrant"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
