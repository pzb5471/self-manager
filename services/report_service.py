from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Optional

from services.common import validate_user_id


class ReportService:
    def __init__(
        self,
        *,
        checkin_periods: tuple[str, ...],
        normalize_date_value: Callable,
        list_all_checkins: Callable,
        list_all_phone_focus: Callable,
        get_all_tasks: Callable,
        list_categories: Callable,
        get_pomodoro_stats: Callable,
    ):
        self.checkin_periods = checkin_periods
        self.normalize_date_value = normalize_date_value
        self.list_all_checkins = list_all_checkins
        self.list_all_phone_focus = list_all_phone_focus
        self.get_all_tasks = get_all_tasks
        self.list_categories = list_categories
        self.get_pomodoro_stats = get_pomodoro_stats

    def resolve_weekly_report_window(self, end_date: Optional[str], days: int) -> tuple[date, date, int]:
        days_checked = max(1, min(int(days), 31))
        end_day = datetime.strptime(self.normalize_date_value(end_date), "%Y-%m-%d").date()
        start_day = end_day - timedelta(days=days_checked - 1)
        return start_day, end_day, days_checked

    def get_weekly_report(self, user_id: int, end_date: Optional[str] = None, days: int = 7) -> Dict:
        uid = validate_user_id(user_id)
        start_day, end_day, days_checked = self.resolve_weekly_report_window(end_date, days)
        start_iso = start_day.isoformat()
        end_iso = end_day.isoformat()

        tasks = self.get_all_tasks(uid, status="all")
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

        all_checkins = self.list_all_checkins(uid)
        all_phone_focus = self.list_all_phone_focus(uid)
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
            full_checkin = period_count == len(self.checkin_periods)
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
                f"第 {top_quadrant} 象限任务最多，建议继续优先处理重要事项。"
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
