from __future__ import annotations

from typing import Callable, Optional

from fastapi import Depends, FastAPI, Header, HTTPException

from api.deps import parse_bearer_token
from api.schemas import LoginPayload, RegisterPayload
from service import TaskService


def register_auth_routes(app: FastAPI, service: TaskService, require_user: Callable[..., dict]) -> None:
    @app.post("/api/auth/register")
    def register(payload: RegisterPayload) -> dict:
        user = service.register_user(payload.username, payload.password)
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
