"""Self Manager service layer backed by SQLite."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import csv
import io
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger


class TaskService:
    """Service class for persistence and business rules."""

    DEFAULT_CATEGORIES = [
        {"name": "工作", "color": "#006D77"},
        {"name": "学习", "color": "#0F766E"},
        {"name": "生活", "color": "#C2410C"},
        {"name": "健康", "color": "#2563EB"},
    ]
    PASSWORD_ITERATIONS = 100_000
    TOKEN_TTL_HOURS = 24
    TOKEN_TTL_REMEMBER_HOURS = 24 * 7
    STATUS_ALL = "all"
    STATUS_PENDING = "pending"
    STATUS_COMPLETED = "completed"
    CHECKIN_PERIODS = ("morning", "noon", "evening")
    POMODORO_TYPES = ("work", "short_break", "long_break")

    def __init__(self, db_path: str = "productivity_manager.db"):
        raw_db_path = str(db_path)
        self._use_uri = raw_db_path.startswith("file:")
        if raw_db_path == ":memory:":
            raw_db_path = "file:self_manager_memdb?mode=memory&cache=shared"
            self._use_uri = True
        self.db_path = raw_db_path if self._use_uri else str(Path(raw_db_path))
        self._keepalive_connection: Optional[sqlite3.Connection] = None
        if self._use_uri and "mode=memory" in self.db_path:
            self._keepalive_connection = sqlite3.connect(
                self.db_path,
                uri=True,
                check_same_thread=False,
            )
            self._keepalive_connection.row_factory = sqlite3.Row
            self._keepalive_connection.execute("PRAGMA foreign_keys = ON")
        logger.info("初始化 TaskService，数据库文件: {}", self.db_path)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        try:
            conn = sqlite3.connect(
                self.db_path,
                uri=self._use_uri,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            logger.info("已建立数据库连接: {}", self.db_path)
            return conn
        except sqlite3.Error:
            logger.exception("建立数据库连接失败: {}", self.db_path)
            raise

    def close(self) -> None:
        if self._keepalive_connection is not None:
            self._keepalive_connection.close()
            self._keepalive_connection = None

    @staticmethod
    def _now_str() -> str:
        return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _mask_token(token: str) -> str:
        if not token:
            return "<empty>"
        if len(token) <= 8:
            return "***"
        return f"{token[:4]}***{token[-4:]}"

    def _init_db(self) -> None:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            logger.info("开始初始化数据库结构")

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
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    color TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(user_id, name),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    category_id INTEGER,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT NOT NULL,
                    quadrant INTEGER NOT NULL CHECK(quadrant BETWEEN 1 AND 4),
                    completed INTEGER NOT NULL DEFAULT 0,
                    due_at TEXT,
                    recurrence_rule TEXT NOT NULL DEFAULT 'none',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (category_id) REFERENCES categories(id)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS workstation_checkins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    checkin_date TEXT NOT NULL,
                    period TEXT NOT NULL CHECK(period IN ('morning', 'noon', 'evening')),
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(user_id, checkin_date, period),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS phone_focus_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    duration_minutes INTEGER NOT NULL CHECK(duration_minutes > 0),
                    note TEXT NOT NULL DEFAULT '',
                    resisted_at TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS pomodoro_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    session_date TEXT NOT NULL,
                    session_type TEXT NOT NULL CHECK(session_type IN ('work', 'short_break', 'long_break')),
                    duration_minutes INTEGER NOT NULL CHECK(duration_minutes > 0),
                    completed INTEGER NOT NULL DEFAULT 0,
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )

            task_columns = [row["name"] for row in cursor.execute("PRAGMA table_info(tasks)").fetchall()]
            if "user_id" not in task_columns:
                logger.warning("检测到旧版 tasks 表结构，准备补充 user_id 字段")
                cursor.execute("ALTER TABLE tasks ADD COLUMN user_id INTEGER")
            if "category_id" not in task_columns:
                logger.warning("检测到旧版 tasks 表结构，准备补充 category_id 字段")
                cursor.execute("ALTER TABLE tasks ADD COLUMN category_id INTEGER")
            if "completed" not in task_columns:
                logger.warning("检测到旧版 tasks 表结构，准备补充 completed 字段")
                cursor.execute("ALTER TABLE tasks ADD COLUMN completed INTEGER NOT NULL DEFAULT 0")
            if "due_at" not in task_columns:
                logger.warning("检测到旧版 tasks 表结构，准备补充 due_at 字段")
                cursor.execute("ALTER TABLE tasks ADD COLUMN due_at TEXT")
            if "recurrence_rule" not in task_columns:
                logger.warning("检测到旧版 tasks 表结构，准备补充 recurrence_rule 字段")
                cursor.execute("ALTER TABLE tasks ADD COLUMN recurrence_rule TEXT NOT NULL DEFAULT 'none'")

            token_columns = [row["name"] for row in cursor.execute("PRAGMA table_info(auth_tokens)").fetchall()]
            if "token_hash" not in token_columns:
                logger.warning("检测到旧版 auth_tokens 表结构，准备补充 token_hash 字段")
                cursor.execute("ALTER TABLE auth_tokens ADD COLUMN token_hash TEXT")
                legacy_rows = cursor.execute(
                    "SELECT id, token FROM auth_tokens WHERE token IS NOT NULL AND token_hash IS NULL"
                ).fetchall()
                for row in legacy_rows:
                    cursor.execute(
                        "UPDATE auth_tokens SET token_hash = ? WHERE id = ?",
                        (self._hash_token(row["token"]), row["id"]),
                    )
                logger.info("历史 token_hash 数据迁移完成，共 {} 条", len(legacy_rows))

            self._seed_categories_for_existing_users(cursor)
            self._migrate_task_categories(cursor)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_category ON tasks(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_quadrant ON tasks(quadrant)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_created ON tasks(user_id, created_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_completed ON tasks(user_id, completed)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_category_id ON tasks(category_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_due_at ON tasks(due_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_categories_user_id ON categories(user_id)")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_user_name ON categories(user_id, name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_tokens_token ON auth_tokens(token)")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_tokens_token_hash ON auth_tokens(token_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_tokens_user ON auth_tokens(user_id)")
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_workstation_checkins_unique "
                "ON workstation_checkins(user_id, checkin_date, period)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_workstation_checkins_user_date "
                "ON workstation_checkins(user_id, checkin_date DESC)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_phone_focus_user_time "
                "ON phone_focus_records(user_id, resisted_at DESC)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_pomodoro_sessions_user_date "
                "ON pomodoro_sessions(user_id, session_date DESC, created_at DESC)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_pomodoro_sessions_user_type "
                "ON pomodoro_sessions(user_id, session_type)"
            )

            conn.commit()
            logger.info("数据库初始化完成")
        except sqlite3.Error:
            logger.exception("数据库初始化失败")
            raise
        finally:
            conn.close()

    def _seed_categories_for_existing_users(self, cursor: sqlite3.Cursor) -> None:
        user_rows = cursor.execute("SELECT id FROM users").fetchall()
        for row in user_rows:
            self._seed_default_categories(cursor, row["id"])

    def _seed_default_categories(self, cursor: sqlite3.Cursor, user_id: int) -> None:
        for category in self.DEFAULT_CATEGORIES:
            cursor.execute(
                """
                INSERT OR IGNORE INTO categories (user_id, name, color)
                VALUES (?, ?, ?)
                """,
                (user_id, category["name"], category["color"]),
            )

    def _migrate_task_categories(self, cursor: sqlite3.Cursor) -> None:
        rows = cursor.execute(
            """
            SELECT DISTINCT user_id, category
            FROM tasks
            WHERE user_id IS NOT NULL
              AND category IS NOT NULL
              AND TRIM(category) != ''
            """
        ).fetchall()
        for row in rows:
            category_name = row["category"].strip()
            category_id = self._ensure_category_exists(cursor, row["user_id"], category_name)
            cursor.execute(
                """
                UPDATE tasks
                SET category_id = ?, category = ?
                WHERE user_id = ? AND category = ? AND (category_id IS NULL OR category_id != ?)
                """,
                (category_id, category_name, row["user_id"], category_name, category_id),
            )

    def _ensure_category_exists(
        self,
        cursor: sqlite3.Cursor,
        user_id: int,
        name: str,
        color: Optional[str] = None,
    ) -> int:
        cursor.execute("SELECT id FROM categories WHERE user_id = ? AND name = ?", (user_id, name))
        row = cursor.fetchone()
        if row:
            return row["id"]

        fallback_color = color or self._default_color_for_name(name)
        cursor.execute(
            """
            INSERT INTO categories (user_id, name, color)
            VALUES (?, ?, ?)
            """,
            (user_id, name, fallback_color),
        )
        logger.info("迁移中创建缺失分类: user_id={}, name={}", user_id, name)
        return int(cursor.lastrowid)

    @staticmethod
    def _default_color_for_name(name: str) -> str:
        palette = ["#006D77", "#0F766E", "#C2410C", "#2563EB", "#B45309", "#BE123C", "#4338CA", "#0F766E"]
        index = abs(hash(name)) % len(palette)
        return palette[index]

    @staticmethod
    def _status_to_completed(status: str) -> Optional[int]:
        if status == TaskService.STATUS_ALL:
            return None
        if status == TaskService.STATUS_PENDING:
            return 0
        if status == TaskService.STATUS_COMPLETED:
            return 1
        raise ValueError("状态必须是 all/pending/completed 之一")

    def _task_base_query(self) -> str:
        return """
            SELECT
                t.id,
                t.user_id,
                t.category_id,
                t.title,
                t.description,
                COALESCE(c.name, t.category) AS category,
                COALESCE(c.color, '#94A3B8') AS category_color,
                t.quadrant,
                t.completed,
                t.due_at,
                t.recurrence_rule,
                t.created_at,
                t.updated_at
            FROM tasks t
            LEFT JOIN categories c ON c.id = t.category_id
        """

    def register_user(self, username: str, password: str) -> Dict:
        username_norm = self._validate_username(username)
        self._validate_password(password)
        logger.info("准备注册用户: {}", username_norm)

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
            user_id = int(cursor.lastrowid)
            self._seed_default_categories(cursor, user_id)
            conn.commit()
        except sqlite3.IntegrityError as exc:
            logger.warning("用户注册失败，用户名已存在: {}", username_norm)
            conn.close()
            raise ValueError("用户名已存在") from exc
        except sqlite3.Error:
            logger.exception("用户注册数据库写入失败: {}", username_norm)
            conn.close()
            raise

        cursor.execute("SELECT id, username, created_at FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        logger.info("用户注册成功: user_id={}, username={}", user_id, username_norm)
        return {"id": row["id"], "username": row["username"], "created_at": row["created_at"]}

    def login_user(self, username: str, password: str, remember_me: bool = False) -> Optional[Dict]:
        username_norm = username.strip()
        if not username_norm or not password:
            logger.warning("用户登录失败，请求参数不完整")
            return None

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
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
                logger.warning("用户登录失败，用户名不存在: {}", username_norm)
                return None

            expected_hash = self._hash_password(password, user["password_salt"])
            if not hmac.compare_digest(expected_hash, user["password_hash"]):
                logger.warning("用户登录失败，密码校验不通过: {}", username_norm)
                return None

            token = secrets.token_urlsafe(32)
            token_hash = self._hash_token(token)
            token_placeholder = secrets.token_urlsafe(16)
            ttl_hours = self.TOKEN_TTL_REMEMBER_HOURS if remember_me else self.TOKEN_TTL_HOURS
            expires_at = (datetime.utcnow() + timedelta(hours=ttl_hours)).strftime("%Y-%m-%d %H:%M:%S")

            self._seed_default_categories(cursor, int(user["id"]))
            cursor.execute(
                """
                INSERT INTO auth_tokens (user_id, token, token_hash, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (user["id"], token_placeholder, token_hash, expires_at),
            )

            cursor.execute("DELETE FROM auth_tokens WHERE expires_at <= ?", (self._now_str(),))
            expired_count = cursor.rowcount
            conn.commit()
            logger.info(
                "用户登录成功: user_id={}, username={}, remember_me={}, 清理过期令牌={}条",
                user["id"],
                username_norm,
                remember_me,
                expired_count,
            )
            return {
                "token": token,
                "expires_at": expires_at,
                "user": {"id": user["id"], "username": user["username"], "created_at": user["created_at"]},
            }
        except sqlite3.Error:
            logger.exception("用户登录数据库操作失败: {}", username_norm)
            raise
        finally:
            conn.close()

    def verify_token(self, token: str) -> Optional[Dict]:
        if not token:
            logger.warning("令牌校验失败，token 为空")
            return None

        conn = self._get_connection()
        cursor = conn.cursor()
        token_hash = self._hash_token(token)
        try:
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
            if not row:
                logger.warning("令牌校验未通过: {}", self._mask_token(token))
                return None

            logger.info("令牌校验成功: user_id={}", row["id"])
            return {
                "id": row["id"],
                "username": row["username"],
                "created_at": row["created_at"],
                "token_expires_at": row["expires_at"],
            }
        except sqlite3.Error:
            logger.exception("令牌校验数据库查询失败: {}", self._mask_token(token))
            raise
        finally:
            conn.close()

    def logout(self, token: str) -> bool:
        if not token:
            logger.warning("退出登录失败，token 为空")
            return False

        conn = self._get_connection()
        cursor = conn.cursor()
        token_hash = self._hash_token(token)
        try:
            cursor.execute("DELETE FROM auth_tokens WHERE token_hash = ?", (token_hash,))
            conn.commit()
            removed = cursor.rowcount > 0
            if removed:
                logger.info("退出登录成功: {}", self._mask_token(token))
            else:
                logger.warning("退出登录未删除任何令牌: {}", self._mask_token(token))
            return removed
        except sqlite3.Error:
            logger.exception("退出登录数据库删除失败: {}", self._mask_token(token))
            raise
        finally:
            conn.close()

    def list_categories(self, user_id: int) -> List[Dict]:
        uid = self._validate_user_id(user_id)
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            self._seed_default_categories(cursor, uid)
            cursor.execute(
                """
                SELECT id, name, color, created_at
                FROM categories
                WHERE user_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (uid,),
            )
            rows = cursor.fetchall()
            conn.commit()
            logger.info("查询分类成功: user_id={}, count={}", uid, len(rows))
            return [self._row_to_category(row) for row in rows]
        except sqlite3.Error:
            logger.exception("查询分类失败: user_id={}", uid)
            raise
        finally:
            conn.close()

    def get_categories(self, user_id: Optional[int] = None) -> List:
        if user_id is None:
            return [item["name"] for item in self.DEFAULT_CATEGORIES]
        return self.list_categories(user_id)

    def create_category(self, user_id: int, name: str, color: str) -> Dict:
        uid = self._validate_user_id(user_id)
        name_checked = self._validate_category_name(name)
        color_checked = self._validate_category_color(color)
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO categories (user_id, name, color)
                VALUES (?, ?, ?)
                """,
                (uid, name_checked, color_checked),
            )
            category_id = int(cursor.lastrowid)
            conn.commit()
            logger.info("创建分类成功: user_id={}, category_id={}, name={}", uid, category_id, name_checked)
        except sqlite3.IntegrityError as exc:
            logger.warning("创建分类失败，名称重复: user_id={}, name={}", uid, name_checked)
            conn.close()
            raise ValueError("分类名称已存在") from exc
        except sqlite3.Error:
            logger.exception("创建分类失败: user_id={}, name={}", uid, name_checked)
            conn.close()
            raise

        cursor.execute(
            "SELECT id, name, color, created_at FROM categories WHERE id = ? AND user_id = ?",
            (category_id, uid),
        )
        row = cursor.fetchone()
        conn.close()
        return self._row_to_category(row)

    def update_category(self, category_id: int, user_id: int, name: str, color: str) -> Optional[Dict]:
        uid = self._validate_user_id(user_id)
        cid = self._validate_positive_int(category_id, "分类ID无效")
        name_checked = self._validate_category_name(name)
        color_checked = self._validate_category_color(color)
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE categories
                SET name = ?, color = ?
                WHERE id = ? AND user_id = ?
                """,
                (name_checked, color_checked, cid, uid),
            )
            if cursor.rowcount == 0:
                conn.commit()
                logger.warning("更新分类失败，记录不存在: user_id={}, category_id={}", uid, cid)
                return None

            cursor.execute(
                """
                UPDATE tasks
                SET category = ?, updated_at = datetime('now')
                WHERE user_id = ? AND category_id = ?
                """,
                (name_checked, uid, cid),
            )
            conn.commit()
            logger.info("更新分类成功: user_id={}, category_id={}", uid, cid)
        except sqlite3.IntegrityError as exc:
            logger.warning("更新分类失败，名称重复: user_id={}, category_id={}", uid, cid)
            conn.close()
            raise ValueError("分类名称已存在") from exc
        except sqlite3.Error:
            logger.exception("更新分类失败: user_id={}, category_id={}", uid, cid)
            conn.close()
            raise

        cursor.execute(
            "SELECT id, name, color, created_at FROM categories WHERE id = ? AND user_id = ?",
            (cid, uid),
        )
        row = cursor.fetchone()
        conn.close()
        return self._row_to_category(row)

    def delete_category(self, category_id: int, user_id: int) -> bool:
        uid = self._validate_user_id(user_id)
        cid = self._validate_positive_int(category_id, "分类ID无效")
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) AS total FROM tasks WHERE user_id = ? AND category_id = ?", (uid, cid))
            in_use = int(cursor.fetchone()["total"])
            if in_use > 0:
                logger.warning("删除分类失败，仍有关联任务: user_id={}, category_id={}, count={}", uid, cid, in_use)
                raise ValueError("分类下还有任务，无法删除")

            cursor.execute("DELETE FROM categories WHERE id = ? AND user_id = ?", (cid, uid))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info("删除分类成功: user_id={}, category_id={}", uid, cid)
            else:
                logger.warning("删除分类失败，记录不存在: user_id={}, category_id={}", uid, cid)
            return deleted
        except sqlite3.Error:
            logger.exception("删除分类失败: user_id={}, category_id={}", uid, cid)
            raise
        finally:
            conn.close()

    def add_task(
        self,
        user_id: int,
        title: str,
        description: Optional[str] = "",
        category: str = "工作",
        quadrant: int = 1,
        completed: bool = False,
        due_at: Optional[str] = None,
        recurrence_rule: str = "none",
    ) -> Dict:
        uid = self._validate_user_id(user_id)
        title_trimmed = self._validate_title(title)
        category_name, category_id = self._resolve_category_for_user(uid, category)
        quadrant_checked = self._validate_quadrant(quadrant)
        completed_value = self._bool_to_db(completed)
        due_at_value = self._normalize_due_at(due_at)
        recurrence_value = self._validate_recurrence_rule(recurrence_rule)
        logger.info("准备新增任务: user_id={}, title={}", uid, title_trimmed)

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO tasks (
                    user_id, category_id, title, description, category, quadrant, completed, due_at, recurrence_rule
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uid,
                    category_id,
                    title_trimmed,
                    (description or "").strip(),
                    category_name,
                    quadrant_checked,
                    completed_value,
                    due_at_value,
                    recurrence_value,
                ),
            )
            conn.commit()
            task_id = int(cursor.lastrowid)
            logger.info("新增任务成功: task_id={}, user_id={}", task_id, uid)
        except sqlite3.Error:
            logger.exception("新增任务失败: user_id={}, title={}", uid, title_trimmed)
            conn.close()
            raise
        conn.close()

        task = self.get_task_by_id(task_id, uid)
        if task is None:
            logger.error("任务写入后读取失败: task_id={}, user_id={}", task_id, uid)
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
        completed: Optional[bool] = None,
        due_at: Optional[str] = None,
        recurrence_rule: Optional[str] = None,
    ) -> bool:
        uid = self._validate_user_id(user_id)
        tid = self._validate_positive_int(task_id, "任务ID无效")

        updates: List[str] = []
        params: List = []

        if title is not None:
            updates.append("title = ?")
            params.append(self._validate_title(title))
        if description is not None:
            updates.append("description = ?")
            params.append(description.strip())
        if category is not None:
            category_name, category_id = self._resolve_category_for_user(uid, category)
            updates.append("category = ?")
            params.append(category_name)
            updates.append("category_id = ?")
            params.append(category_id)
        if quadrant is not None:
            updates.append("quadrant = ?")
            params.append(self._validate_quadrant(quadrant))
        if completed is not None:
            updates.append("completed = ?")
            params.append(self._bool_to_db(completed))
        if due_at is not None:
            updates.append("due_at = ?")
            params.append(self._normalize_due_at(due_at))
        if recurrence_rule is not None:
            updates.append("recurrence_rule = ?")
            params.append(self._validate_recurrence_rule(recurrence_rule))

        updates.append("updated_at = datetime('now')")

        conn = self._get_connection()
        cursor = conn.cursor()
        sql = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND user_id = ?"
        params.extend([tid, uid])
        try:
            cursor.execute(sql, params)
            conn.commit()
            updated = cursor.rowcount > 0
            if updated:
                logger.info("更新任务成功: task_id={}, user_id={}", tid, uid)
            else:
                logger.warning("更新任务失败，记录不存在: task_id={}, user_id={}", tid, uid)
            return updated
        except sqlite3.Error:
            logger.exception("更新任务数据库操作失败: task_id={}, user_id={}", tid, uid)
            raise
        finally:
            conn.close()

    def set_task_completed(self, task_id: int, user_id: int, completed: bool) -> bool:
        logger.info("准备更新任务状态: task_id={}, user_id={}, completed={}", task_id, user_id, completed)
        return self.update_task(task_id=task_id, user_id=user_id, completed=completed)

    def delete_task(self, task_id: int, user_id: int) -> bool:
        uid = self._validate_user_id(user_id)
        tid = self._validate_positive_int(task_id, "任务ID无效")

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (tid, uid))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info("删除任务成功: task_id={}, user_id={}", tid, uid)
            else:
                logger.warning("删除任务失败，记录不存在: task_id={}, user_id={}", tid, uid)
            return deleted
        except sqlite3.Error:
            logger.exception("删除任务数据库操作失败: task_id={}, user_id={}", tid, uid)
            raise
        finally:
            conn.close()

    def get_task_by_id(self, task_id: int, user_id: int) -> Optional[Dict]:
        uid = self._validate_user_id(user_id)
        tid = self._validate_positive_int(task_id, "任务ID无效")

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"""
                {self._task_base_query()}
                WHERE t.id = ? AND t.user_id = ?
                """,
                (tid, uid),
            )
            row = cursor.fetchone()
            if row:
                logger.info("查询任务详情成功: task_id={}, user_id={}", tid, uid)
            else:
                logger.warning("查询任务详情未命中: task_id={}, user_id={}", tid, uid)
            return self._row_to_task(row) if row else None
        except sqlite3.Error:
            logger.exception("查询任务详情失败: task_id={}, user_id={}", tid, uid)
            raise
        finally:
            conn.close()

    def get_all_tasks(self, user_id: int, status: str = STATUS_PENDING) -> List[Dict]:
        uid = self._validate_user_id(user_id)
        completed_filter = self._validate_status(status)

        conn = self._get_connection()
        cursor = conn.cursor()
        params: List = [uid]
        where_sql = "WHERE t.user_id = ?"
        if completed_filter is not None:
            where_sql += " AND t.completed = ?"
            params.append(completed_filter)
        try:
            cursor.execute(
                f"""
                {self._task_base_query()}
                {where_sql}
                ORDER BY t.created_at DESC, t.id DESC
                """,
                params,
            )
            rows = cursor.fetchall()
            logger.info("查询全部任务成功: user_id={}, status={}, count={}", uid, status, len(rows))
            return [self._row_to_task(row) for row in rows]
        except sqlite3.Error:
            logger.exception("查询全部任务失败: user_id={}, status={}", uid, status)
            raise
        finally:
            conn.close()

    def filter_tasks(
        self,
        user_id: int,
        category: Optional[str] = None,
        quadrant: Optional[int] = None,
        status: str = STATUS_PENDING,
    ) -> List[Dict]:
        uid = self._validate_user_id(user_id)
        completed_filter = self._validate_status(status)

        conditions: List[str] = ["t.user_id = ?"]
        params: List = [uid]

        if category and category != "全部":
            conditions.append("COALESCE(c.name, t.category) = ?")
            params.append(category)

        if quadrant and str(quadrant) != "全部":
            conditions.append("t.quadrant = ?")
            params.append(self._validate_quadrant(int(quadrant)))

        if completed_filter is not None:
            conditions.append("t.completed = ?")
            params.append(completed_filter)

        where_sql = "WHERE " + " AND ".join(conditions)

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"""
                {self._task_base_query()}
                {where_sql}
                ORDER BY t.created_at DESC, t.id DESC
                """,
                params,
            )
            rows = cursor.fetchall()
            logger.info(
                "筛选任务成功: user_id={}, category={}, quadrant={}, status={}, count={}",
                uid,
                category,
                quadrant,
                status,
                len(rows),
            )
            return [self._row_to_task(row) for row in rows]
        except sqlite3.Error:
            logger.exception("筛选任务失败: user_id={}", uid)
            raise
        finally:
            conn.close()

    def search_tasks(self, user_id: int, keyword: str, status: str = STATUS_PENDING) -> List[Dict]:
        uid = self._validate_user_id(user_id)
        completed_filter = self._validate_status(status)

        if not keyword or not keyword.strip():
            return self.get_all_tasks(uid, status=status)

        search_term = f"%{keyword.strip()}%"
        conn = self._get_connection()
        cursor = conn.cursor()
        params: List = [uid, search_term, search_term]
        where_sql = "WHERE t.user_id = ? AND (t.title LIKE ? OR t.description LIKE ?)"
        if completed_filter is not None:
            where_sql += " AND t.completed = ?"
            params.append(completed_filter)
        try:
            cursor.execute(
                f"""
                {self._task_base_query()}
                {where_sql}
                ORDER BY t.created_at DESC, t.id DESC
                """,
                params,
            )
            rows = cursor.fetchall()
            logger.info(
                "搜索任务成功: user_id={}, keyword={}, status={}, count={}",
                uid,
                keyword.strip(),
                status,
                len(rows),
            )
            return [self._row_to_task(row) for row in rows]
        except sqlite3.Error:
            logger.exception("搜索任务失败: user_id={}, keyword={}", uid, keyword.strip())
            raise
        finally:
            conn.close()

    def get_sorted_tasks(self, user_id: int, sort_by: str = "created_desc", status: str = STATUS_PENDING) -> List[Dict]:
        uid = self._validate_user_id(user_id)
        completed_filter = self._validate_status(status)

        sort_mapping = {
            "created_desc": "t.created_at DESC, t.id DESC",
            "created_asc": "t.created_at ASC, t.id ASC",
            "updated_desc": "t.updated_at DESC, t.id DESC",
            "updated_asc": "t.updated_at ASC, t.id ASC",
        }
        order_clause = sort_mapping.get(sort_by, sort_mapping["created_desc"])

        conn = self._get_connection()
        cursor = conn.cursor()
        params: List = [uid]
        where_sql = "WHERE t.user_id = ?"
        if completed_filter is not None:
            where_sql += " AND t.completed = ?"
            params.append(completed_filter)
        try:
            cursor.execute(
                f"""
                {self._task_base_query()}
                {where_sql}
                ORDER BY {order_clause}
                """,
                params,
            )
            rows = cursor.fetchall()
            logger.info(
                "排序查询任务成功: user_id={}, sort_by={}, status={}, count={}",
                uid,
                sort_by,
                status,
                len(rows),
            )
            return [self._row_to_task(row) for row in rows]
        except sqlite3.Error:
            logger.exception("排序查询任务失败: user_id={}, sort_by={}", uid, sort_by)
            raise
        finally:
            conn.close()

    def get_statistics(self, user_id: int) -> Dict:
        all_tasks = self.get_all_tasks(user_id, status=self.STATUS_ALL)
        categories = self.list_categories(user_id)
        category_stats = {category["name"]: 0 for category in categories}
        quadrant_stats = {1: 0, 2: 0, 3: 0, 4: 0}
        completed_count = 0

        for task in all_tasks:
            category_stats.setdefault(task["category"], 0)
            category_stats[task["category"]] += 1
            quadrant_stats[task["quadrant"]] += 1
            if task["completed"]:
                completed_count += 1

        return {
            "total": len(all_tasks),
            "completed": completed_count,
            "pending": len(all_tasks) - completed_count,
            "by_category": category_stats,
            "by_quadrant": quadrant_stats,
        }

    def _resolve_weekly_report_window(self, end_date: Optional[str], days: int) -> tuple[date, date, int]:
        days_checked = max(1, min(int(days), 31))
        end_day = datetime.strptime(self._normalize_date_value(end_date), "%Y-%m-%d").date()
        start_day = end_day - timedelta(days=days_checked - 1)
        return start_day, end_day, days_checked

    def get_weekly_report(self, user_id: int, end_date: Optional[str] = None, days: int = 7) -> Dict:
        uid = self._validate_user_id(user_id)
        start_day, end_day, days_checked = self._resolve_weekly_report_window(end_date, days)
        start_iso = start_day.isoformat()
        end_iso = end_day.isoformat()

        tasks = self.get_all_tasks(uid, status=self.STATUS_ALL)
        categories = self.list_categories(uid)
        task_category_stats = {category["name"]: 0 for category in categories}
        task_quadrant_stats = {1: 0, 2: 0, 3: 0, 4: 0}
        created_tasks: List[Dict] = []
        completed_tasks: List[Dict] = []

        for task in tasks:
            created_at = datetime.strptime(task["created_at"], "%Y-%m-%d %H:%M:%S").date()
            if not (start_day <= created_at <= end_day):
                continue
            created_tasks.append(task)
            task_category_stats.setdefault(task["category"], 0)
            task_category_stats[task["category"]] += 1
            task_quadrant_stats[task["quadrant"]] += 1
            if task["completed"]:
                completed_tasks.append(task)

        tasks_created = len(created_tasks)
        tasks_completed = len(completed_tasks)
        completion_rate = int(round((tasks_completed / max(tasks_created, tasks_completed, 1)) * 100))
        top_completed_titles = [
            task["title"]
            for task in sorted(completed_tasks, key=lambda item: (item["updated_at"], item["id"]), reverse=True)[:3]
        ]

        pomodoro_stats = self.get_pomodoro_stats(uid, start_date=start_iso, end_date=end_iso, days=days_checked)
        pomodoro_by_date = [
            {
                "date": day,
                "focus_minutes": int(bucket["work"]["completed_minutes"]),
                "focus_sessions": int(bucket["work"]["completed_count"]),
            }
            for day, bucket in sorted(pomodoro_stats["by_date"].items())
        ]

        all_checkins = self._list_all_checkins(uid)
        all_phone_focus = self._list_all_phone_focus(uid)
        checkin_map: Dict[str, set[str]] = {}
        phone_map: Dict[str, Dict[str, int]] = {}

        for item in all_checkins:
            checkin_day = datetime.strptime(item["checkin_date"], "%Y-%m-%d").date()
            if not (start_day <= checkin_day <= end_day):
                continue
            checkin_map.setdefault(item["checkin_date"], set()).add(item["period"])

        for item in all_phone_focus:
            resisted_day = datetime.strptime(item["resisted_at"], "%Y-%m-%d %H:%M:%S").date()
            if not (start_day <= resisted_day <= end_day):
                continue
            day_key = resisted_day.isoformat()
            bucket = phone_map.setdefault(day_key, {"minutes": 0, "sessions": 0})
            bucket["minutes"] += int(item["duration_minutes"])
            bucket["sessions"] += 1

        habit_by_date: List[Dict[str, object]] = []
        checkin_days = 0
        full_checkin_days = 0
        phone_focus_minutes = 0
        phone_focus_sessions = 0
        for offset in range(days_checked):
            current_day = start_day + timedelta(days=offset)
            day_key = current_day.isoformat()
            period_count = len(checkin_map.get(day_key, set()))
            full_checkin = period_count == len(self.CHECKIN_PERIODS)
            phone_bucket = phone_map.get(day_key, {"minutes": 0, "sessions": 0})
            habit_by_date.append(
                {
                    "date": day_key,
                    "period_count": period_count,
                    "is_full": full_checkin,
                    "phone_focus_minutes": phone_bucket["minutes"],
                    "phone_focus_sessions": phone_bucket["sessions"],
                }
            )
            if period_count:
                checkin_days += 1
            if full_checkin:
                full_checkin_days += 1
            phone_focus_minutes += phone_bucket["minutes"]
            phone_focus_sessions += phone_bucket["sessions"]

        focus_minutes = int(pomodoro_stats["summary"]["focus_minutes"])
        focus_sessions = int(pomodoro_stats["summary"]["focus_sessions"])
        top_quadrant = max(task_quadrant_stats.items(), key=lambda item: (item[1], -item[0]))[0]
        completed_days = sum(1 for item in habit_by_date if item["period_count"] > 0)
        missing_full_days = max(0, days_checked - full_checkin_days)

        insights = {
            "highlight": (
                f"本周创建 {tasks_created} 个任务，完成 {tasks_completed} 个，完成率 {completion_rate}%。"
                if tasks_created or tasks_completed
                else "本周暂无任务数据，建议先创建一条周计划。"
            ),
            "focus": (
                f"本周累计专注 {focus_minutes} 分钟，完成 {focus_sessions} 次专注番茄。"
                if focus_sessions
                else "本周尚未记录有效的专注番茄，可继续保持聚焦节奏。"
            ),
            "habit": (
                f"本周有 {completed_days} 天完成工位打卡，其中 {full_checkin_days} 天达成三段全勤。"
                if completed_days
                else "本周尚未记录工位打卡，建议固定早中晚三个打卡节点。"
            ),
            "improvement": (
                f"第{top_quadrant}象限任务最多，建议继续优先处理重要事项。"
                if tasks_created
                else f"本周还剩 {missing_full_days} 天未达成三段全勤，可优先补齐日常习惯。"
            ),
        }

        return {
            "range": {
                "start_date": start_iso,
                "end_date": end_iso,
                "days": days_checked,
                "label": f"{start_iso} ~ {end_iso}",
            },
            "summary": {
                "tasks_created": tasks_created,
                "tasks_completed": tasks_completed,
                "completion_rate": completion_rate,
                "focus_minutes": focus_minutes,
                "focus_sessions": focus_sessions,
                "checkin_days": checkin_days,
                "full_checkin_days": full_checkin_days,
                "phone_focus_minutes": phone_focus_minutes,
                "phone_focus_sessions": phone_focus_sessions,
            },
            "tasks": {
                "created": tasks_created,
                "completed": tasks_completed,
                "completion_rate": completion_rate,
                "by_quadrant": task_quadrant_stats,
                "by_category": task_category_stats,
                "top_completed_titles": top_completed_titles,
            },
            "pomodoro": {
                "focus_minutes": focus_minutes,
                "focus_sessions": focus_sessions,
                "completed_sessions": int(pomodoro_stats["summary"]["completed_sessions"]),
                "by_date": pomodoro_by_date,
            },
            "habits": {
                "checkin_days": checkin_days,
                "full_checkin_days": full_checkin_days,
                "phone_focus_minutes": phone_focus_minutes,
                "phone_focus_sessions": phone_focus_sessions,
                "checkins_by_date": [
                    {
                        "date": item["date"],
                        "period_count": item["period_count"],
                        "is_full": item["is_full"],
                    }
                    for item in habit_by_date
                ],
                "phone_focus_by_date": [
                    {
                        "date": item["date"],
                        "minutes": item["phone_focus_minutes"],
                        "sessions": item["phone_focus_sessions"],
                    }
                    for item in habit_by_date
                ],
            },
            "insights": insights,
        }

    def record_pomodoro_session(
        self,
        user_id: int,
        session_type: str,
        duration_minutes: int,
        completed: bool = True,
        session_date: Optional[str] = None,
        note: str = "",
    ) -> Dict:
        uid = self._validate_user_id(user_id)
        session_type_checked = self._validate_pomodoro_type(session_type)
        duration_checked = self._validate_pomodoro_duration(duration_minutes)
        date_checked = self._normalize_date_value(session_date)
        note_checked = (note or "").strip()
        if len(note_checked) > 120:
            raise ValueError("note must not exceed 120 characters")

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO pomodoro_sessions (
                    user_id, session_date, session_type, duration_minutes, completed, note
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (uid, date_checked, session_type_checked, duration_checked, self._bool_to_db(completed), note_checked),
            )
            conn.commit()
            record_id = int(cursor.lastrowid)
            cursor.execute(
                """
                SELECT id, user_id, session_date, session_type, duration_minutes, completed, note, created_at, updated_at
                FROM pomodoro_sessions
                WHERE id = ?
                """,
                (record_id,),
            )
            row = cursor.fetchone()
            return self._row_to_pomodoro_session(row)
        finally:
            conn.close()

    def list_pomodoro_sessions(
        self,
        user_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        session_type: Optional[str] = None,
        completed: Optional[bool] = None,
        days: int = 7,
    ) -> List[Dict]:
        uid = self._validate_user_id(user_id)
        end_day = datetime.strptime(self._normalize_date_value(end_date), "%Y-%m-%d").date()
        if start_date:
            start_day = datetime.strptime(self._normalize_date_value(start_date), "%Y-%m-%d").date()
        else:
            days_checked = max(1, min(int(days), 90))
            start_day = end_day - timedelta(days=days_checked - 1)
        if start_day > end_day:
            raise ValueError("start_date must not be later than end_date")

        params: List = [uid, start_day.isoformat(), end_day.isoformat()]
        where_sql = "WHERE user_id = ? AND session_date BETWEEN ? AND ?"
        if session_type:
            where_sql += " AND session_type = ?"
            params.append(self._validate_pomodoro_type(session_type))
        if completed is not None:
            where_sql += " AND completed = ?"
            params.append(self._bool_to_db(completed))

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"""
                SELECT id, user_id, session_date, session_type, duration_minutes, completed, note, created_at, updated_at
                FROM pomodoro_sessions
                {where_sql}
                ORDER BY session_date DESC, created_at DESC, id DESC
                """,
                params,
            )
            return [self._row_to_pomodoro_session(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_pomodoro_stats(
        self,
        user_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 7,
    ) -> Dict:
        uid = self._validate_user_id(user_id)
        end_day = datetime.strptime(self._normalize_date_value(end_date), "%Y-%m-%d").date()
        if start_date:
            start_day = datetime.strptime(self._normalize_date_value(start_date), "%Y-%m-%d").date()
        else:
            days_checked = max(1, min(int(days), 90))
            start_day = end_day - timedelta(days=days_checked - 1)
        if start_day > end_day:
            raise ValueError("start_date must not be later than end_date")

        sessions = self.list_pomodoro_sessions(uid, start_day.isoformat(), end_day.isoformat(), days=days)
        by_date: Dict[str, Dict[str, object]] = {}
        for offset in range((end_day - start_day).days + 1):
            current = start_day + timedelta(days=offset)
            by_date[current.isoformat()] = self._empty_pomodoro_day()

        totals = self._empty_pomodoro_day()
        type_totals = {session_type: {"count": 0, "minutes": 0, "completed": 0} for session_type in self.POMODORO_TYPES}
        for session in sessions:
            day_bucket = by_date.setdefault(session["session_date"], self._empty_pomodoro_day())
            self._accumulate_pomodoro_bucket(day_bucket, session)
            self._accumulate_pomodoro_bucket(totals, session)

            type_bucket = type_totals[session["session_type"]]
            type_bucket["count"] += 1
            type_bucket["minutes"] += int(session["duration_minutes"])
            type_bucket["completed"] += 1 if session["completed"] else 0

        focus_sessions = totals["work"]["completed_count"]
        focus_minutes = totals["work"]["completed_minutes"]

        return {
            "range": {
                "start_date": start_day.isoformat(),
                "end_date": end_day.isoformat(),
            },
            "summary": {
                "total_sessions": totals["total_count"],
                "completed_sessions": totals["total_completed"],
                "focus_sessions": focus_sessions,
                "focus_minutes": focus_minutes,
                "work_sessions": totals["work"]["count"],
                "short_break_sessions": totals["short_break"]["count"],
                "long_break_sessions": totals["long_break"]["count"],
            },
            "by_type": type_totals,
            "by_date": by_date,
            "items": sessions,
        }

    def record_workstation_checkin(
        self,
        user_id: int,
        period: str,
        checkin_date: Optional[str] = None,
    ) -> Dict:
        uid = self._validate_user_id(user_id)
        period_checked = self._validate_checkin_period(period)
        date_checked = self._normalize_date_value(checkin_date)

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO workstation_checkins (user_id, checkin_date, period)
                VALUES (?, ?, ?)
                """,
                (uid, date_checked, period_checked),
            )
            conn.commit()
            record_id = int(cursor.lastrowid)
            cursor.execute(
                """
                SELECT id, user_id, checkin_date, period, created_at
                FROM workstation_checkins
                WHERE id = ?
                """,
                (record_id,),
            )
            row = cursor.fetchone()
            return self._row_to_checkin(row)
        except sqlite3.IntegrityError as exc:
            raise ValueError("该时段已完成打卡，请勿重复打卡") from exc
        finally:
            conn.close()

    def list_workstation_checkins(
        self,
        user_id: int,
        days: int = 7,
        end_date: Optional[str] = None,
    ) -> List[Dict]:
        uid = self._validate_user_id(user_id)
        days_checked = max(1, min(int(days), 90))
        end_day = datetime.strptime(self._normalize_date_value(end_date), "%Y-%m-%d").date()
        start_day = end_day - timedelta(days=days_checked - 1)

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, user_id, checkin_date, period, created_at
                FROM workstation_checkins
                WHERE user_id = ?
                  AND checkin_date BETWEEN ? AND ?
                ORDER BY checkin_date DESC, created_at DESC, id DESC
                """,
                (uid, start_day.isoformat(), end_day.isoformat()),
            )
            rows = cursor.fetchall()
            return [self._row_to_checkin(row) for row in rows]
        finally:
            conn.close()

    def record_phone_focus(
        self,
        user_id: int,
        duration_minutes: int,
        note: str = "",
        resisted_at: Optional[str] = None,
    ) -> Dict:
        uid = self._validate_user_id(user_id)
        duration_checked = self._validate_duration_minutes(duration_minutes)
        resisted_at_checked = self._normalize_datetime_input(resisted_at)
        note_checked = (note or "").strip()
        if len(note_checked) > 120:
            raise ValueError("备注不能超过120个字符")

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO phone_focus_records (user_id, duration_minutes, note, resisted_at)
                VALUES (?, ?, ?, ?)
                """,
                (uid, duration_checked, note_checked, resisted_at_checked),
            )
            conn.commit()
            record_id = int(cursor.lastrowid)
            cursor.execute(
                """
                SELECT id, user_id, duration_minutes, note, resisted_at, created_at
                FROM phone_focus_records
                WHERE id = ?
                """,
                (record_id,),
            )
            row = cursor.fetchone()
            return self._row_to_phone_focus(row)
        finally:
            conn.close()

    def list_phone_focus_records(
        self,
        user_id: int,
        days: int = 14,
        end_date: Optional[str] = None,
    ) -> List[Dict]:
        uid = self._validate_user_id(user_id)
        days_checked = max(1, min(int(days), 180))
        end_day = datetime.strptime(self._normalize_date_value(end_date), "%Y-%m-%d").date()
        start_dt = datetime.combine(end_day - timedelta(days=days_checked - 1), datetime.min.time())
        end_dt = datetime.combine(end_day, datetime.max.time()).replace(microsecond=0)

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, user_id, duration_minutes, note, resisted_at, created_at
                FROM phone_focus_records
                WHERE user_id = ?
                  AND resisted_at BETWEEN ? AND ?
                ORDER BY resisted_at DESC, id DESC
                """,
                (uid, start_dt.strftime("%Y-%m-%d %H:%M:%S"), end_dt.strftime("%Y-%m-%d %H:%M:%S")),
            )
            rows = cursor.fetchall()
            return [self._row_to_phone_focus(row) for row in rows]
        finally:
            conn.close()

    def get_habit_dashboard(self, user_id: int, today: Optional[str] = None) -> Dict:
        uid = self._validate_user_id(user_id)
        today_value = self._normalize_date_value(today)
        today_records = self.list_workstation_checkins(uid, days=1, end_date=today_value)
        recent_checkins = self.list_workstation_checkins(uid, days=14, end_date=today_value)
        recent_phone_focus = self.list_phone_focus_records(uid, days=14, end_date=today_value)

        all_checkins = self._list_all_checkins(uid)
        all_phone_focus = self._list_all_phone_focus(uid)

        by_date: Dict[str, set[str]] = {}
        for item in all_checkins:
            by_date.setdefault(item["checkin_date"], set()).add(item["period"])

        sorted_dates = sorted(by_date.keys())
        checkin_days = len(sorted_dates)
        full_day_dates = sorted(date for date, periods in by_date.items() if len(periods) == len(self.CHECKIN_PERIODS))
        full_day_count = len(full_day_dates)
        full_day_streak = self._compute_consecutive_day_streak(full_day_dates, today_value)
        total_checkins = sum(len(periods) for periods in by_date.values())
        total_phone_minutes = sum(item["duration_minutes"] for item in all_phone_focus)
        total_phone_sessions = len(all_phone_focus)

        achievements = self._build_habit_achievements(
            today_value=today_value,
            today_periods={item["period"] for item in today_records},
            checkin_days=checkin_days,
            full_day_count=full_day_count,
            full_day_streak=full_day_streak,
            total_phone_minutes=total_phone_minutes,
            total_phone_sessions=total_phone_sessions,
        )

        return {
            "today": {
                "date": today_value,
                "periods": {period: any(item["period"] == period for item in today_records) for period in self.CHECKIN_PERIODS},
                "records": sorted(today_records, key=lambda item: self.CHECKIN_PERIODS.index(item["period"])),
            },
            "recent_checkins": recent_checkins,
            "recent_phone_focus": recent_phone_focus,
            "summary": {
                "total_checkins": total_checkins,
                "checkin_days": checkin_days,
                "full_day_count": full_day_count,
                "full_day_streak": full_day_streak,
                "total_phone_minutes": total_phone_minutes,
                "total_phone_sessions": total_phone_sessions,
                "unlocked_achievements": sum(1 for item in achievements if item["unlocked"]),
            },
            "achievements": achievements,
        }

    def get_schedule_overview(self, user_id: int, now: Optional[datetime] = None) -> Dict[str, List[Dict]]:
        uid = self._validate_user_id(user_id)
        current = now or datetime.utcnow()
        start = datetime.combine(current.date(), datetime.min.time())
        end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)

        tasks = self.get_all_tasks(uid, status=self.STATUS_PENDING)
        today_items: List[Dict] = []
        week_items: List[Dict] = []
        today_key = current.strftime("%Y-%m-%d")

        for task in tasks:
            occurrences = self._expand_task_occurrences(task, start, end)
            for item in occurrences:
                if item["occurrence_date"] == today_key:
                    today_items.append(item)
                week_items.append(item)

        today_items.sort(key=lambda item: item["occurrence_at"])
        week_items.sort(key=lambda item: item["occurrence_at"])
        return {"today": today_items, "week": week_items}

    def get_calendar_view(self, user_id: int, start_date: Optional[str] = None, days: int = 35) -> Dict:
        uid = self._validate_user_id(user_id)
        days_checked = max(1, min(int(days), 90))
        start_dt = (
            datetime.strptime(start_date, "%Y-%m-%d")
            if start_date
            else datetime.combine(datetime.utcnow().date(), datetime.min.time())
        )
        end_dt = start_dt + timedelta(days=days_checked, seconds=-1)

        tasks = self.get_all_tasks(uid, status=self.STATUS_PENDING)
        items: List[Dict] = []
        grouped: Dict[str, List[Dict]] = {}
        for task in tasks:
            for item in self._expand_task_occurrences(task, start_dt, end_dt):
                items.append(item)
                grouped.setdefault(item["occurrence_date"], []).append(item)

        items.sort(key=lambda item: item["occurrence_at"])
        for key in grouped:
            grouped[key].sort(key=lambda item: item["occurrence_at"])

        return {
            "start_date": start_dt.strftime("%Y-%m-%d"),
            "days": days_checked,
            "items": items,
            "by_date": grouped,
        }

    def get_tasks_grouped_by_quadrant(self, user_id: int, status: str = STATUS_ALL) -> Dict[int, List[Dict]]:
        grouped = {1: [], 2: [], 3: [], 4: []}
        for task in self.get_all_tasks(user_id, status=status):
            grouped[task["quadrant"]].append(task)
        return grouped

    def get_tasks_grouped_by_category(self, user_id: int, status: str = STATUS_ALL) -> Dict[str, List[Dict]]:
        grouped = {category["name"]: [] for category in self.list_categories(user_id)}
        for task in self.get_all_tasks(user_id, status=status):
            grouped.setdefault(task["category"], [])
            grouped[task["category"]].append(task)
        return grouped

    def clear_all_tasks(self, user_id: int) -> None:
        uid = self._validate_user_id(user_id)
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM tasks WHERE user_id = ?", (uid,))
            conn.commit()
            logger.warning("已清空用户全部任务: user_id={}, count={}", uid, cursor.rowcount)
        except sqlite3.Error:
            logger.exception("清空任务失败: user_id={}", uid)
            raise
        finally:
            conn.close()

    def export_tasks_csv(self, user_id: int) -> str:
        uid = self._validate_user_id(user_id)
        tasks = self.get_all_tasks(uid, status=self.STATUS_ALL)
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "title",
                "description",
                "category",
                "quadrant",
                "completed",
                "due_at",
                "recurrence_rule",
                "created_at",
                "updated_at",
            ],
        )
        writer.writeheader()
        for task in tasks:
            writer.writerow(
                {
                    "title": task["title"],
                    "description": task["description"],
                    "category": task["category"],
                    "quadrant": task["quadrant"],
                    "completed": 1 if task["completed"] else 0,
                    "due_at": task["due_at"] or "",
                    "recurrence_rule": task["recurrence_rule"],
                    "created_at": task["created_at"],
                    "updated_at": task["updated_at"],
                }
            )
        return "\ufeff" + output.getvalue()

    def import_tasks_csv(self, user_id: int, csv_text: str) -> Dict[str, int]:
        uid = self._validate_user_id(user_id)
        raw = (csv_text or "").lstrip("\ufeff").strip()
        if not raw:
            raise ValueError("导入内容不能为空")

        reader = csv.DictReader(io.StringIO(raw))
        required = {"title", "description", "category", "quadrant", "completed", "due_at", "recurrence_rule"}
        headers = set(reader.fieldnames or [])
        if not required.issubset(headers):
            raise ValueError("CSV 缺少必要列")

        conn = self._get_connection()
        cursor = conn.cursor()
        imported = 0
        skipped = 0
        try:
            self._seed_default_categories(cursor, uid)
            for row in reader:
                if not any((value or "").strip() for value in row.values()):
                    skipped += 1
                    continue
                title = self._validate_title(row.get("title", ""))
                description = (row.get("description") or "").strip()
                category_name = self._validate_category_name(row.get("category", ""))
                quadrant = self._validate_quadrant(int((row.get("quadrant") or "").strip() or 0))
                completed_raw = (row.get("completed") or "0").strip().lower()
                completed = completed_raw in {"1", "true", "yes", "y"}
                due_at = self._normalize_due_at(row.get("due_at"))
                recurrence_rule = self._validate_recurrence_rule(row.get("recurrence_rule") or "none")
                created_at = self._normalize_datetime_or_now(row.get("created_at"))
                updated_at = self._normalize_datetime_or_now(row.get("updated_at"), fallback=created_at)
                category_id = self._ensure_category_exists(cursor, uid, category_name)

                cursor.execute(
                    """
                    INSERT INTO tasks (
                        user_id, category_id, title, description, category, quadrant, completed,
                        due_at, recurrence_rule, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uid,
                        category_id,
                        title,
                        description,
                        category_name,
                        quadrant,
                        self._bool_to_db(completed),
                        due_at,
                        recurrence_rule,
                        created_at,
                        updated_at,
                    ),
                )
                imported += 1
            conn.commit()
            return {"imported": imported, "skipped": skipped}
        except (sqlite3.Error, ValueError):
            conn.rollback()
            raise
        finally:
            conn.close()

    def _list_all_checkins(self, user_id: int) -> List[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, user_id, checkin_date, period, created_at
                FROM workstation_checkins
                WHERE user_id = ?
                ORDER BY checkin_date ASC, created_at ASC, id ASC
                """,
                (user_id,),
            )
            return [self._row_to_checkin(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def _list_all_phone_focus(self, user_id: int) -> List[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, user_id, duration_minutes, note, resisted_at, created_at
                FROM phone_focus_records
                WHERE user_id = ?
                ORDER BY resisted_at ASC, id ASC
                """,
                (user_id,),
            )
            return [self._row_to_phone_focus(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    @classmethod
    def _compute_consecutive_day_streak(cls, dates: List[str], end_date: Optional[str] = None) -> int:
        if not dates:
            return 0
        target = datetime.strptime(end_date or dates[-1], "%Y-%m-%d").date()
        date_set = {datetime.strptime(value, "%Y-%m-%d").date() for value in dates}
        streak = 0
        current = target
        while current in date_set:
            streak += 1
            current -= timedelta(days=1)
        return streak

    def _build_habit_achievements(
        self,
        *,
        today_value: str,
        today_periods: set[str],
        checkin_days: int,
        full_day_count: int,
        full_day_streak: int,
        total_phone_minutes: int,
        total_phone_sessions: int,
    ) -> List[Dict]:
        defs = [
            ("first_checkin", "工位晨启", "首次完成工位打卡", checkin_days, 1),
            ("full_day", "三段全勤", "单日完成早中晚三段打卡", full_day_count, 1),
            ("steady_worker", "稳定到岗", "累计完成3天工位打卡", checkin_days, 3),
            ("phone_hour", "克机一小时", "累计克制玩手机60分钟", total_phone_minutes, 60),
            ("phone_guard", "手机克星", "累计完成5次克制玩手机记录", total_phone_sessions, 5),
            ("discipline_master", "自律达人", "连续3天全勤打卡", full_day_streak, 3),
        ]
        return [
            {
                "key": key,
                "title": title,
                "description": description,
                "progress": min(progress, target),
                "target": target,
                "unlocked": progress >= target,
                "today_unlocked": key == "full_day" and len(today_periods) == len(self.CHECKIN_PERIODS),
                "today": today_value,
            }
            for key, title, description, progress, target in defs
        ]

    @staticmethod
    def _empty_pomodoro_day() -> Dict[str, object]:
        return {
            "total_count": 0,
            "total_completed": 0,
            "focus_count": 0,
            "focus_minutes": 0,
            "work": {"count": 0, "completed_count": 0, "minutes": 0, "completed_minutes": 0},
            "short_break": {"count": 0, "completed_count": 0, "minutes": 0, "completed_minutes": 0},
            "long_break": {"count": 0, "completed_count": 0, "minutes": 0, "completed_minutes": 0},
        }

    @staticmethod
    def _accumulate_pomodoro_bucket(bucket: Dict[str, object], session: Dict) -> None:
        session_type = session["session_type"]
        session_bucket = bucket[session_type]
        session_bucket["count"] += 1
        session_bucket["minutes"] += int(session["duration_minutes"])
        if session["completed"]:
            session_bucket["completed_count"] += 1
            session_bucket["completed_minutes"] += int(session["duration_minutes"])
            bucket["total_completed"] += 1
            if session_type == "work":
                bucket["focus_count"] += 1
                bucket["focus_minutes"] += int(session["duration_minutes"])
        bucket["total_count"] += 1

    def _validate_user_id(self, user_id: int) -> int:
        if not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("用户未登录或用户ID无效")
        return user_id

    @staticmethod
    def _validate_positive_int(value: int, message: str) -> int:
        if not isinstance(value, int) or value <= 0:
            raise ValueError(message)
        return value

    def _validate_title(self, title: str) -> str:
        title_trimmed = (title or "").strip()
        if not title_trimmed:
            raise ValueError("任务标题不能为空")
        if len(title_trimmed) < 2:
            raise ValueError("任务标题太短（至少2个字符）")
        return title_trimmed

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

    @staticmethod
    def _validate_category_name(name: str) -> str:
        name_checked = (name or "").strip()
        if len(name_checked) < 1:
            raise ValueError("分类名称不能为空")
        if len(name_checked) > 20:
            raise ValueError("分类名称不能超过20个字符")
        return name_checked

    @staticmethod
    def _validate_category_color(color: str) -> str:
        color_checked = (color or "").strip()
        if len(color_checked) != 7 or not color_checked.startswith("#"):
            raise ValueError("分类颜色必须是 #RRGGBB 格式")
        hex_part = color_checked[1:]
        if any(ch not in "0123456789abcdefABCDEF" for ch in hex_part):
            raise ValueError("分类颜色必须是 #RRGGBB 格式")
        return color_checked.upper()

    def _validate_status(self, status: str) -> Optional[int]:
        status_checked = (status or self.STATUS_PENDING).strip().lower()
        return self._status_to_completed(status_checked)

    @classmethod
    def _validate_checkin_period(cls, period: str) -> str:
        checked = (period or "").strip().lower()
        if checked not in cls.CHECKIN_PERIODS:
            raise ValueError("打卡时段必须是 morning/noon/evening 之一")
        return checked

    @staticmethod
    def _validate_duration_minutes(value: int) -> int:
        if not isinstance(value, int) or value <= 0:
            raise ValueError("克制玩手机时长必须是正整数分钟")
        if value > 24 * 60:
            raise ValueError("克制玩手机时长不能超过1440分钟")
        return value

    @staticmethod
    def _normalize_date_value(value: Optional[str]) -> str:
        raw = (value or "").strip()
        if not raw:
            return datetime.utcnow().strftime("%Y-%m-%d")
        try:
            return datetime.strptime(raw, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("日期格式无效，应为 YYYY-MM-DD") from exc

    @staticmethod
    def _parse_due_at(value: Optional[str]) -> Optional[datetime]:
        if value is None:
            return None
        raw = str(value).strip()
        if not raw:
            return None
        normalized = raw.replace("T", " ")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(normalized, fmt)
            except ValueError:
                continue
        return None

    def _normalize_due_at(self, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        raw = str(value).strip()
        if not raw:
            return None
        parsed = self._parse_due_at(raw)
        if parsed is None:
            raise ValueError("截止日期时间格式无效")
        return parsed.strftime("%Y-%m-%d %H:%M:%S")

    def _normalize_datetime_or_now(self, value: Optional[str], fallback: Optional[str] = None) -> str:
        raw = (value or "").strip()
        if not raw:
            return fallback or self._now_str()
        parsed = self._parse_due_at(raw)
        if parsed is None:
            raise ValueError("CSV 中存在无效时间格式")
        return parsed.strftime("%Y-%m-%d %H:%M:%S")

    def _normalize_datetime_input(self, value: Optional[str]) -> str:
        if value is None or not str(value).strip():
            return self._now_str()
        parsed = self._parse_due_at(value)
        if parsed is None:
            raise ValueError("日期时间格式无效，应为 YYYY-MM-DD HH:MM[:SS]")
        return parsed.strftime("%Y-%m-%d %H:%M:%S")

    @classmethod
    def _validate_pomodoro_type(cls, session_type: str) -> str:
        checked = (session_type or "").strip().lower()
        if checked not in cls.POMODORO_TYPES:
            raise ValueError("session_type must be work, short_break, or long_break")
        return checked

    @staticmethod
    def _validate_pomodoro_duration(duration_minutes: int) -> int:
        if not isinstance(duration_minutes, int) or duration_minutes <= 0:
            raise ValueError("duration_minutes must be a positive integer")
        if duration_minutes > 480:
            raise ValueError("duration_minutes must not exceed 480")
        return duration_minutes

    @staticmethod
    def _validate_recurrence_rule(value: str) -> str:
        rule = (value or "none").strip().lower()
        if rule not in {"none", "daily", "weekly", "monthly"}:
            raise ValueError("重复日程必须是 none/daily/weekly/monthly 之一")
        return rule

    @staticmethod
    def _format_delta_label(prefix: str, delta: timedelta) -> str:
        total_minutes = max(1, int(delta.total_seconds() // 60))
        days, remainder = divmod(total_minutes, 60 * 24)
        hours, minutes = divmod(remainder, 60)
        parts: List[str] = []
        if days:
            parts.append(f"{days}天")
        if hours:
            parts.append(f"{hours}小时")
        if minutes or not parts:
            parts.append(f"{minutes}分钟")
        return prefix + "".join(parts[:2])

    @classmethod
    def _build_due_status(cls, due_at: Optional[str], completed: bool) -> Dict[str, Optional[object]]:
        if not due_at:
            return {"due_at": None, "due_state": "none", "due_text": "未设置截止时间", "due_minutes": None}

        due_dt = cls._parse_due_at(due_at)
        if due_dt is None:
            return {"due_at": due_at, "due_state": "invalid", "due_text": "截止时间无效", "due_minutes": None}

        now = datetime.utcnow()
        delta = due_dt - now
        due_minutes = int(delta.total_seconds() // 60)
        if completed:
            state = "completed"
            text = f"截止于 {due_dt.strftime('%Y-%m-%d %H:%M')}"
        elif delta.total_seconds() < 0:
            state = "overdue"
            text = cls._format_delta_label("已逾期", now - due_dt)
        else:
            state = "upcoming"
            text = cls._format_delta_label("剩余", delta)

        return {
            "due_at": due_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "due_state": state,
            "due_text": text,
            "due_minutes": due_minutes,
        }

    @staticmethod
    def _task_due_sort_key(task: Dict) -> tuple[int, str, int]:
        return (0 if task.get("due_at") else 1, task.get("due_at") or "", int(task["id"]))

    def _expand_task_occurrences(self, task: Dict, start: datetime, end: datetime) -> List[Dict]:
        due_dt = self._parse_due_at(task.get("due_at"))
        if due_dt is None:
            return []

        rule = task.get("recurrence_rule") or "none"
        occurrences: List[Dict] = []
        current = due_dt
        occurrence_index = 0
        while current <= end:
            if current >= start:
                item = dict(task)
                item["occurrence_at"] = current.strftime("%Y-%m-%d %H:%M:%S")
                item["occurrence_date"] = current.strftime("%Y-%m-%d")
                item["occurrence_index"] = occurrence_index
                occurrences.append(item)
            if rule == "none":
                break
            if rule == "daily":
                current += timedelta(days=1)
            elif rule == "weekly":
                current += timedelta(days=7)
            else:
                month = current.month + 1
                year = current.year
                if month > 12:
                    month = 1
                    year += 1
                next_day = min(current.day, 28)
                current = current.replace(year=year, month=month, day=next_day)
            occurrence_index += 1
        return occurrences

    def _resolve_category_for_user(self, user_id: int, category: str) -> tuple[str, int]:
        category_name = self._validate_category_name(category)
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            self._seed_default_categories(cursor, user_id)
            cursor.execute(
                """
                SELECT id, name
                FROM categories
                WHERE user_id = ? AND name = ?
                """,
                (user_id, category_name),
            )
            row = cursor.fetchone()
            conn.commit()
            if not row:
                logger.warning("分类不存在: user_id={}, category={}", user_id, category_name)
                raise ValueError("任务分类不存在，请先创建分类")
            return row["name"], int(row["id"])
        finally:
            conn.close()

    @staticmethod
    def _bool_to_db(value: bool) -> int:
        return 1 if bool(value) else 0

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
    def _row_to_category(row: sqlite3.Row) -> Dict:
        return {
            "id": row["id"],
            "name": row["name"],
            "color": row["color"],
            "created_at": row["created_at"],
        }

    @staticmethod
    def _row_to_checkin(row: sqlite3.Row) -> Dict:
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "checkin_date": row["checkin_date"],
            "period": row["period"],
            "created_at": row["created_at"],
        }

    @staticmethod
    def _row_to_phone_focus(row: sqlite3.Row) -> Dict:
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "duration_minutes": row["duration_minutes"],
            "note": row["note"] or "",
            "resisted_at": row["resisted_at"],
            "created_at": row["created_at"],
        }

    @staticmethod
    def _row_to_pomodoro_session(row: sqlite3.Row) -> Dict:
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "session_date": row["session_date"],
            "session_type": row["session_type"],
            "duration_minutes": row["duration_minutes"],
            "completed": bool(row["completed"]),
            "note": row["note"] or "",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> Dict:
        due_info = TaskService._build_due_status(row["due_at"], bool(row["completed"]))
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "category_id": row["category_id"],
            "title": row["title"],
            "description": row["description"] or "",
            "category": row["category"],
            "category_color": row["category_color"],
            "quadrant": row["quadrant"],
            "completed": bool(row["completed"]),
            "due_at": due_info["due_at"],
            "due_state": due_info["due_state"],
            "due_text": due_info["due_text"],
            "due_minutes": due_info["due_minutes"],
            "recurrence_rule": row["recurrence_rule"] or "none",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
