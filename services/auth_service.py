from __future__ import annotations

import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from loguru import logger

from services.category_service import CategoryService
from services.common import ServiceContext, hash_password, hash_token, validate_password, validate_username


class AuthService:
    def __init__(self, context: ServiceContext, category_service: CategoryService):
        self.context = context
        self.category_service = category_service

    def register_user(self, username: str, password: str) -> Dict:
        username_norm = validate_username(username)
        validate_password(password)
        logger.info("准备注册用户: {}", username_norm)

        salt = os.urandom(16).hex()
        password_hash_value = hash_password(password, salt, self.context.password_iterations)

        conn = self.context.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO users (username, password_hash, password_salt)
                VALUES (?, ?, ?)
                """,
                (username_norm, password_hash_value, salt),
            )
            user_id = int(cursor.lastrowid)
            self.category_service.seed_default_categories(cursor, user_id)
            conn.commit()
        except sqlite3.IntegrityError as exc:
            logger.warning("用户注册失败，用户名已存在: {}", username_norm)
            conn.close()
            raise ValueError("用户名已存在") from exc
        except sqlite3.Error:
            logger.exception("用户注册数据库写入失败: {}", username_norm)
            conn.close()
            raise

        cursor.execute("SELECT id, username, created_at FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        logger.info("用户注册成功: user_id={}, username={}", user_id, username_norm)
        return {"id": row["id"], "username": row["username"], "created_at": row["created_at"]}

    def login_user(self, username: str, password: str, remember_me: bool = False) -> Optional[Dict]:
        username_norm = username.strip()
        if not username_norm or not password:
            logger.warning("用户登录失败，请求参数不完整")
            return None

        conn = self.context.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, username, password_hash, password_salt, created_at
                FROM users
                WHERE username = ?
                """,
                (username_norm,),
            )
            user = cursor.fetchone()
            if not user:
                logger.warning("用户登录失败，用户名不存在: {}", username_norm)
                return None

            expected_hash = hash_password(password, user["password_salt"], self.context.password_iterations)
            if not hmac.compare_digest(expected_hash, user["password_hash"]):
                logger.warning("用户登录失败，密码校验不通过: {}", username_norm)
                return None

            token = secrets.token_urlsafe(32)
            token_hash_value = hash_token(token)
            token_placeholder = secrets.token_urlsafe(16)
            ttl_hours = self.context.token_ttl_remember_hours if remember_me else self.context.token_ttl_hours
            expires_at = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=ttl_hours)).strftime("%Y-%m-%d %H:%M:%S")

            self.category_service.seed_default_categories(cursor, int(user["id"]))
            cursor.execute(
                """
                INSERT INTO auth_tokens (user_id, token, token_hash, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (user["id"], token_placeholder, token_hash_value, expires_at),
            )

            cursor.execute("DELETE FROM auth_tokens WHERE expires_at <= ?", (self.context.now_str(),))
            expired_count = cursor.rowcount
            conn.commit()
            logger.info(
                "用户登录成功: user_id={}, username={}, remember_me={}, 清理过期令牌={}条",
                user["id"],
                username_norm,
                remember_me,
                expired_count,
            )
            return {
                "token": token,
                "expires_at": expires_at,
                "user": {"id": user["id"], "username": user["username"], "created_at": user["created_at"]},
            }
        except sqlite3.Error:
            logger.exception("用户登录数据库操作失败: {}", username_norm)
            raise
        finally:
            conn.close()

    def verify_token(self, token: str) -> Optional[Dict]:
        if not token:
            logger.warning("令牌校验失败，token 为空")
            return None

        conn = self.context.get_connection()
        cursor = conn.cursor()
        token_hash_value = hash_token(token)
        try:
            cursor.execute(
                """
                SELECT u.id, u.username, u.created_at, t.expires_at
                FROM auth_tokens t
                JOIN users u ON u.id = t.user_id
                WHERE t.token_hash = ? AND t.expires_at > ?
                """,
                (token_hash_value, self.context.now_str()),
            )
            row = cursor.fetchone()
            if not row:
                logger.warning("令牌校验未通过: {}", self.context.mask_token(token))
                return None

            logger.info("令牌校验成功: user_id={}", row["id"])
            return {
                "id": row["id"],
                "username": row["username"],
                "created_at": row["created_at"],
                "token_expires_at": row["expires_at"],
            }
        except sqlite3.Error:
            logger.exception("令牌校验数据库查询失败: {}", self.context.mask_token(token))
            raise
        finally:
            conn.close()

    def logout(self, token: str) -> bool:
        if not token:
            logger.warning("退出登录失败，token 为空")
            return False

        conn = self.context.get_connection()
        cursor = conn.cursor()
        token_hash_value = hash_token(token)
        try:
            cursor.execute("DELETE FROM auth_tokens WHERE token_hash = ?", (token_hash_value,))
            conn.commit()
            removed = cursor.rowcount > 0
            if removed:
                logger.info("退出登录成功: {}", self.context.mask_token(token))
            else:
                logger.warning("退出登录未删除任何令牌: {}", self.context.mask_token(token))
            return removed
        except sqlite3.Error:
            logger.exception("退出登录数据库删除失败: {}", self.context.mask_token(token))
            raise
        finally:
            conn.close()
