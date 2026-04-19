from __future__ import annotations

import sqlite3
from typing import Dict, List, Optional

from loguru import logger

from services.common import (
    ServiceContext,
    default_color_for_name,
    row_to_category,
    validate_category_color,
    validate_category_name,
    validate_positive_int,
    validate_user_id,
)


class CategoryService:
    def __init__(self, context: ServiceContext):
        self.context = context

    def seed_default_categories(self, cursor: sqlite3.Cursor, user_id: int) -> None:
        for category in self.context.default_categories:
            cursor.execute(
                """
                INSERT OR IGNORE INTO categories (user_id, name, color)
                VALUES (?, ?, ?)
                """,
                (user_id, category["name"], category["color"]),
            )

    def ensure_category_exists(
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

        fallback_color = color or default_color_for_name(name)
        cursor.execute(
            """
            INSERT INTO categories (user_id, name, color)
            VALUES (?, ?, ?)
            """,
            (user_id, name, fallback_color),
        )
        logger.info("迁移中创建缺失分类: user_id={}, name={}", user_id, name)
        return int(cursor.lastrowid)

    def list_categories(self, user_id: int) -> List[Dict]:
        uid = validate_user_id(user_id)
        with self.context.connection() as conn:
            cursor = conn.cursor()
            self.seed_default_categories(cursor, uid)
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
            return [row_to_category(row) for row in rows]

    def get_categories(self, user_id: Optional[int], list_categories_func) -> List:
        if user_id is None:
            return [item["name"] for item in self.context.default_categories]
        return list_categories_func(user_id)

    def create_category(self, user_id: int, name: str, color: str) -> Dict:
        uid = validate_user_id(user_id)
        name_checked = validate_category_name(name)
        color_checked = validate_category_color(color)
        with self.context.connection() as conn:
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
                raise ValueError("分类名称已存在") from exc

            cursor.execute(
                "SELECT id, name, color, created_at FROM categories WHERE id = ? AND user_id = ?",
                (category_id, uid),
            )
            row = cursor.fetchone()
            return row_to_category(row)

    def update_category(self, category_id: int, user_id: int, name: str, color: str) -> Optional[Dict]:
        uid = validate_user_id(user_id)
        cid = validate_positive_int(category_id, "分类ID无效")
        name_checked = validate_category_name(name)
        color_checked = validate_category_color(color)
        with self.context.connection() as conn:
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
                raise ValueError("分类名称已存在") from exc

            cursor.execute(
                "SELECT id, name, color, created_at FROM categories WHERE id = ? AND user_id = ?",
                (cid, uid),
            )
            row = cursor.fetchone()
            return row_to_category(row) if row else None

    def delete_category(self, category_id: int, user_id: int) -> bool:
        uid = validate_user_id(user_id)
        cid = validate_positive_int(category_id, "分类ID无效")
        with self.context.connection() as conn:
            cursor = conn.cursor()
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

    def resolve_category_for_user(self, user_id: int, category: str) -> tuple[str, int]:
        category_name = validate_category_name(category)
        with self.context.connection() as conn:
            cursor = conn.cursor()
            self.seed_default_categories(cursor, user_id)
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
