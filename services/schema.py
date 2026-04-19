"""Database schema creation, migrations, and index management."""

from __future__ import annotations

import sqlite3
from typing import Callable, List

from loguru import logger


def init_schema(
    conn: sqlite3.Connection,
    *,
    hash_token: Callable[[str], str],
    seed_categories_for_existing_users: Callable[[sqlite3.Cursor], None],
    migrate_task_categories: Callable[[sqlite3.Cursor], None],
) -> None:
    """Create tables, run migrations, and create indexes."""
    cursor = conn.cursor()
    logger.info("开始初始化数据库结构")

    # --- Table creation ---
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

    # --- Column migrations for tasks ---
    task_columns = [row["name"] for row in cursor.execute("PRAGMA table_info(tasks)").fetchall()]
    _add_column_if_missing(cursor, "tasks", task_columns, "user_id", "INTEGER")
    _add_column_if_missing(cursor, "tasks", task_columns, "category_id", "INTEGER")
    _add_column_if_missing(cursor, "tasks", task_columns, "completed", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(cursor, "tasks", task_columns, "due_at", "TEXT")
    _add_column_if_missing(cursor, "tasks", task_columns, "recurrence_rule", "TEXT NOT NULL DEFAULT 'none'")

    # --- Column migrations for auth_tokens ---
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
                (hash_token(row["token"]), row["id"]),
            )
        logger.info("历史 token_hash 数据迁移完成，共 {} 条", len(legacy_rows))

    # --- Data migrations ---
    seed_categories_for_existing_users(cursor)
    migrate_task_categories(cursor)

    # --- Indexes ---
    _create_indexes(cursor)

    conn.commit()
    logger.info("数据库初始化完成")


def _add_column_if_missing(
    cursor: sqlite3.Cursor,
    table: str,
    existing_columns: List[str],
    column: str,
    definition: str,
) -> None:
    if column not in existing_columns:
        logger.warning("检测到旧版 {} 表结构，准备补充 {} 字段", table, column)
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _create_indexes(cursor: sqlite3.Cursor) -> None:
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_tasks_category ON tasks(category)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_quadrant ON tasks(quadrant)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_user_created ON tasks(user_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_user_completed ON tasks(user_id, completed)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_category_id ON tasks(category_id)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_due_at ON tasks(due_at)",
        "CREATE INDEX IF NOT EXISTS idx_categories_user_id ON categories(user_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_categories_user_name ON categories(user_id, name)",
        "CREATE INDEX IF NOT EXISTS idx_auth_tokens_token ON auth_tokens(token)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_tokens_token_hash ON auth_tokens(token_hash)",
        "CREATE INDEX IF NOT EXISTS idx_auth_tokens_user ON auth_tokens(user_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_workstation_checkins_unique ON workstation_checkins(user_id, checkin_date, period)",
        "CREATE INDEX IF NOT EXISTS idx_workstation_checkins_user_date ON workstation_checkins(user_id, checkin_date DESC)",
        "CREATE INDEX IF NOT EXISTS idx_phone_focus_user_time ON phone_focus_records(user_id, resisted_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_pomodoro_sessions_user_date ON pomodoro_sessions(user_id, session_date DESC, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_pomodoro_sessions_user_type ON pomodoro_sessions(user_id, session_type)",
    ]
    for sql in indexes:
        cursor.execute(sql)
