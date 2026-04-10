import sys
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from main import create_app


pytestmark = pytest.mark.unit


@pytest.fixture
def habit_api_ctx():
    db_path = f"file:habit_api_{uuid4().hex}?mode=memory&cache=shared"
    app = create_app(db_path=db_path)
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def login(client: TestClient, username: str = "habit_api_user") -> str:
    assert client.post("/api/auth/register", json={"username": username, "password": "secure123"}).status_code == 200
    resp = client.post("/api/auth/login", json={"username": username, "password": "secure123"})
    assert resp.status_code == 200
    return resp.json()["token"]


def test_habit_checkin_and_dashboard_api(habit_api_ctx):
    client = habit_api_ctx
    token = login(client)
    headers = auth_headers(token)

    for period in ("morning", "noon", "evening"):
        resp = client.post("/api/habits/checkins", headers=headers, json={"period": period, "checkin_date": "2026-04-09"})
        assert resp.status_code == 200

    dashboard = client.get("/api/habits/dashboard?today=2026-04-09", headers=headers)
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["today"]["periods"] == {"morning": True, "noon": True, "evening": True}
    assert body["summary"]["full_day_count"] == 1


def test_phone_focus_api_and_validation(habit_api_ctx):
    client = habit_api_ctx
    token = login(client, username="habit_api_user_2")
    headers = auth_headers(token)

    created = client.post(
        "/api/habits/phone-focus",
        headers=headers,
        json={"duration_minutes": 35, "note": "no phone while coding", "resisted_at": "2026-04-09 15:30"},
    )
    assert created.status_code == 200
    assert created.json()["item"]["duration_minutes"] == 35

    listed = client.get("/api/habits/phone-focus?days=1&end_date=2026-04-09", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 1

    invalid = client.post("/api/habits/checkins", headers=headers, json={"period": "night"})
    assert invalid.status_code == 400

