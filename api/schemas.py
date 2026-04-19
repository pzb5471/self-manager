from __future__ import annotations

from pydantic import BaseModel, Field


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
