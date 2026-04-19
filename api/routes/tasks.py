from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import Response

from api.schemas import TaskImportPayload, TaskPayload, TaskStatusPayload
from service import TaskService


def register_task_routes(app: FastAPI, service: TaskService, require_user: Callable[..., dict]) -> None:
    @app.get("/api/tasks")
    def list_tasks(
        keyword: str = "",
        category: str = "全部",
        quadrant: str = "全部",
        sort: str = "created_desc",
        status: str = "pending",
        user: dict = Depends(require_user),
    ) -> dict:
        quadrant_int: Optional[int] = None
        if quadrant != "全部":
            try:
                quadrant_int = int(quadrant)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="象限参数无效") from exc

        tasks = service.list_tasks(
            user_id=user["id"],
            keyword=keyword.strip() or None,
            category=category if category != "全部" else None,
            quadrant=quadrant_int,
            sort_by=sort,
            status=status,
        )
        return {"ok": True, "items": tasks}

    @app.post("/api/tasks")
    def create_task(payload: TaskPayload, user: dict = Depends(require_user)) -> dict:
        task = service.add_task(
            user_id=user["id"],
            title=payload.title,
            description=payload.description,
            category=payload.category,
            quadrant=payload.quadrant,
            due_at=payload.due_at,
            recurrence_rule=payload.recurrence_rule,
        )
        return {"ok": True, "item": task}

    @app.put("/api/tasks/{task_id}")
    def update_task(task_id: int, payload: TaskPayload, user: dict = Depends(require_user)) -> dict:
        task = service.update_task(
            task_id=task_id,
            user_id=user["id"],
            title=payload.title,
            description=payload.description,
            category=payload.category,
            quadrant=payload.quadrant,
            due_at=payload.due_at,
            recurrence_rule=payload.recurrence_rule,
        )
        if task is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        return {"ok": True, "item": task}

    @app.delete("/api/tasks/{task_id}")
    def delete_task(task_id: int, user: dict = Depends(require_user)) -> dict:
        deleted = service.delete_task(task_id, user["id"])
        if not deleted:
            raise HTTPException(status_code=404, detail="任务不存在")
        return {"ok": True}

    @app.patch("/api/tasks/{task_id}/status")
    def update_task_status(task_id: int, payload: TaskStatusPayload, user: dict = Depends(require_user)) -> dict:
        task = service.set_task_completed(task_id, user["id"], payload.completed)
        if task is None:
            raise HTTPException(status_code=404, detail="任务不存在")
        return {"ok": True, "item": task}

    @app.get("/api/tasks/export")
    def export_tasks(user: dict = Depends(require_user)) -> Response:
        csv_text = service.export_tasks_csv(user["id"])
        filename = quote(f"self-manager-tasks-{datetime.now(timezone.utc).replace(tzinfo=None).strftime('%Y%m%d-%H%M%S')}.csv")
        headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
        }
        return Response(content=csv_text, media_type="text/csv; charset=utf-8", headers=headers)

    @app.post("/api/tasks/import")
    def import_tasks(payload: TaskImportPayload, user: dict = Depends(require_user)) -> dict:
        result = service.import_tasks_csv(user["id"], payload.csv_text)
        return {"ok": True, **result}
