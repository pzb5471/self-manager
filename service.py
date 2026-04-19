"""Self Manager service layer backed by SQLite."""

from __future__ import annotations

import csv
import io
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from services.auth_service import AuthService
from services.category_service import CategoryService
from services.common import (
    ServiceContext,
    bool_to_db,
    hash_password,
    hash_token,
    normalize_due_at,
    parse_due_at,
    validate_category_name,
    validate_quadrant,
    validate_recurrence_rule,
    validate_title,
    validate_user_id,
)
from services.habit_service import HabitService
from services.pomodoro_service import PomodoroService
from services.report_service import ReportService
from services.schema import init_schema
from services.task_service import TaskDomainService


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
        self._service_context = ServiceContext(
            get_connection=self._get_connection,
            now_str=self._now_str,
            local_now_str=self._local_now_str,
            mask_token=self._mask_token,
            default_categories=self.DEFAULT_CATEGORIES,
            password_iterations=self.PASSWORD_ITERATIONS,
            token_ttl_hours=self.TOKEN_TTL_HOURS,
            token_ttl_remember_hours=self.TOKEN_TTL_REMEMBER_HOURS,
        )
        self.category_service = CategoryService(self._service_context)
        self.auth_service = AuthService(self._service_context, self.category_service)
        self.task_service = TaskDomainService(
            self._service_context,
            status_all=self.STATUS_ALL,
            status_pending=self.STATUS_PENDING,
            task_base_query=self._task_base_query,
            resolve_category_for_user=self._resolve_category_for_user,
            expand_task_occurrences=self._expand_task_occurrences,
            list_categories=self.list_categories,
        )
        self.pomodoro_service = PomodoroService(
            self._service_context,
            pomodoro_types=self.POMODORO_TYPES,
            normalize_date_value=self._normalize_date_value,
        )
        self.habit_service = HabitService(
            self._service_context,
            checkin_periods=self.CHECKIN_PERIODS,
            normalize_date_value=self._normalize_date_value,
            local_now_str=self._local_now_str,
            normalize_datetime_input=self._normalize_datetime_input,
            compute_consecutive_day_streak=self._compute_consecutive_day_streak,
            build_habit_achievements=self._build_habit_achievements,
        )
        self.report_service = ReportService(
            checkin_periods=self.CHECKIN_PERIODS,
            normalize_date_value=self._normalize_date_value,
            list_all_checkins=self._list_all_checkins,
            list_all_phone_focus=self._list_all_phone_focus,
            get_all_tasks=self.get_all_tasks,
            list_categories=self.list_categories,
            get_pomodoro_stats=self.get_pomodoro_stats,
        )
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
        return datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _local_now() -> datetime:
        return datetime.now().astimezone().replace(tzinfo=None)

    @classmethod
    def _local_now_str(cls) -> str:
        return cls._local_now().strftime("%Y-%m-%d %H:%M:%S")

    @classmethod
    def _local_today_str(cls) -> str:
        return cls._local_now().strftime("%Y-%m-%d")

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
            init_schema(
                conn,
                hash_token=self._hash_token,
                seed_categories_for_existing_users=self._seed_categories_for_existing_users,
                migrate_task_categories=self._migrate_task_categories,
            )
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
        self.category_service.seed_default_categories(cursor, user_id)

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
        return self.category_service.ensure_category_exists(cursor, user_id, name, color)

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
        return self.auth_service.register_user(username, password)

    def login_user(self, username: str, password: str, remember_me: bool = False) -> Optional[Dict]:
        return self.auth_service.login_user(username, password, remember_me)

    def verify_token(self, token: str) -> Optional[Dict]:
        return self.auth_service.verify_token(token)

    def logout(self, token: str) -> bool:
        return self.auth_service.logout(token)

    def list_categories(self, user_id: int) -> List[Dict]:
        return self.category_service.list_categories(user_id)

    def get_categories(self, user_id: Optional[int] = None) -> List:
        return self.category_service.get_categories(user_id, self.list_categories)

    def create_category(self, user_id: int, name: str, color: str) -> Dict:
        return self.category_service.create_category(user_id, name, color)

    def update_category(self, category_id: int, user_id: int, name: str, color: str) -> Optional[Dict]:
        return self.category_service.update_category(category_id, user_id, name, color)

    def delete_category(self, category_id: int, user_id: int) -> bool:
        return self.category_service.delete_category(category_id, user_id)

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
        return self.task_service.add_task(user_id, title, description, category, quadrant, completed, due_at, recurrence_rule)

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
        return self.task_service.update_task(task_id, user_id, title, description, category, quadrant, completed, due_at, recurrence_rule)

    def set_task_completed(self, task_id: int, user_id: int, completed: bool) -> Optional[Dict]:
        logger.info("准备更新任务状态: task_id={}, user_id={}, completed={}", task_id, user_id, completed)
        return self.update_task(task_id=task_id, user_id=user_id, completed=completed)

    def delete_task(self, task_id: int, user_id: int) -> bool:
        return self.task_service.delete_task(task_id, user_id)

    def get_task_by_id(self, task_id: int, user_id: int) -> Optional[Dict]:
        return self.task_service.get_task_by_id(task_id, user_id)

    def get_all_tasks(self, user_id: int, status: str = STATUS_PENDING) -> List[Dict]:
        return self.task_service.get_all_tasks(user_id, status)

    def filter_tasks(
        self,
        user_id: int,
        category: Optional[str] = None,
        quadrant: Optional[int] = None,
        status: str = STATUS_PENDING,
    ) -> List[Dict]:
        return self.task_service.filter_tasks(user_id, category, quadrant, status)

    def search_tasks(self, user_id: int, keyword: str, status: str = STATUS_PENDING) -> List[Dict]:
        return self.task_service.search_tasks(user_id, keyword, status)

    def get_sorted_tasks(self, user_id: int, sort_by: str = "created_desc", status: str = STATUS_PENDING) -> List[Dict]:
        return self.task_service.get_sorted_tasks(user_id, sort_by, status)

    def list_tasks(
        self,
        user_id: int,
        keyword: Optional[str] = None,
        category: Optional[str] = None,
        quadrant: Optional[int] = None,
        sort_by: str = "created_desc",
        status: str = STATUS_PENDING,
    ) -> List[Dict]:
        return self.task_service.list_tasks(user_id, keyword, category, quadrant, sort_by, status)

    def get_statistics(self, user_id: int) -> Dict:
        return self.task_service.get_statistics(user_id)

    def _resolve_weekly_report_window(self, end_date: Optional[str], days: int) -> tuple[date, date, int]:
        return self.report_service.resolve_weekly_report_window(end_date, days)

    def get_weekly_report(self, user_id: int, end_date: Optional[str] = None, days: int = 7) -> Dict:
        return self.report_service.get_weekly_report(user_id, end_date, days)

    def record_pomodoro_session(
        self,
        user_id: int,
        session_type: str,
        duration_minutes: int,
        completed: bool = True,
        session_date: Optional[str] = None,
        note: str = "",
    ) -> Dict:
        return self.pomodoro_service.record_pomodoro_session(
            user_id, session_type, duration_minutes, completed, session_date, note,
        )

    def list_pomodoro_sessions(
        self,
        user_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        session_type: Optional[str] = None,
        completed: Optional[bool] = None,
        days: int = 7,
    ) -> List[Dict]:
        return self.pomodoro_service.list_pomodoro_sessions(
            user_id, start_date, end_date, session_type, completed, days,
        )

    def get_pomodoro_stats(
        self,
        user_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 7,
    ) -> Dict:
        return self.pomodoro_service.get_pomodoro_stats(
            user_id, list_pomodoro_sessions=self.list_pomodoro_sessions,
            start_date=start_date, end_date=end_date, days=days,
        )

    def record_workstation_checkin(
        self,
        user_id: int,
        period: str,
        checkin_date: Optional[str] = None,
    ) -> Dict:
        return self.habit_service.record_workstation_checkin(user_id, period, checkin_date)

    def list_workstation_checkins(
        self,
        user_id: int,
        days: int = 7,
        end_date: Optional[str] = None,
    ) -> List[Dict]:
        return self.habit_service.list_workstation_checkins(user_id, days, end_date)

    def record_phone_focus(
        self,
        user_id: int,
        duration_minutes: int,
        note: str = "",
        resisted_at: Optional[str] = None,
    ) -> Dict:
        return self.habit_service.record_phone_focus(user_id, duration_minutes, note, resisted_at)

    def list_phone_focus_records(
        self,
        user_id: int,
        days: int = 14,
        end_date: Optional[str] = None,
    ) -> List[Dict]:
        return self.habit_service.list_phone_focus_records(user_id, days, end_date)

    def get_habit_dashboard(self, user_id: int, today: Optional[str] = None) -> Dict:
        return self.habit_service.get_habit_dashboard(
            user_id,
            list_workstation_checkins=self.list_workstation_checkins,
            list_phone_focus_records=self.list_phone_focus_records,
            today=today,
        )

    def get_schedule_overview(self, user_id: int, now: Optional[datetime] = None) -> Dict[str, List[Dict]]:
        return self.task_service.get_schedule_overview(user_id, now)

    def get_calendar_view(self, user_id: int, start_date: Optional[str] = None, days: int = 35) -> Dict:
        return self.task_service.get_calendar_view(user_id, start_date, days)

    def get_tasks_grouped_by_quadrant(self, user_id: int, status: str = STATUS_ALL) -> Dict[int, List[Dict]]:
        return self.task_service.get_tasks_grouped_by_quadrant(user_id, status)

    def get_tasks_grouped_by_category(self, user_id: int, status: str = STATUS_ALL) -> Dict[str, List[Dict]]:
        return self.task_service.get_tasks_grouped_by_category(user_id, status)

    def clear_all_tasks(self, user_id: int) -> None:
        self.task_service.clear_all_tasks(user_id)

    def export_tasks_csv(self, user_id: int) -> str:
        return self.task_service.export_tasks_csv(user_id, self.STATUS_ALL)

    def import_tasks_csv(self, user_id: int, csv_text: str) -> Dict[str, int]:
        uid = validate_user_id(user_id)
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
                title = validate_title(row.get("title", ""))
                description = (row.get("description") or "").strip()
                category_name = validate_category_name(row.get("category", ""))
                quadrant = validate_quadrant(int((row.get("quadrant") or "").strip() or 0))
                completed_raw = (row.get("completed") or "0").strip().lower()
                completed = completed_raw in {"1", "true", "yes", "y"}
                due_at = normalize_due_at(row.get("due_at"))
                recurrence_rule = validate_recurrence_rule(row.get("recurrence_rule") or "none")
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
                        bool_to_db(completed),
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
        return self.habit_service.list_all_checkins(user_id)

    def _list_all_phone_focus(self, user_id: int) -> List[Dict]:
        return self.habit_service.list_all_phone_focus(user_id)

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
    def _normalize_date_value(value: Optional[str]) -> str:
        raw = (value or "").strip()
        if not raw:
            return TaskService._local_today_str()
        try:
            return datetime.strptime(raw, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("日期格式无效，应为 YYYY-MM-DD") from exc

    def _normalize_datetime_or_now(self, value: Optional[str], fallback: Optional[str] = None) -> str:
        raw = (value or "").strip()
        if not raw:
            return fallback or self._now_str()
        parsed = parse_due_at(raw)
        if parsed is None:
            raise ValueError("CSV 中存在无效时间格式")
        return parsed.strftime("%Y-%m-%d %H:%M:%S")

    def _normalize_datetime_input(self, value: Optional[str]) -> str:
        if value is None or not str(value).strip():
            return self._local_now_str()
        parsed = parse_due_at(value)
        if parsed is None:
            raise ValueError("日期时间格式无效，应为 YYYY-MM-DD HH:MM[:SS]")
        return parsed.strftime("%Y-%m-%d %H:%M:%S")

    def _expand_task_occurrences(self, task: Dict, start: datetime, end: datetime) -> List[Dict]:
        due_dt = parse_due_at(task.get("due_at"))
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
        return self.category_service.resolve_category_for_user(user_id, category)

    def _hash_password(self, password: str, salt_hex: str) -> str:
        return hash_password(password, salt_hex, self.PASSWORD_ITERATIONS)

    @staticmethod
    def _hash_token(token: str) -> str:
        return hash_token(token)
