import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from main import create_app


@pytest.fixture
def api_ctx():
    db_dir = project_root / "tests" / ".tmp"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / f"api_{uuid4().hex}.db"

    app = create_app(db_path=str(db_path))
    client = TestClient(app)

    try:
        yield {"client": client, "db_path": db_path}
    finally:
        if db_path.exists():
            db_path.unlink()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register_and_login(client: TestClient, username: str = "alice") -> str:
    register_resp = client.post(
        "/api/auth/register",
        json={"username": username, "password": "alice123"},
    )
    assert register_resp.status_code == 200

    login_resp = client.post(
        "/api/auth/login",
        json={"username": username, "password": "alice123"},
    )
    assert login_resp.status_code == 200
    return login_resp.json()["token"]


def test_root_page_served(api_ctx):
    client = api_ctx["client"]

    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_auth_required_on_tasks(api_ctx):
    client = api_ctx["client"]

    resp = client.get("/api/tasks")
    assert resp.status_code == 401


def test_register_login_me_logout_flow(api_ctx):
    client = api_ctx["client"]
    token = register_and_login(client)

    me_resp = client.get("/api/auth/me", headers=auth_headers(token))
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["username"] == "alice"

    logout_resp = client.post("/api/auth/logout", headers=auth_headers(token))
    assert logout_resp.status_code == 200

    me_after = client.get("/api/auth/me", headers=auth_headers(token))
    assert me_after.status_code == 401


def test_task_crud_and_filter(api_ctx):
    client = api_ctx["client"]
    token = register_and_login(client)
    headers = auth_headers(token)

    created = client.post(
        "/api/tasks",
        headers=headers,
        json={
            "title": "Project report",
            "description": "monthly summary",
            "category": "工作",
            "quadrant": 1,
        },
    )
    assert created.status_code == 200
    task_id = created.json()["item"]["id"]

    updated = client.put(
        f"/api/tasks/{task_id}",
        headers=headers,
        json={
            "title": "Project report v2",
            "description": "updated",
            "category": "学习",
            "quadrant": 2,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["item"]["title"] == "Project report v2"

    filtered = client.get("/api/tasks?keyword=report&category=学习&quadrant=2", headers=headers)
    assert filtered.status_code == 200
    items = filtered.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == task_id

    deleted = client.delete(f"/api/tasks/{task_id}", headers=headers)
    assert deleted.status_code == 200

    after_delete = client.get("/api/tasks", headers=headers)
    assert after_delete.status_code == 200
    assert after_delete.json()["items"] == []


def test_dashboard_stats(api_ctx):
    client = api_ctx["client"]
    token = register_and_login(client)
    headers = auth_headers(token)

    payloads = [
        {"title": "A task", "description": "", "category": "工作", "quadrant": 1},
        {"title": "B task", "description": "", "category": "学习", "quadrant": 2},
    ]
    for payload in payloads:
        resp = client.post("/api/tasks", headers=headers, json=payload)
        assert resp.status_code == 200

    stats_resp = client.get("/api/stats/dashboard", headers=headers)
    assert stats_resp.status_code == 200

    body = stats_resp.json()
    assert body["stats"]["total"] == 2
    assert body["stats"]["by_quadrant"]["1"] == 1
    assert body["stats"]["by_quadrant"]["2"] == 1
    assert len(body["trend"]) == 14


def test_login_ttl_respects_remember_me(api_ctx):
    client = api_ctx["client"]

    register_resp = client.post(
        "/api/auth/register",
        json={"username": "ttl_user", "password": "alice123"},
    )
    assert register_resp.status_code == 200

    normal_login = client.post(
        "/api/auth/login",
        json={"username": "ttl_user", "password": "alice123", "remember_me": False},
    )
    remember_login = client.post(
        "/api/auth/login",
        json={"username": "ttl_user", "password": "alice123", "remember_me": True},
    )
    assert normal_login.status_code == 200
    assert remember_login.status_code == 200

    normal_exp = datetime.strptime(normal_login.json()["expires_at"], "%Y-%m-%d %H:%M:%S")
    remember_exp = datetime.strptime(remember_login.json()["expires_at"], "%Y-%m-%d %H:%M:%S")
    ttl_hours_normal = (normal_exp - datetime.utcnow()).total_seconds() / 3600
    ttl_hours_remember = (remember_exp - datetime.utcnow()).total_seconds() / 3600

    assert 23 <= ttl_hours_normal <= 24.1
    assert 167 <= ttl_hours_remember <= 168.1
