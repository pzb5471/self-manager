from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

from services.common import (
    ServiceContext,
    accumulate_pomodoro_bucket,
    bool_to_db,
    empty_pomodoro_day,
    row_to_pomodoro_session,
    validate_pomodoro_duration,
    validate_pomodoro_type,
    validate_user_id,
)


class PomodoroService:
    def __init__(
        self,
        context: ServiceContext,
        *,
        pomodoro_types: tuple[str, ...],
        normalize_date_value: Callable[[Optional[str]], str],
    ):
        self.context = context
        self.pomodoro_types = pomodoro_types
        self.normalize_date_value = normalize_date_value

    def record_pomodoro_session(
        self,
        user_id: int,
        session_type: str,
        duration_minutes: int,
        completed: bool = True,
        session_date: Optional[str] = None,
        note: str = "",
    ) -> Dict:
        uid = validate_user_id(user_id)
        session_type_checked = validate_pomodoro_type(session_type, self.pomodoro_types)
        duration_checked = validate_pomodoro_duration(duration_minutes)
        date_checked = self.normalize_date_value(session_date)
        note_checked = (note or "").strip()
        if len(note_checked) > 120:
            raise ValueError("note must not exceed 120 characters")

        with self.context.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO pomodoro_sessions (
                    user_id, session_date, session_type, duration_minutes, completed, note
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (uid, date_checked, session_type_checked, duration_checked, bool_to_db(completed), note_checked),
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
            return row_to_pomodoro_session(row)

    def list_pomodoro_sessions(
        self,
        user_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        session_type: Optional[str] = None,
        completed: Optional[bool] = None,
        days: int = 7,
    ) -> List[Dict]:
        uid = validate_user_id(user_id)
        end_day = datetime.strptime(self.normalize_date_value(end_date), "%Y-%m-%d").date()
        if start_date:
            start_day = datetime.strptime(self.normalize_date_value(start_date), "%Y-%m-%d").date()
        else:
            days_checked = max(1, min(int(days), 90))
            start_day = end_day - timedelta(days=days_checked - 1)
        if start_day > end_day:
            raise ValueError("start_date must not be later than end_date")

        params: List = [uid, start_day.isoformat(), end_day.isoformat()]
        where_sql = "WHERE user_id = ? AND session_date BETWEEN ? AND ?"
        if session_type:
            where_sql += " AND session_type = ?"
            params.append(validate_pomodoro_type(session_type, self.pomodoro_types))
        if completed is not None:
            where_sql += " AND completed = ?"
            params.append(bool_to_db(completed))

        with self.context.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT id, user_id, session_date, session_type, duration_minutes, completed, note, created_at, updated_at
                FROM pomodoro_sessions
                {where_sql}
                ORDER BY session_date DESC, created_at DESC, id DESC
                """,
                params,
            )
            return [row_to_pomodoro_session(row) for row in cursor.fetchall()]

    def get_pomodoro_stats(
        self,
        user_id: int,
        list_pomodoro_sessions: Callable[..., List[Dict]],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 7,
    ) -> Dict:
        uid = validate_user_id(user_id)
        end_day = datetime.strptime(self.normalize_date_value(end_date), "%Y-%m-%d").date()
        if start_date:
            start_day = datetime.strptime(self.normalize_date_value(start_date), "%Y-%m-%d").date()
        else:
            days_checked = max(1, min(int(days), 90))
            start_day = end_day - timedelta(days=days_checked - 1)
        if start_day > end_day:
            raise ValueError("start_date must not be later than end_date")

        sessions = list_pomodoro_sessions(uid, start_day.isoformat(), end_day.isoformat(), days=days)
        by_date: Dict[str, Dict[str, object]] = {}
        for offset in range((end_day - start_day).days + 1):
            current = start_day + timedelta(days=offset)
            by_date[current.isoformat()] = empty_pomodoro_day()

        totals = empty_pomodoro_day()
        type_totals = {st: {"count": 0, "minutes": 0, "completed": 0} for st in self.pomodoro_types}
        for session in sessions:
            day_bucket = by_date.setdefault(session["session_date"], empty_pomodoro_day())
            accumulate_pomodoro_bucket(day_bucket, session)
            accumulate_pomodoro_bucket(totals, session)

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
