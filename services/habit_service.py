from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

from services.common import (
    ServiceContext,
    row_to_checkin,
    row_to_phone_focus,
    validate_checkin_period,
    validate_duration_minutes,
    validate_user_id,
)


class HabitService:
    def __init__(
        self,
        context: ServiceContext,
        *,
        checkin_periods: tuple[str, ...],
        normalize_date_value: Callable[[Optional[str]], str],
        local_now_str: Callable[[], str],
        normalize_datetime_input: Callable[[Optional[str]], str],
        compute_consecutive_day_streak: Callable[[List[str], Optional[str]], int],
        build_habit_achievements: Callable[..., List[Dict]],
    ):
        self.context = context
        self.checkin_periods = checkin_periods
        self.normalize_date_value = normalize_date_value
        self.local_now_str = local_now_str
        self.normalize_datetime_input = normalize_datetime_input
        self.compute_consecutive_day_streak = compute_consecutive_day_streak
        self.build_habit_achievements = build_habit_achievements

    def record_workstation_checkin(self, user_id: int, period: str, checkin_date: Optional[str] = None) -> Dict:
        uid = validate_user_id(user_id)
        period_checked = validate_checkin_period(period, self.checkin_periods)
        date_checked = self.normalize_date_value(checkin_date)

        with self.context.connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO workstation_checkins (user_id, checkin_date, period, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (uid, date_checked, period_checked, self.local_now_str()),
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
                return row_to_checkin(row)
            except sqlite3.IntegrityError as exc:
                raise ValueError("该时段已完成打卡，请勿重复打卡") from exc

    def list_workstation_checkins(self, user_id: int, days: int = 7, end_date: Optional[str] = None) -> List[Dict]:
        uid = validate_user_id(user_id)
        days_checked = max(1, min(int(days), 90))
        end_day = datetime.strptime(self.normalize_date_value(end_date), "%Y-%m-%d").date()
        start_day = end_day - timedelta(days=days_checked - 1)

        with self.context.connection() as conn:
            cursor = conn.cursor()
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
            return [row_to_checkin(row) for row in cursor.fetchall()]

    def record_phone_focus(
        self,
        user_id: int,
        duration_minutes: int,
        note: str = "",
        resisted_at: Optional[str] = None,
    ) -> Dict:
        uid = validate_user_id(user_id)
        duration_checked = validate_duration_minutes(duration_minutes)
        resisted_at_checked = self.normalize_datetime_input(resisted_at)
        note_checked = (note or "").strip()
        if len(note_checked) > 120:
            raise ValueError("备注不能超过120个字符")

        with self.context.connection() as conn:
            cursor = conn.cursor()
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
            return row_to_phone_focus(row)

    def list_phone_focus_records(self, user_id: int, days: int = 14, end_date: Optional[str] = None) -> List[Dict]:
        uid = validate_user_id(user_id)
        days_checked = max(1, min(int(days), 180))
        end_day = datetime.strptime(self.normalize_date_value(end_date), "%Y-%m-%d").date()
        start_dt = datetime.combine(end_day - timedelta(days=days_checked - 1), datetime.min.time())
        end_dt = datetime.combine(end_day, datetime.max.time()).replace(microsecond=0)

        with self.context.connection() as conn:
            cursor = conn.cursor()
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
            return [row_to_phone_focus(row) for row in cursor.fetchall()]

    def list_all_checkins(self, user_id: int) -> List[Dict]:
        with self.context.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, user_id, checkin_date, period, created_at
                FROM workstation_checkins
                WHERE user_id = ?
                ORDER BY checkin_date ASC, created_at ASC, id ASC
                """,
                (user_id,),
            )
            return [row_to_checkin(row) for row in cursor.fetchall()]

    def list_all_phone_focus(self, user_id: int) -> List[Dict]:
        with self.context.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, user_id, duration_minutes, note, resisted_at, created_at
                FROM phone_focus_records
                WHERE user_id = ?
                ORDER BY resisted_at ASC, id ASC
                """,
                (user_id,),
            )
            return [row_to_phone_focus(row) for row in cursor.fetchall()]

    def get_habit_dashboard(
        self,
        user_id: int,
        *,
        list_workstation_checkins: Callable[..., List[Dict]],
        list_phone_focus_records: Callable[..., List[Dict]],
        today: Optional[str] = None,
    ) -> Dict:
        uid = validate_user_id(user_id)
        today_value = self.normalize_date_value(today)
        today_records = list_workstation_checkins(uid, days=1, end_date=today_value)
        recent_checkins = list_workstation_checkins(uid, days=14, end_date=today_value)
        recent_phone_focus = list_phone_focus_records(uid, days=14, end_date=today_value)

        all_checkins = self.list_all_checkins(uid)
        all_phone_focus = self.list_all_phone_focus(uid)

        by_date: Dict[str, set[str]] = {}
        for item in all_checkins:
            by_date.setdefault(item["checkin_date"], set()).add(item["period"])

        sorted_dates = sorted(by_date.keys())
        checkin_days = len(sorted_dates)
        full_day_dates = sorted(date for date, periods in by_date.items() if len(periods) == len(self.checkin_periods))
        full_day_count = len(full_day_dates)
        full_day_streak = self.compute_consecutive_day_streak(full_day_dates, today_value)
        total_checkins = sum(len(periods) for periods in by_date.values())
        total_phone_minutes = sum(item["duration_minutes"] for item in all_phone_focus)
        total_phone_sessions = len(all_phone_focus)

        achievements = self.build_habit_achievements(
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
                "periods": {period: any(item["period"] == period for item in today_records) for period in self.checkin_periods},
                "records": sorted(today_records, key=lambda item: self.checkin_periods.index(item["period"])),
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
