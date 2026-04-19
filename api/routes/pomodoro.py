from __future__ import annotations

from typing import Callable, Optional

from fastapi import Depends, FastAPI

from api.schemas import PomodoroSessionPayload
from service import TaskService


def register_pomodoro_routes(app: FastAPI, service: TaskService, require_user: Callable[..., dict]) -> None:
    @app.post("/api/pomodoro/sessions")
    def create_pomodoro_session(payload: PomodoroSessionPayload, user: dict = Depends(require_user)) -> dict:
        item = service.record_pomodoro_session(
            user["id"],
            session_type=payload.session_type,
            duration_minutes=payload.duration_minutes,
            completed=payload.completed,
            session_date=payload.session_date or None,
            note=payload.note,
        )
        return {"ok": True, "item": item}

    @app.get("/api/pomodoro/sessions")
    def list_pomodoro_sessions(
        start_date: str = "",
        end_date: str = "",
        session_type: str = "",
        completed: Optional[bool] = None,
        days: int = 7,
        user: dict = Depends(require_user),
    ) -> dict:
        items = service.list_pomodoro_sessions(
            user["id"],
            start_date=start_date or None,
            end_date=end_date or None,
            session_type=session_type or None,
            completed=completed,
            days=days,
        )
        return {"ok": True, "items": items}

    @app.get("/api/pomodoro/stats")
    def pomodoro_stats(
        start_date: str = "",
        end_date: str = "",
        days: int = 7,
        user: dict = Depends(require_user),
    ) -> dict:
        stats = service.get_pomodoro_stats(
            user["id"],
            start_date=start_date or None,
            end_date=end_date or None,
            days=days,
        )
        return {"ok": True, **stats}
