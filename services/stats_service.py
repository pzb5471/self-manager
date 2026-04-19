from __future__ import annotations

from datetime import datetime, timedelta, timezone


def build_dashboard_trend(tasks: list[dict], days: int = 14) -> list[dict]:
    today = datetime.now(timezone.utc).replace(tzinfo=None).date()
    start = today - timedelta(days=days - 1)
    trend_map: dict[str, int] = {}

    for task in tasks:
        try:
            day = datetime.strptime(task["created_at"], "%Y-%m-%d %H:%M:%S").date()
        except ValueError:
            continue
        if day < start:
            continue
        key = day.isoformat()
        trend_map[key] = trend_map.get(key, 0) + 1

    trend = []
    for offset in range(days):
        current = start + timedelta(days=offset)
        iso = current.isoformat()
        trend.append({"date": iso, "count": trend_map.get(iso, 0)})
    return trend
