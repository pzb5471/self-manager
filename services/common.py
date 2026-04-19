from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Generator, List, Optional


@dataclass(frozen=True)
class ServiceContext:
    get_connection: Callable[[], sqlite3.Connection]
    now_str: Callable[[], str]
    local_now_str: Callable[[], str]
    mask_token: Callable[[str], str]
    default_categories: List[Dict[str, str]]
    password_iterations: int
    token_ttl_hours: int
    token_ttl_remember_hours: int

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = self.get_connection()
        try:
            yield conn
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Auth / crypto helpers
# ---------------------------------------------------------------------------

def validate_username(username: str) -> str:
    username_norm = (username or "").strip()
    if len(username_norm) < 3:
        raise ValueError("用户名至少3个字符")
    if len(username_norm) > 32:
        raise ValueError("用户名不能超过32个字符")
    return username_norm


def validate_password(password: str) -> None:
    if password is None or len(password) < 6:
        raise ValueError("密码至少6个字符")
    if len(password) > 128:
        raise ValueError("密码长度不能超过128个字符")


def hash_password(password: str, salt_hex: str, iterations: int) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        iterations,
    )
    return digest.hex()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Category helpers
# ---------------------------------------------------------------------------

def validate_category_name(name: str) -> str:
    name_checked = (name or "").strip()
    if len(name_checked) < 1:
        raise ValueError("分类名称不能为空")
    if len(name_checked) > 20:
        raise ValueError("分类名称不能超过20个字符")
    return name_checked


def validate_category_color(color: str) -> str:
    color_checked = (color or "").strip()
    if len(color_checked) != 7 or not color_checked.startswith("#"):
        raise ValueError("分类颜色必须是 #RRGGBB 格式")
    hex_part = color_checked[1:]
    if any(ch not in "0123456789abcdefABCDEF" for ch in hex_part):
        raise ValueError("分类颜色必须是 #RRGGBB 格式")
    return color_checked.upper()


def row_to_category(row: sqlite3.Row) -> Dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "color": row["color"],
        "created_at": row["created_at"],
    }


def default_color_for_name(name: str) -> str:
    palette = ["#006D77", "#0F766E", "#C2410C", "#2563EB", "#B45309", "#BE123C", "#4338CA", "#0F766E"]
    index = abs(hash(name)) % len(palette)
    return palette[index]


# ---------------------------------------------------------------------------
# Shared validators (pure functions, no class state)
# ---------------------------------------------------------------------------

def validate_user_id(user_id: int) -> int:
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("用户未登录或用户ID无效")
    return user_id


def validate_positive_int(value: int, message: str) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ValueError(message)
    return value


def validate_title(title: str) -> str:
    title_trimmed = (title or "").strip()
    if not title_trimmed:
        raise ValueError("任务标题不能为空")
    if len(title_trimmed) < 2:
        raise ValueError("任务标题太短（至少2个字符）")
    return title_trimmed


def validate_quadrant(quadrant: int) -> int:
    if quadrant not in (1, 2, 3, 4):
        raise ValueError("象限必须是 1-4 的整数")
    return quadrant


def validate_pomodoro_type(session_type: str, valid_types: tuple[str, ...] = ("work", "short_break", "long_break")) -> str:
    checked = (session_type or "").strip().lower()
    if checked not in valid_types:
        raise ValueError("session_type must be work, short_break, or long_break")
    return checked


def validate_pomodoro_duration(duration_minutes: int) -> int:
    if not isinstance(duration_minutes, int) or duration_minutes <= 0:
        raise ValueError("duration_minutes must be a positive integer")
    if duration_minutes > 480:
        raise ValueError("duration_minutes must not exceed 480")
    return duration_minutes


def validate_checkin_period(period: str, valid_periods: tuple[str, ...] = ("morning", "noon", "evening")) -> str:
    checked = (period or "").strip().lower()
    if checked not in valid_periods:
        raise ValueError("打卡时段必须是 morning/noon/evening 之一")
    return checked


def validate_duration_minutes(value: int) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ValueError("克制玩手机时长必须是正整数分钟")
    if value > 24 * 60:
        raise ValueError("克制玩手机时长不能超过1440分钟")
    return value


def validate_recurrence_rule(value: str) -> str:
    rule = (value or "none").strip().lower()
    if rule not in {"none", "daily", "weekly", "monthly"}:
        raise ValueError("重复日程必须是 none/daily/weekly/monthly 之一")
    return rule


def status_to_completed(status: str, status_all: str = "all", status_pending: str = "pending", status_completed: str = "completed") -> Optional[int]:
    if status == status_all:
        return None
    if status == status_pending:
        return 0
    if status == status_completed:
        return 1
    raise ValueError("状态必须是 all/pending/completed 之一")


