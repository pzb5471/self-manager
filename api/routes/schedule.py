from __future__ import annotations

from typing import Callable

from fastapi import Depends, FastAPI

from service import TaskService


def register_schedule_routes(app: FastAPI, service: TaskService, require_user: Callable[..., dict]) -> None:
    @app.get("/api/schedule/overview")
    def schedule_overview(user: dict = Depends(require_user)) -> dict:
        overview = service.get_schedule_overview(user["id"])
        return {"ok": True, **overview}

    @app.get("/api/schedule/calendar")
    def schedule_calendar(
        start_date: str = "",
        days: int = 35,
        user: dict = Depends(require_user),
    ) -> dict:
        calendar = service.get_calendar_view(user["id"], start_date=start_date or None, days=days)
        return {"ok": True, **calendar}
