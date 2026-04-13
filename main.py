from __future__ import annotations

import os
from urllib.parse import quote
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, Response
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
    due_at: str = ""
    recurrence_rule: str = "none"


class CategoryPayload(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    color: str = Field(pattern=r"^#[0-9a-fA-F]{6}$")


class TaskStatusPayload(BaseModel):
    completed: bool


class TaskImportPayload(BaseModel):
    csv_text: str = Field(min_length=1)


class PomodoroSessionPayload(BaseModel):
    session_type: str
    duration_minutes: int = Field(gt=0, le=480)
    completed: bool = True
    session_date: str = ""
    note: str = Field(default="", max_length=120)


class WorkstationCheckinPayload(BaseModel):
    period: str
    checkin_date: str = ""


class PhoneFocusPayload(BaseModel):
    duration_minutes: int = Field(gt=0, le=1440)
    note: str = Field(default="", max_length=120)
    resisted_at: str = ""


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
                due_at=payload.due_at,
                recurrence_rule=payload.recurrence_rule,
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
                due_at=payload.due_at,
                recurrence_rule=payload.recurrence_rule,
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

    @app.get("/api/tasks/export")
    def export_tasks(user: dict = Depends(require_user)) -> Response:
        csv_text = service.export_tasks_csv(int(user["id"]))
        filename = quote(f"self-manager-tasks-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.csv")
        headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
        }
        return Response(content=csv_text, media_type="text/csv; charset=utf-8", headers=headers)

    @app.post("/api/tasks/import")
    def import_tasks(payload: TaskImportPayload, user: dict = Depends(require_user)) -> dict:
        try:
            result = service.import_tasks_csv(int(user["id"]), payload.csv_text)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, **result}

    @app.post("/api/pomodoro/sessions")
    def create_pomodoro_session(payload: PomodoroSessionPayload, user: dict = Depends(require_user)) -> dict:
        try:
            item = service.record_pomodoro_session(
                int(user["id"]),
                session_type=payload.session_type,
                duration_minutes=payload.duration_minutes,
                completed=payload.completed,
                session_date=payload.session_date or None,
                note=payload.note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
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
        try:
            items = service.list_pomodoro_sessions(
                int(user["id"]),
                start_date=start_date or None,
                end_date=end_date or None,
                session_type=session_type or None,
                completed=completed,
                days=days,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "items": items}

    @app.get("/api/pomodoro/stats")
    def pomodoro_stats(
        start_date: str = "",
        end_date: str = "",
        days: int = 7,
        user: dict = Depends(require_user),
    ) -> dict:
        try:
            stats = service.get_pomodoro_stats(
                int(user["id"]),
                start_date=start_date or None,
                end_date=end_date or None,
                days=days,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, **stats}

    @app.get("/api/habits/dashboard")
    def habit_dashboard(today: str = "", user: dict = Depends(require_user)) -> dict:
        try:
            data = service.get_habit_dashboard(int(user["id"]), today=today or None)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, **data}

    @app.get("/api/habits/checkins")
    def list_habit_checkins(days: int = 14, end_date: str = "", user: dict = Depends(require_user)) -> dict:
        try:
            items = service.list_workstation_checkins(int(user["id"]), days=days, end_date=end_date or None)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "items": items}

    @app.post("/api/habits/checkins")
    def create_habit_checkin(payload: WorkstationCheckinPayload, user: dict = Depends(require_user)) -> dict:
        try:
            item = service.record_workstation_checkin(
                int(user["id"]),
                period=payload.period,
                checkin_date=payload.checkin_date or None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "item": item}

    @app.get("/api/habits/phone-focus")
    def list_phone_focus(days: int = 14, end_date: str = "", user: dict = Depends(require_user)) -> dict:
        try:
            items = service.list_phone_focus_records(int(user["id"]), days=days, end_date=end_date or None)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "items": items}

    @app.post("/api/habits/phone-focus")
    def create_phone_focus(payload: PhoneFocusPayload, user: dict = Depends(require_user)) -> dict:
        try:
            item = service.record_phone_focus(
                int(user["id"]),
                duration_minutes=payload.duration_minutes,
                note=payload.note,
                resisted_at=payload.resisted_at or None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "item": item}

    @app.get("/api/schedule/overview")
    def schedule_overview(user: dict = Depends(require_user)) -> dict:
        overview = service.get_schedule_overview(int(user["id"]))
        return {"ok": True, **overview}

    @app.get("/api/schedule/calendar")
    def schedule_calendar(
        start_date: str = "",
        days: int = 35,
        user: dict = Depends(require_user),
    ) -> dict:
        try:
            calendar = service.get_calendar_view(int(user["id"]), start_date=start_date or None, days=days)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, **calendar}

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

    @app.get("/api/reports/weekly")
    def weekly_report(
        end_date: str = "",
        days: int = Query(default=7, ge=1, le=31),
        user: dict = Depends(require_user),
    ) -> dict:
        try:
            report = service.get_weekly_report(int(user["id"]), end_date=end_date or None, days=days)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, "report": report}

    return app


app = create_app(db_path=os.getenv("SELF_MANAGER_DB_PATH", "productivity_manager.db"))
