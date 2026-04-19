from __future__ import annotations

from typing import Callable

from fastapi import Depends, FastAPI, HTTPException

from api.schemas import CategoryPayload
from service import TaskService


def register_category_routes(app: FastAPI, service: TaskService, require_user: Callable[..., dict]) -> None:
    @app.get("/api/categories")
    def list_categories(user: dict = Depends(require_user)) -> dict:
        return {"ok": True, "items": service.list_categories(user["id"])}

    @app.post("/api/categories")
    def create_category(payload: CategoryPayload, user: dict = Depends(require_user)) -> dict:
        category = service.create_category(user["id"], payload.name, payload.color)
        return {"ok": True, "item": category}

    @app.put("/api/categories/{category_id}")
    def update_category(category_id: int, payload: CategoryPayload, user: dict = Depends(require_user)) -> dict:
        category = service.update_category(category_id, user["id"], payload.name, payload.color)
        if category is None:
            raise HTTPException(status_code=404, detail="分类不存在")
        return {"ok": True, "item": category}

    @app.delete("/api/categories/{category_id}")
    def delete_category(category_id: int, user: dict = Depends(require_user)) -> dict:
        deleted = service.delete_category(category_id, user["id"])
        if not deleted:
            raise HTTPException(status_code=404, detail="分类不存在")
        return {"ok": True}
