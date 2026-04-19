from __future__ import annotations

import csv
import io
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional

from loguru import logger

from services.common import (
    ServiceContext,
    bool_to_db,
    normalize_due_at,
    parse_due_at,
    row_to_task,
    status_to_completed,
    validate_positive_int,
    validate_quadrant,
    validate_recurrence_rule,
    validate_title,
    validate_user_id,
)


class TaskDomainService:
    def __init__(
        self,
        context: ServiceContext,
        *,
        status_all: str,
        status_pending: str,
        task_base_query: Callable[[], str],
        resolve_category_for_user: Callable[[int, str], tuple[str, int]],
        expand_task_occurrences: Callable[[Dict, datetime, datetime], List[Dict]],
        list_categories: Callable[[int], List[Dict]],
    ):
        self.context = context
        self.status_all = status_all
        self.status_pending = status_pending
        self.task_base_query = task_base_query
        self.resolve_category_for_user = resolve_category_for_user
        self.expand_task_occurrences = expand_task_occurrences
        self.list_categories = list_categories

    def _validate_status(self, status: str) -> Optional[int]:
        status_checked = (status or self.status_pending).strip().lower()
        return status_to_completed(status_checked)

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
        uid = validate_user_id(user_id)
        title_trimmed = validate_title(title)
        category_name, category_id = self.resolve_category_for_user(uid, category)
        quadrant_checked = validate_quadrant(quadrant)
        completed_value = bool_to_db(completed)
        due_at_value = normalize_due_at(due_at)
        recurrence_value = validate_recurrence_rule(recurrence_rule)
        logger.info("准备新增任务: user_id={}, title={}", uid, title_trimmed)

        with self.context.connection() as conn:
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
                raise

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
    ) -> Optional[Dict]:
        uid = validate_user_id(user_id)
        tid = validate_positive_int(task_id, "任务ID无效")

        updates: List[str] = []
        params: List = []

        if title is not None:
            updates.append("title = ?")
            params.append(validate_title(title))
        if description is not None:
            updates.append("description = ?")
            params.append(description.strip())
        if category is not None:
            category_name, category_id = self.resolve_category_for_user(uid, category)
            updates.append("category = ?")
            params.append(category_name)
            updates.append("category_id = ?")
            params.append(category_id)
        if quadrant is not None:
            updates.append("quadrant = ?")
            params.append(validate_quadrant(quadrant))
        if completed is not None:
            updates.append("completed = ?")
            params.append(bool_to_db(completed))
        if due_at is not None:
            updates.append("due_at = ?")
            params.append(normalize_due_at(due_at))
        if recurrence_rule is not None:
            updates.append("recurrence_rule = ?")
            params.append(validate_recurrence_rule(recurrence_rule))

        updates.append("updated_at = datetime('now')")

        sql = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ? AND user_id = ?"
        params.extend([tid, uid])
        with self.context.connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, params)
                conn.commit()
                if cursor.rowcount == 0:
                    logger.warning("更新任务失败，记录不存在: task_id={}, user_id={}", tid, uid)
                    return None
                logger.info("更新任务成功: task_id={}, user_id={}", tid, uid)
                cursor.execute(
                    f"{self.task_base_query()} WHERE t.id = ? AND t.user_id = ?",
                    (tid, uid),
                )
                row = cursor.fetchone()
                return row_to_task(row) if row else None
            except sqlite3.Error:
                logger.exception("更新任务数据库操作失败: task_id={}, user_id={}", tid, uid)
                raise

    def delete_task(self, task_id: int, user_id: int) -> bool:
        uid = validate_user_id(user_id)
        tid = validate_positive_int(task_id, "任务ID无效")

        with self.context.connection() as conn:
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

    def get_task_by_id(self, task_id: int, user_id: int) -> Optional[Dict]:
        uid = validate_user_id(user_id)
        tid = validate_positive_int(task_id, "任务ID无效")

        with self.context.connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    f"""
                    {self.task_base_query()}
                    WHERE t.id = ? AND t.user_id = ?
                    """,
                    (tid, uid),
                )
                row = cursor.fetchone()
                if row:
                    logger.info("查询任务详情成功: task_id={}, user_id={}", tid, uid)
                else:
                    logger.warning("查询任务详情未命中: task_id={}, user_id={}", tid, uid)
                return row_to_task(row) if row else None
            except sqlite3.Error:
                logger.exception("查询任务详情失败: task_id={}, user_id={}", tid, uid)
                raise

    def get_all_tasks(self, user_id: int, status: str) -> List[Dict]:
        uid = validate_user_id(user_id)
        completed_filter = self._validate_status(status)

        params: List = [uid]
        where_sql = "WHERE t.user_id = ?"
        if completed_filter is not None:
            where_sql += " AND t.completed = ?"
            params.append(completed_filter)
        with self.context.connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    f"""
                    {self.task_base_query()}
                    {where_sql}
                    ORDER BY t.created_at DESC, t.id DESC
                    """,
                    params,
                )
                rows = cursor.fetchall()
                logger.info("查询全部任务成功: user_id={}, status={}, count={}", uid, status, len(rows))
                return [row_to_task(row) for row in rows]
            except sqlite3.Error:
                logger.exception("查询全部任务失败: user_id={}, status={}", uid, status)
                raise

    def filter_tasks(
        self,
        user_id: int,
        category: Optional[str] = None,
        quadrant: Optional[int] = None,
        status: str = "pending",
    ) -> List[Dict]:
        uid = validate_user_id(user_id)
        completed_filter = self._validate_status(status)

        conditions: List[str] = ["t.user_id = ?"]
        params: List = [uid]

        if category and category != "全部":
            conditions.append("COALESCE(c.name, t.category) = ?")
            params.append(category)

        if quadrant and str(quadrant) != "全部":
            conditions.append("t.quadrant = ?")
            params.append(validate_quadrant(int(quadrant)))

        if completed_filter is not None:
            conditions.append("t.completed = ?")
            params.append(completed_filter)

        where_sql = "WHERE " + " AND ".join(conditions)

        with self.context.connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    f"""
                    {self.task_base_query()}
                    {where_sql}
                    ORDER BY t.created_at DESC, t.id DESC
                    """,
                    params,
                )
                rows = cursor.fetchall()
                logger.info(
                    "筛选任务成功: user_id={}, category={}, quadrant={}, status={}, count={}",
                    uid, category, quadrant, status, len(rows),
                )
                return [row_to_task(row) for row in rows]
            except sqlite3.Error:
                logger.exception("筛选任务失败: user_id={}", uid)
                raise

    def search_tasks(self, user_id: int, keyword: str, status: str) -> List[Dict]:
        uid = validate_user_id(user_id)
        completed_filter = self._validate_status(status)

        if not keyword or not keyword.strip():
            return self.get_all_tasks(uid, status=status)

        search_term = f"%{keyword.strip()}%"
        params: List = [uid, search_term, search_term]
        where_sql = "WHERE t.user_id = ? AND (t.title LIKE ? OR t.description LIKE ?)"
        if completed_filter is not None:
            where_sql += " AND t.completed = ?"
            params.append(completed_filter)
        with self.context.connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    f"""
                    {self.task_base_query()}
                    {where_sql}
                    ORDER BY t.created_at DESC, t.id DESC
                    """,
                    params,
                )
                rows = cursor.fetchall()
                logger.info("搜索任务成功: user_id={}, keyword={}, status={}, count={}", uid, keyword.strip(), status, len(rows))
                return [row_to_task(row) for row in rows]
            except sqlite3.Error:
                logger.exception("搜索任务失败: user_id={}, keyword={}", uid, keyword.strip())
                raise

    def get_sorted_tasks(self, user_id: int, sort_by: str, status: str) -> List[Dict]:
        uid = validate_user_id(user_id)
        completed_filter = self._validate_status(status)

        sort_mapping = {
            "created_desc": "t.created_at DESC, t.id DESC",
            "created_asc": "t.created_at ASC, t.id ASC",
            "updated_desc": "t.updated_at DESC, t.id DESC",
            "updated_asc": "t.updated_at ASC, t.id ASC",
        }
        order_clause = sort_mapping.get(sort_by, sort_mapping["created_desc"])

        params: List = [uid]
        where_sql = "WHERE t.user_id = ?"
        if completed_filter is not None:
            where_sql += " AND t.completed = ?"
            params.append(completed_filter)
        with self.context.connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    f"""
                    {self.task_base_query()}
                    {where_sql}
                    ORDER BY {order_clause}
                    """,
                    params,
                )
                rows = cursor.fetchall()
                logger.info("排序查询任务成功: user_id={}, sort_by={}, status={}, count={}", uid, sort_by, status, len(rows))
                return [row_to_task(row) for row in rows]
            except sqlite3.Error:
                logger.exception("排序查询任务失败: user_id={}, sort_by={}", uid, sort_by)
                raise

    def list_tasks(
        self,
        user_id: int,
        keyword: Optional[str] = None,
        category: Optional[str] = None,
        quadrant: Optional[int] = None,
        sort_by: str = "created_desc",
        status: str = "pending",
    ) -> List[Dict]:
        uid = validate_user_id(user_id)

        has_keyword = keyword and keyword.strip()
        has_category = category and category != "全部"
        has_quadrant = quadrant is not None and str(quadrant) != "全部"

        if has_keyword:
            tasks = self.search_tasks(uid, keyword.strip(), status=status)
        elif has_category or has_quadrant:
            tasks = self.filter_tasks(uid, category=category, quadrant=quadrant, status=status)
        else:
            tasks = self.get_sorted_tasks(uid, sort_by, status=status)
            return tasks

        if has_category:
            tasks = [t for t in tasks if t["category"] == category]
        if has_quadrant:
            tasks = [t for t in tasks if t["quadrant"] == quadrant]

        sort_field = "created_at" if "created" in sort_by else "updated_at"
        reverse = "desc" in sort_by
        tasks.sort(key=lambda t: (t[sort_field], t["id"]), reverse=reverse)
        return tasks

    def get_statistics(self, user_id: int) -> Dict:
        all_tasks = self.get_all_tasks(user_id, status=self.status_all)
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

    def get_schedule_overview(self, user_id: int, now: Optional[datetime] = None) -> Dict[str, List[Dict]]:
        uid = validate_user_id(user_id)
        current = now or datetime.now(timezone.utc).replace(tzinfo=None)
        start = datetime.combine(current.date(), datetime.min.time())
        end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)

        tasks = self.get_all_tasks(uid, status=self.status_pending)
        today_items: List[Dict] = []
        week_items: List[Dict] = []
        today_key = current.strftime("%Y-%m-%d")

        for task in tasks:
            occurrences = self.expand_task_occurrences(task, start, end)
            for item in occurrences:
                if item["occurrence_date"] == today_key:
                    today_items.append(item)
                week_items.append(item)

        today_items.sort(key=lambda item: item["occurrence_at"])
        week_items.sort(key=lambda item: item["occurrence_at"])
        return {"today": today_items, "week": week_items}

    def get_calendar_view(self, user_id: int, start_date: Optional[str] = None, days: int = 35) -> Dict:
        uid = validate_user_id(user_id)
        days_checked = max(1, min(int(days), 90))
        start_dt = (
            datetime.strptime(start_date, "%Y-%m-%d")
            if start_date
            else datetime.combine(datetime.now(timezone.utc).replace(tzinfo=None).date(), datetime.min.time())
        )
        end_dt = start_dt + timedelta(days=days_checked, seconds=-1)

        tasks = self.get_all_tasks(uid, status=self.status_pending)
        items: List[Dict] = []
        grouped: Dict[str, List[Dict]] = {}
        for task in tasks:
            for item in self.expand_task_occurrences(task, start_dt, end_dt):
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

    def clear_all_tasks(self, user_id: int) -> None:
        uid = validate_user_id(user_id)
        with self.context.connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("DELETE FROM tasks WHERE user_id = ?", (uid,))
                conn.commit()
                logger.warning("已清空用户全部任务: user_id={}, count={}", uid, cursor.rowcount)
            except sqlite3.Error:
                logger.exception("清空任务失败: user_id={}", uid)
                raise

    def get_tasks_grouped_by_quadrant(self, user_id: int, status: str) -> Dict[int, List[Dict]]:
        grouped = {1: [], 2: [], 3: [], 4: []}
        for task in self.get_all_tasks(user_id, status=status):
            grouped[task["quadrant"]].append(task)
        return grouped

    def get_tasks_grouped_by_category(self, user_id: int, status: str) -> Dict[str, List[Dict]]:
        categories = self.list_categories(user_id)
        grouped = {category["name"]: [] for category in categories}
        for task in self.get_all_tasks(user_id, status=status):
            grouped.setdefault(task["category"], [])
            grouped[task["category"]].append(task)
        return grouped

    def export_tasks_csv(self, user_id: int, status_all: str) -> str:
        uid = validate_user_id(user_id)
        tasks = self.get_all_tasks(uid, status=status_all)
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "title", "description", "category", "quadrant",
                "completed", "due_at", "recurrence_rule", "created_at", "updated_at",
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
