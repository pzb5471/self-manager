from __future__ import annotations

from typing import Callable

from fastapi import Depends, FastAPI

from api.schemas import PhoneFocusPayload, WorkstationCheckinPayload
from service import TaskService


def register_habit_routes(app: FastAPI, service: TaskService, require_user: Callable[..., dict]) -> None:
    @app.get("/api/habits/dashboard")
    def habit_dashboard(today: str = "", user: dict = Depends(require_user)) -> dict:
        data = service.get_habit_dashboard(user["id"], today=today or None)
        return {"ok": True, **data}

    @app.get("/api/habits/checkins")
    def list_habit_checkins(days: int = 14, end_date: str = "", user: dict = Depends(require_user)) -> dict:
        items = service.list_workstation_checkins(user["id"], days=days, end_date=end_date or None)
        return {"ok": True, "items": items}

    @app.post("/api/habits/checkins")
    def create_habit_checkin(payload: WorkstationCheckinPayload, user: dict = Depends(require_user)) -> dict:
        item = service.record_workstation_checkin(
            user["id"],
            period=payload.period,
            checkin_date=payload.checkin_date or None,
        )
        return {"ok": True, "item": item}

    @app.get("/api/habits/phone-focus")
    def list_phone_focus(days: int = 14, end_date: str = "", user: dict = Depends(require_user)) -> dict:
        items = service.list_phone_focus_records(user["id"], days=days, end_date=end_date or None)
        return {"ok": True, "items": items}

    @app.post("/api/habits/phone-focus")
    def create_phone_focus(payload: PhoneFocusPayload, user: dict = Depends(require_user)) -> dict:
        item = service.record_phone_focus(
            user["id"],
            duration_minutes=payload.duration_minutes,
            note=payload.note,
            resisted_at=payload.resisted_at or None,
        )
        return {"ok": True, "item": item}
