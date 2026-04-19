from __future__ import annotations

from typing import Callable

from fastapi import Depends, FastAPI, Query

from service import TaskService


def register_report_routes(app: FastAPI, service: TaskService, require_user: Callable[..., dict]) -> None:
    @app.get("/api/reports/weekly")
    def weekly_report(
        end_date: str = "",
        days: int = Query(default=7, ge=1, le=31),
        user: dict = Depends(require_user),
    ) -> dict:
        report = service.get_weekly_report(user["id"], end_date=end_date or None, days=days)
        return {"ok": True, "report": report}
