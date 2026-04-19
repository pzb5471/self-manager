from __future__ import annotations

from typing import Callable, Optional

from fastapi import Header, HTTPException
from loguru import logger

from service import TaskService


def parse_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        logger.warning("请求缺少 Authorization 头")
        raise HTTPException(status_code=401, detail="缺少鉴权信息")

    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
        logger.warning("请求携带了无效的 Bearer Token 格式")
        raise HTTPException(status_code=401, detail="鉴权格式无效")
    return parts[1]


def build_require_user(service: TaskService) -> Callable[[Optional[str]], dict]:
    def require_user(authorization: Optional[str] = Header(default=None)) -> dict:
        token = parse_bearer_token(authorization)
        user = service.verify_token(token)
        if user is None:
            logger.warning("用户令牌校验失败")
            raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
        return user

    return require_user
