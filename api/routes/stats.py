from __future__ import annotations

from typing import Callable

from fastapi import Depends, FastAPI

from services.stats_service import build_dashboard_trend
from service import TaskService


def register_stats_routes(app: FastAPI, service: TaskService, require_user: Callable[..., dict]) -> None:
    @app.get("/api/stats/dashboard")
    def dashboard_stats(user: dict = Depends(require_user)) -> dict:
        user_id = user["id"]
        tasks = service.get_all_tasks(user_id, status=service.STATUS_ALL)
        stats = service.get_statistics(user_id)

        return {
            "ok": True,
            "stats": stats,
            "trend": build_dashboard_trend(tasks, days=14),
        }
