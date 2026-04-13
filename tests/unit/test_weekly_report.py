import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from main import create_app
from service import TaskService


pytestmark = pytest.mark.unit


REPORT_END_DATE = "2026-04-13"


@pytest.fixture
def weekly_service():
    db_path = f"file:weekly_service_{uuid4().hex}?mode=memory&cache=shared"
    service = TaskService(db_path=db_path)
    user = service.register_user("weekly_user", "secure123")
    try:
        yield service, user["id"]
    finally:
        service.close()


@pytest.fixture
def weekly_api_ctx():
    db_path = f"file:weekly_api_{uuid4().hex}?mode=memory&cache=shared"
    app = create_app(db_path=db_path)
    client = TestClient(app)
    try:
        yield {"client": client, "db_path": db_path}
    finally:
        client.close()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register_and_login(client: TestClient, username: str = "weekly_api_user") -> str:
    register_resp = client.post("/api/auth/register", json={"username": username, "password": "secure123"})
    assert register_resp.status_code == 200
    login_resp = client.post("/api/auth/login", json={"username": username, "password": "secure123"})
    assert login_resp.status_code == 200
    return login_resp.json()["token"]


def insert_task(service: TaskService, user_id: int, *, title: str, category: str, quadrant: int, created_at: str, completed: bool) -> None:
    conn = service._get_connection()
    cursor = conn.cursor()
    try:
        category_id = service._ensure_category_exists(cursor, user_id, category)
        cursor.execute(
            """
            INSERT INTO tasks (
                user_id, category_id, title, description, category, quadrant, completed,
                due_at, recurrence_rule, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                category_id,
                title,
                "",
                category,
                quadrant,
                1 if completed else 0,
                None,
                "none",
                created_at,
                created_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def seed_weekly_data(service: TaskService, user_id: int) -> None:
    insert_task(
        service,
        user_id,
        title="完成接口设计",
        category="工作",
        quadrant=1,
        created_at="2026-04-07 09:00:00",
        completed=True,
    )
    insert_task(
        service,
        user_id,
        title="整理每周复盘",
        category="学习",
        quadrant=2,
        created_at="2026-04-12 12:00:00",
        completed=False,
    )

    for date in ("2026-04-07", "2026-04-08"):
        for period in ("morning", "noon", "evening"):
            service.record_workstation_checkin(user_id, period, date)

    service.record_phone_focus(user_id, 30, "deep work", "2026-04-07 14:00")
    service.record_phone_focus(user_id, 45, "stay focused", "2026-04-10 20:00")

    service.record_pomodoro_session(user_id, "work", 25, True, "2026-04-07", "focus block")
    service.record_pomodoro_session(user_id, "short_break", 5, True, "2026-04-07", "short break")
    service.record_pomodoro_session(user_id, "work", 35, True, "2026-04-10", "focus block")


def test_weekly_report_service_aggregates_and_fills_dates(weekly_service):
    service, user_id = weekly_service
    seed_weekly_data(service, user_id)

    report = service.get_weekly_report(user_id, end_date=REPORT_END_DATE, days=7)

    assert report["range"] == {
        "start_date": "2026-04-07",
        "end_date": REPORT_END_DATE,
        "days": 7,
        "label": "2026-04-07 ~ 2026-04-13",
    }
    assert report["summary"]["tasks_created"] == 2
    assert report["summary"]["tasks_completed"] == 1
    assert report["summary"]["completion_rate"] == 50
    assert report["summary"]["focus_minutes"] == 60
    assert report["summary"]["focus_sessions"] == 2
    assert report["summary"]["checkin_days"] == 2
    assert report["summary"]["full_checkin_days"] == 2
    assert report["summary"]["phone_focus_minutes"] == 75
    assert report["summary"]["phone_focus_sessions"] == 2

    assert report["tasks"]["by_quadrant"] == {1: 1, 2: 1, 3: 0, 4: 0}
    assert report["tasks"]["by_category"]["工作"] == 1
    assert report["tasks"]["by_category"]["学习"] == 1
    assert report["tasks"]["top_completed_titles"] == ["完成接口设计"]

    pomodoro_by_date = {item["date"]: item for item in report["pomodoro"]["by_date"]}
    assert len(pomodoro_by_date) == 7
    assert pomodoro_by_date["2026-04-07"]["focus_minutes"] == 25
    assert pomodoro_by_date["2026-04-08"]["focus_minutes"] == 0
    assert pomodoro_by_date["2026-04-10"]["focus_minutes"] == 35

    checkins_by_date = {item["date"]: item for item in report["habits"]["checkins_by_date"]}
    phone_by_date = {item["date"]: item for item in report["habits"]["phone_focus_by_date"]}
    assert len(checkins_by_date) == 7
    assert checkins_by_date["2026-04-07"]["period_count"] == 3
    assert checkins_by_date["2026-04-09"]["period_count"] == 0
    assert phone_by_date["2026-04-07"]["minutes"] == 30
    assert phone_by_date["2026-04-08"]["minutes"] == 0
    assert phone_by_date["2026-04-10"]["minutes"] == 45

    assert set(report["insights"]) == {"highlight", "focus", "habit", "improvement"}
    assert all(isinstance(value, str) and value for value in report["insights"].values())


def test_weekly_report_api_requires_auth_and_validates_params(weekly_api_ctx):
    client = weekly_api_ctx["client"]

    unauthorized = client.get("/api/reports/weekly")
    assert unauthorized.status_code == 401

    token = register_and_login(client)
    headers = auth_headers(token)

    invalid_days = client.get("/api/reports/weekly?days=32", headers=headers)
    assert invalid_days.status_code == 422

    invalid_date = client.get("/api/reports/weekly?end_date=2026-13-40", headers=headers)
    assert invalid_date.status_code == 400


def test_weekly_report_api_returns_report_payload(weekly_api_ctx):
    client = weekly_api_ctx["client"]
    token = register_and_login(client, username="weekly_api_user_2")
    headers = auth_headers(token)

    seeded_service = TaskService(db_path=weekly_api_ctx["db_path"])
    try:
        conn = seeded_service._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username = ?", ("weekly_api_user_2",))
            row = cursor.fetchone()
            assert row is not None
            seed_weekly_data(seeded_service, row["id"])
        finally:
            conn.close()
    finally:
        seeded_service.close()

    response = client.get("/api/reports/weekly?end_date=2026-04-13&days=7", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["report"]["range"]["days"] == 7
    assert "summary" in body["report"]
