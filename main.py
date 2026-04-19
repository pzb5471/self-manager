from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from api.deps import build_require_user
from api.routes.auth import register_auth_routes
from api.routes.categories import register_category_routes
from api.routes.habits import register_habit_routes
from api.routes.pomodoro import register_pomodoro_routes
from api.routes.reports import register_report_routes
from api.routes.schedule import register_schedule_routes
from api.routes.stats import register_stats_routes
from api.routes.tasks import register_task_routes
from logger_config import setup_logging
from service import TaskService


def create_app(db_path: str = "productivity_manager.db") -> FastAPI:
    setup_logging()
    app = FastAPI(title="Self Manager API", version="3.0")

    @app.exception_handler(ValueError)
    async def value_error_handler(request, exc):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    service = TaskService(db_path=db_path)
    logger.info("应用初始化完成，数据库路径: {}", db_path)

    frontend_dir = Path(__file__).resolve().parent / "frontend"
    app.mount("/assets", StaticFiles(directory=str(frontend_dir)), name="assets")
    require_user = build_require_user(service)

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(frontend_dir / "index.html")

    register_auth_routes(app, service, require_user)
    register_category_routes(app, service, require_user)
    register_task_routes(app, service, require_user)
    register_pomodoro_routes(app, service, require_user)
    register_habit_routes(app, service, require_user)
    register_schedule_routes(app, service, require_user)
    register_stats_routes(app, service, require_user)
    register_report_routes(app, service, require_user)

    return app


app = create_app(db_path=os.getenv("SELF_MANAGER_DB_PATH", "productivity_manager.db"))