def bool_to_db(value: bool) -> int:
    return 1 if bool(value) else 0


# ---------------------------------------------------------------------------
# Date / time parsing helpers
# ---------------------------------------------------------------------------

def parse_due_at(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    normalized = raw.replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue
    return None


def normalize_due_at(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    parsed = parse_due_at(raw)
    if parsed is None:
        raise ValueError("截止日期时间格式无效")
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def format_delta_label(prefix: str, delta: timedelta) -> str:
    total_minutes = max(1, int(delta.total_seconds() // 60))
    days, remainder = divmod(total_minutes, 60 * 24)
    hours, minutes = divmod(remainder, 60)
    parts: List[str] = []
    if days:
        parts.append(f"{days}天")
    if hours:
        parts.append(f"{hours}小时")
    if minutes or not parts:
        parts.append(f"{minutes}分钟")
    return prefix + "".join(parts[:2])


def build_due_status(due_at: Optional[str], completed: bool) -> Dict[str, Optional[object]]:
    if not due_at:
        return {"due_at": None, "due_state": "none", "due_text": "未设置截止时间", "due_minutes": None}

    due_dt = parse_due_at(due_at)
    if due_dt is None:
        return {"due_at": due_at, "due_state": "invalid", "due_text": "截止时间无效", "due_minutes": None}

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    delta = due_dt - now
    due_minutes = int(delta.total_seconds() // 60)
    if completed:
        state = "completed"
        text = f"截止于 {due_dt.strftime('%Y-%m-%d %H:%M')}"
    elif delta.total_seconds() < 0:
        state = "overdue"
        text = format_delta_label("已逾期", now - due_dt)
    else:
        state = "upcoming"
        text = format_delta_label("剩余", delta)

    return {
        "due_at": due_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "due_state": state,
        "due_text": text,
        "due_minutes": due_minutes,
    }


# ---------------------------------------------------------------------------
# Row mappers
# ---------------------------------------------------------------------------

def row_to_checkin(row: sqlite3.Row) -> Dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "checkin_date": row["checkin_date"],
        "period": row["period"],
        "created_at": row["created_at"],
    }


def row_to_phone_focus(row: sqlite3.Row) -> Dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "duration_minutes": row["duration_minutes"],
        "note": row["note"] or "",
        "resisted_at": row["resisted_at"],
        "created_at": row["created_at"],
    }


def row_to_pomodoro_session(row: sqlite3.Row) -> Dict:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "session_date": row["session_date"],
        "session_type": row["session_type"],
        "duration_minutes": row["duration_minutes"],
        "completed": bool(row["completed"]),
        "note": row["note"] or "",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def row_to_task(row: sqlite3.Row) -> Dict:
    due_info = build_due_status(row["due_at"], bool(row["completed"]))
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "category_id": row["category_id"],
        "title": row["title"],
        "description": row["description"] or "",
        "category": row["category"],
        "category_color": row["category_color"],
        "quadrant": row["quadrant"],
        "completed": bool(row["completed"]),
        "due_at": due_info["due_at"],
        "due_state": due_info["due_state"],
        "due_text": due_info["due_text"],
        "due_minutes": due_info["due_minutes"],
        "recurrence_rule": row["recurrence_rule"] or "none",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


# ---------------------------------------------------------------------------
# Pomodoro aggregation helpers
# ---------------------------------------------------------------------------

def empty_pomodoro_day() -> Dict[str, object]:
    return {
        "total_count": 0,
        "total_completed": 0,
        "focus_count": 0,
        "focus_minutes": 0,
        "work": {"count": 0, "completed_count": 0, "minutes": 0, "completed_minutes": 0},
        "short_break": {"count": 0, "completed_count": 0, "minutes": 0, "completed_minutes": 0},
        "long_break": {"count": 0, "completed_count": 0, "minutes": 0, "completed_minutes": 0},
    }


def accumulate_pomodoro_bucket(bucket: Dict[str, object], session: Dict) -> None:
    session_type = session["session_type"]
    session_bucket = bucket[session_type]
    session_bucket["count"] += 1
    session_bucket["minutes"] += int(session["duration_minutes"])
    if session["completed"]:
        session_bucket["completed_count"] += 1
        session_bucket["completed_minutes"] += int(session["duration_minutes"])
        bucket["total_completed"] += 1
        if session_type == "work":
            bucket["focus_count"] += 1
            bucket["focus_minutes"] += int(session["duration_minutes"])
    bucket["total_count"] += 1


# ---------------------------------------------------------------------------
# Task sorting / grouping helpers
# ---------------------------------------------------------------------------

def task_due_sort_key(task: Dict) -> tuple[int, str, int]:
    return (0 if task.get("due_at") else 1, task.get("due_at") or "", int(task["id"]))
