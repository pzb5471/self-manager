from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel, Field

from logger_config import setup_logging
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


class CategoryPayload(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class TaskStatusPayload(BaseModel):
    completed: bool


def create_app(db_path: str = "productivity_manager.db") -> FastAPI:
    setup_logging()
    app = FastAPI(title="Self Manager API", version="3.0")
    service = TaskService(db_path=db_path)
    logger.info("应用初始化完成，数据库路径: {}", db_path)

    frontend_dir = Path(__file__).resolve().parent / "frontend"
    app.mount("/assets", StaticFiles(directory=str(frontend_dir)), name="assets")

    def parse_bearer_token(authorization: Optional[str]) -> str:
        if not authorization:
            logger.warning("请求缺少 Authorization 头")
            raise HTTPException(status_code=401, detail="缺少鉴权信息")

        parts = authorization.strip().split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
            logger.warning("请求携带了无效的 Bearer Token 格式")
            raise HTTPException(status_code=401, detail="鉴权格式无效")
        return parts[1]

    def require_user(authorization: Optional[str] = Header(default=None)) -> dict:
        token = parse_bearer_token(authorization)
        user = service.verify_token(token)
        if user is None:
            logger.warning("用户令牌校验失败")
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
        return {"ok": True, "items": service.list_categories(int(user["id"]))}

    @app.get("/api/categories")
    def list_categories(user: dict = Depends(require_user)) -> dict:
        return {"ok": True, "items": service.list_categories(int(user["id"]))}

    @app.post("/api/categories")
    def create_category(payload: CategoryPayload, user: dict = Depends(require_user)) -> dict:
        try:
            category = service.create_category(int(user["id"]), payload.name, payload.color)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "item": category}

    @app.put("/api/categories/{category_id}")
    def update_category(category_id: int, payload: CategoryPayload, user: dict = Depends(require_user)) -> dict:
        try:
            category = service.update_category(category_id, int(user["id"]), payload.name, payload.color)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if category is None:
            raise HTTPException(status_code=404, detail="分类不存在")
        return {"ok": True, "item": category}

    @app.delete("/api/categories/{category_id}")
    def delete_category(category_id: int, user: dict = Depends(require_user)) -> dict:
        try:
            deleted = service.delete_category(category_id, int(user["id"]))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="分类不存在")
        return {"ok": True}

    @app.get("/api/tasks")
    def list_tasks(
        keyword: str = "",
        category: str = "全部",
        quadrant: str = "全部",
        sort: str = "created_desc",
        status: str = "pending",
        user: dict = Depends(require_user),
    ) -> dict:
        user_id = int(user["id"])
        try:
            if keyword.strip():
                tasks = service.search_tasks(user_id, keyword.strip(), status=status)
            else:
                tasks = service.get_all_tasks(user_id, status=status)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if category != "全部":
            tasks = [item for item in tasks if item["category"] == category]
        if quadrant != "全部":
            try:
                q = int(quadrant)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="象限参数无效") from exc
            tasks = [item for item in tasks if item["quadrant"] == q]

        if not keyword.strip() and category == "全部" and quadrant == "全部":
            tasks = service.get_sorted_tasks(user_id, sort, status=status)
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

    @app.patch("/api/tasks/{task_id}/status")
    def update_task_status(task_id: int, payload: TaskStatusPayload, user: dict = Depends(require_user)) -> dict:
        updated = service.set_task_completed(task_id, int(user["id"]), payload.completed)
        if not updated:
            raise HTTPException(status_code=404, detail="任务不存在")
        task = service.get_task_by_id(task_id, int(user["id"]))
        return {"ok": True, "item": task}

    @app.get("/api/stats/dashboard")
    def dashboard_stats(user: dict = Depends(require_user)) -> dict:
        user_id = int(user["id"])
        tasks = service.get_all_tasks(user_id, status=service.STATUS_ALL)
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
