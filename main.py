from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from service import TaskService


class RegisterPayload(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)


class LoginPayload(BaseModel):
    username: str
    password: str
    remember_me: bool = False


class TaskPayload(BaseModel):
    title: str
    description: str = ""
    category: str
    quadrant: int


def create_app(db_path: str = "productivity_manager.db") -> FastAPI:
    app = FastAPI(title="Self Manager API", version="3.0")
    service = TaskService(db_path=db_path)

    frontend_dir = Path(__file__).resolve().parent / "frontend"
    app.mount("/assets", StaticFiles(directory=str(frontend_dir)), name="assets")

    def parse_bearer_token(authorization: Optional[str]) -> str:
        if not authorization:
            raise HTTPException(status_code=401, detail="缺少鉴权信息")

        parts = authorization.strip().split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
            raise HTTPException(status_code=401, detail="鉴权格式无效")
        return parts[1]

    def require_user(authorization: Optional[str] = Header(default=None)) -> dict:
        token = parse_bearer_token(authorization)
        user = service.verify_token(token)
        if user is None:
            raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
        return user

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(frontend_dir / "index.html")

    @app.post("/api/auth/register")
    def register(payload: RegisterPayload) -> dict:
        try:
            user = service.register_user(payload.username, payload.password)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "user": user}

    @app.post("/api/auth/login")
    def login(payload: LoginPayload) -> dict:
        result = service.login_user(payload.username, payload.password, payload.remember_me)
        if result is None:
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        return {"ok": True, **result}

    @app.post("/api/auth/logout")
    def logout(authorization: Optional[str] = Header(default=None)) -> dict:
        token = parse_bearer_token(authorization)
        service.logout(token)
        return {"ok": True}

    @app.get("/api/auth/me")
    def me(user: dict = Depends(require_user)) -> dict:
        return {"ok": True, "user": user}

    @app.get("/api/meta/categories")
    def categories(user: dict = Depends(require_user)) -> dict:
        _ = user
        return {"ok": True, "items": service.get_categories()}

    @app.get("/api/tasks")
    def list_tasks(
        keyword: str = "",
        category: str = "全部",
        quadrant: str = "全部",
        sort: str = "created_desc",
        user: dict = Depends(require_user),
    ) -> dict:
        user_id = int(user["id"])

        if keyword.strip():
            tasks = service.search_tasks(user_id, keyword.strip())
        else:
            tasks = service.get_all_tasks(user_id)

        if category != "全部":
            tasks = [item for item in tasks if item["category"] == category]
        if quadrant != "全部":
            try:
                q = int(quadrant)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="象限参数无效") from exc
            tasks = [item for item in tasks if item["quadrant"] == q]

        if not keyword.strip() and category == "全部" and quadrant == "全部":
            tasks = service.get_sorted_tasks(user_id, sort)
        else:
            sort_field = "created_at" if "created" in sort else "updated_at"
            reverse = "desc" in sort
            tasks = sorted(tasks, key=lambda t: (t[sort_field], t["id"]), reverse=reverse)

        return {"ok": True, "items": tasks}

    @app.post("/api/tasks")
    def create_task(payload: TaskPayload, user: dict = Depends(require_user)) -> dict:
        try:
            task = service.add_task(
                user_id=int(user["id"]),
                title=payload.title,
                description=payload.description,
                category=payload.category,
                quadrant=payload.quadrant,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "item": task}

    @app.put("/api/tasks/{task_id}")
    def update_task(task_id: int, payload: TaskPayload, user: dict = Depends(require_user)) -> dict:
        try:
            updated = service.update_task(
                task_id=task_id,
                user_id=int(user["id"]),
                title=payload.title,
                description=payload.description,
                category=payload.category,
                quadrant=payload.quadrant,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if not updated:
            raise HTTPException(status_code=404, detail="任务不存在")

        task = service.get_task_by_id(task_id, int(user["id"]))
        return {"ok": True, "item": task}

    @app.delete("/api/tasks/{task_id}")
    def delete_task(task_id: int, user: dict = Depends(require_user)) -> dict:
        deleted = service.delete_task(task_id, int(user["id"]))
        if not deleted:
            raise HTTPException(status_code=404, detail="任务不存在")
        return {"ok": True}

    @app.get("/api/stats/dashboard")
    def dashboard_stats(user: dict = Depends(require_user)) -> dict:
        user_id = int(user["id"])
        tasks = service.get_all_tasks(user_id)
        stats = service.get_statistics(user_id)

        today = datetime.utcnow().date()
        start = today - timedelta(days=13)
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
        for offset in range(14):
            current = start + timedelta(days=offset)
            iso = current.isoformat()
            trend.append({"date": iso, "count": trend_map.get(iso, 0)})

        return {
            "ok": True,
            "stats": stats,
            "trend": trend,
        }

    return app


app = create_app(db_path=os.getenv("SELF_MANAGER_DB_PATH", "productivity_manager.db"))
