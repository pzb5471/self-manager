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


@pytest.fixture
def pomodoro_service_ctx():
    db_path = f"file:pomodoro_regression_{uuid4().hex}?mode=memory&cache=shared"
    service = TaskService(db_path=db_path)
    user_a = service.register_user("reg_user_a", "secure123")
    user_b = service.register_user("reg_user_b", "secure123")
    try:
        yield service, user_a["id"], user_b["id"]
    finally:
        service.close()


@pytest.fixture
def pomodoro_api_client():
    db_path = f"file:pomodoro_api_reg_{uuid4().hex}?mode=memory&cache=shared"
    app = create_app(db_path=db_path)
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def login(client: TestClient, username: str) -> str:
    assert client.post("/api/auth/register", json={"username": username, "password": "secure123"}).status_code == 200
    resp = client.post("/api/auth/login", json={"username": username, "password": "secure123"})
    assert resp.status_code == 200
    return resp.json()["token"]


def test_list_pomodoro_sessions_supports_type_and_completed_filters(pomodoro_service_ctx):
    service, user_a_id, _ = pomodoro_service_ctx

    service.record_pomodoro_session(user_a_id, "work", 25, completed=True, session_date="2026-04-10")
    service.record_pomodoro_session(user_a_id, "work", 30, completed=False, session_date="2026-04-10")
    service.record_pomodoro_session(user_a_id, "short_break", 5, completed=True, session_date="2026-04-10")

    only_completed_work = service.list_pomodoro_sessions(
        user_a_id,
        start_date="2026-04-10",
        end_date="2026-04-10",
        session_type="work",
        completed=True,
    )
    only_unfinished_work = service.list_pomodoro_sessions(
        user_a_id,
        start_date="2026-04-10",
        end_date="2026-04-10",
        session_type="work",
        completed=False,
    )

    assert len(only_completed_work) == 1
    assert only_completed_work[0]["duration_minutes"] == 25
    assert len(only_unfinished_work) == 1
    assert only_unfinished_work[0]["completed"] is False


def test_pomodoro_sessions_are_isolated_per_user(pomodoro_service_ctx):
    service, user_a_id, user_b_id = pomodoro_service_ctx

    service.record_pomodoro_session(user_a_id, "work", 25, session_date="2026-04-10", note="user a")
    service.record_pomodoro_session(user_b_id, "work", 40, session_date="2026-04-10", note="user b")

    list_a = service.list_pomodoro_sessions(user_a_id, start_date="2026-04-10", end_date="2026-04-10")
    list_b = service.list_pomodoro_sessions(user_b_id, start_date="2026-04-10", end_date="2026-04-10")

    assert len(list_a) == 1
    assert len(list_b) == 1
    assert list_a[0]["note"] == "user a"
    assert list_b[0]["note"] == "user b"


def test_pomodoro_stats_default_days_window_works(pomodoro_service_ctx):
    service, user_a_id, _ = pomodoro_service_ctx

    service.record_pomodoro_session(user_a_id, "work", 25, completed=True, session_date="2026-04-08")
    service.record_pomodoro_session(user_a_id, "work", 25, completed=True, session_date="2026-04-10")

    stats = service.get_pomodoro_stats(user_a_id, end_date="2026-04-10", days=3)

    assert stats["range"]["start_date"] == "2026-04-08"
    assert stats["range"]["end_date"] == "2026-04-10"
    assert stats["summary"]["focus_sessions"] == 2
    assert stats["summary"]["focus_minutes"] == 50
    assert set(stats["by_date"].keys()) == {"2026-04-08", "2026-04-09", "2026-04-10"}


def test_pomodoro_api_supports_filtering_and_auth(pomodoro_api_client):
    client = pomodoro_api_client
    token = login(client, "pomodoro_filter_user")
    headers = auth_headers(token)

    assert client.get("/api/pomodoro/sessions").status_code == 401

    client.post(
        "/api/pomodoro/sessions",
        headers=headers,
        json={"session_type": "work", "duration_minutes": 25, "completed": True, "session_date": "2026-04-10"},
    )
    client.post(
        "/api/pomodoro/sessions",
        headers=headers,
        json={"session_type": "work", "duration_minutes": 25, "completed": False, "session_date": "2026-04-10"},
    )
    client.post(
        "/api/pomodoro/sessions",
        headers=headers,
        json={"session_type": "short_break", "duration_minutes": 5, "completed": True, "session_date": "2026-04-10"},
    )

    filtered = client.get(
        "/api/pomodoro/sessions?start_date=2026-04-10&end_date=2026-04-10&session_type=work&completed=true",
        headers=headers,
    )
    assert filtered.status_code == 200
    items = filtered.json()["items"]
    assert len(items) == 1
    assert items[0]["session_type"] == "work"
    assert items[0]["completed"] is True

