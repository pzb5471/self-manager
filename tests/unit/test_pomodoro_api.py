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
def pomodoro_api_ctx():
    db_path = f"file:pomodoro_api_{uuid4().hex}?mode=memory&cache=shared"
    app = create_app(db_path=db_path)
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def login(client: TestClient, username: str = "pomodoro_api_user") -> str:
    assert client.post("/api/auth/register", json={"username": username, "password": "secure123"}).status_code == 200
    resp = client.post("/api/auth/login", json={"username": username, "password": "secure123"})
    assert resp.status_code == 200
    return resp.json()["token"]


def test_pomodoro_session_and_stats_api(pomodoro_api_ctx):
    client = pomodoro_api_ctx
    token = login(client)
    headers = auth_headers(token)

    created = client.post(
        "/api/pomodoro/sessions",
        headers=headers,
        json={"session_type": "work", "duration_minutes": 25, "completed": True, "session_date": "2026-04-10"},
    )
    assert created.status_code == 200
    assert created.json()["item"]["session_type"] == "work"

    client.post(
        "/api/pomodoro/sessions",
        headers=headers,
        json={"session_type": "short_break", "duration_minutes": 5, "completed": True, "session_date": "2026-04-10"},
    )

    listed = client.get("/api/pomodoro/sessions?start_date=2026-04-10&end_date=2026-04-10", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()["items"]) == 2

    stats = client.get("/api/pomodoro/stats?start_date=2026-04-10&end_date=2026-04-10", headers=headers)
    assert stats.status_code == 200
    body = stats.json()
    assert body["summary"]["focus_sessions"] == 1
    assert body["summary"]["focus_minutes"] == 25


def test_pomodoro_api_validation_errors(pomodoro_api_ctx):
    client = pomodoro_api_ctx
    token = login(client, username="pomodoro_api_user_2")
    headers = auth_headers(token)

    invalid_type = client.post(
        "/api/pomodoro/sessions",
        headers=headers,
        json={"session_type": "nap", "duration_minutes": 20},
    )
    assert invalid_type.status_code == 400

