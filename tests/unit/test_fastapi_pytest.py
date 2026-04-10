import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from main import create_app

pytestmark = pytest.mark.unit


@pytest.fixture
def api_ctx():
    db_path = f"file:unit_api_{uuid4().hex}?mode=memory&cache=shared"

    app = create_app(db_path=db_path)
    client = TestClient(app)

    yield {"client": client, "db_path": db_path}


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
            "due_at": "2026-04-01T09:00",
            "recurrence_rule": "none",
        },
    )
    assert created.status_code == 200
    task_id = created.json()["item"]["id"]
    assert created.json()["item"]["due_at"] == "2026-04-01 09:00:00"

    updated = client.put(
        f"/api/tasks/{task_id}",
        headers=headers,
        json={
            "title": "Project report v2",
            "description": "updated",
            "category": "学习",
            "quadrant": 2,
            "due_at": "",
            "recurrence_rule": "weekly",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["item"]["title"] == "Project report v2"
    assert updated.json()["item"]["due_at"] is None
    assert updated.json()["item"]["recurrence_rule"] == "weekly"

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


def test_category_management_and_status_filter(api_ctx):
    client = api_ctx["client"]
    token = register_and_login(client)
    headers = auth_headers(token)

    list_resp = client.get("/api/categories", headers=headers)
    assert list_resp.status_code == 200
    initial_count = len(list_resp.json()["items"])
    assert initial_count >= 4

    created_category = client.post(
        "/api/categories",
        headers=headers,
        json={"name": "家庭", "color": "#FF8800"},
    )
    assert created_category.status_code == 200
    category_id = created_category.json()["item"]["id"]

    updated_category = client.put(
        f"/api/categories/{category_id}",
        headers=headers,
        json={"name": "家庭事务", "color": "#0088FF"},
    )
    assert updated_category.status_code == 200
    assert updated_category.json()["item"]["name"] == "家庭事务"

    created_task = client.post(
        "/api/tasks",
        headers=headers,
        json={
            "title": "整理房间",
            "description": "周末完成",
            "category": "家庭事务",
            "quadrant": 2,
            "due_at": "2026-04-06T20:30",
            "recurrence_rule": "monthly",
        },
    )
    assert created_task.status_code == 200
    task_id = created_task.json()["item"]["id"]
    assert created_task.json()["item"]["completed"] is False
    assert created_task.json()["item"]["recurrence_rule"] == "monthly"

    default_list = client.get("/api/tasks", headers=headers)
    assert default_list.status_code == 200
    assert len(default_list.json()["items"]) == 1

    complete_resp = client.patch(
        f"/api/tasks/{task_id}/status",
        headers=headers,
        json={"completed": True},
    )
    assert complete_resp.status_code == 200
    assert complete_resp.json()["item"]["completed"] is True

    pending_list = client.get("/api/tasks?status=pending", headers=headers)
    completed_list = client.get("/api/tasks?status=completed", headers=headers)
    all_list = client.get("/api/tasks?status=all", headers=headers)
    assert pending_list.status_code == 200
    assert completed_list.status_code == 200
    assert all_list.status_code == 200
    assert pending_list.json()["items"] == []
    assert len(completed_list.json()["items"]) == 1
    assert len(all_list.json()["items"]) == 1

    delete_used_category = client.delete(f"/api/categories/{category_id}", headers=headers)
    assert delete_used_category.status_code == 400

    delete_task = client.delete(f"/api/tasks/{task_id}", headers=headers)
    assert delete_task.status_code == 200

    delete_category = client.delete(f"/api/categories/{category_id}", headers=headers)
    assert delete_category.status_code == 200


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


def test_schedule_overview_and_calendar_endpoints(api_ctx):
    client = api_ctx["client"]
    token = register_and_login(client, username="planner")
    headers = auth_headers(token)
    today = datetime.utcnow().date()
    today_str = today.isoformat()
    yesterday_str = (today - timedelta(days=1)).isoformat()

    payloads = [
        {
            "title": "Today plan",
            "description": "",
            "category": "工作",
            "quadrant": 1,
            "due_at": f"{today_str}T09:00",
            "recurrence_rule": "none",
        },
        {
            "title": "Weekly sync",
            "description": "",
            "category": "学习",
            "quadrant": 2,
            "due_at": f"{yesterday_str}T08:30",
            "recurrence_rule": "daily",
        },
        {
            "title": "Someday",
            "description": "",
            "category": "生活",
            "quadrant": 3,
            "due_at": "",
            "recurrence_rule": "none",
        },
    ]
    for payload in payloads:
        resp = client.post("/api/tasks", headers=headers, json=payload)
        assert resp.status_code == 200

    overview = client.get("/api/schedule/overview", headers=headers)
    assert overview.status_code == 200
    today_titles = [item["title"] for item in overview.json()["today"]]
    assert "Today plan" in today_titles
    assert "Weekly sync" in today_titles
    assert "Someday" not in today_titles

    calendar = client.get(f"/api/schedule/calendar?start_date={today_str}&days=3", headers=headers)
    assert calendar.status_code == 200
    body = calendar.json()
    assert body["start_date"] == today_str
    assert today_str in body["by_date"]


def test_task_export_and_import_csv(api_ctx):
    client = api_ctx["client"]
    token = register_and_login(client, username="backup_user")
    headers = auth_headers(token)

    create_resp = client.post(
        "/api/tasks",
        headers=headers,
        json={
            "title": "Backup Task",
            "description": "for csv export",
            "category": "工作",
            "quadrant": 1,
            "due_at": "2026-04-12T09:15",
            "recurrence_rule": "weekly",
        },
    )
    assert create_resp.status_code == 200

    export_resp = client.get("/api/tasks/export", headers=headers)
    assert export_resp.status_code == 200
    assert "text/csv" in export_resp.headers["content-type"]
    csv_text = export_resp.text
    assert "Backup Task" in csv_text
    assert "recurrence_rule" in csv_text

    import_resp = client.post(
        "/api/tasks/import",
        headers=headers,
        json={"csv_text": csv_text},
    )
    assert import_resp.status_code == 200
    assert import_resp.json()["imported"] >= 1

    all_resp = client.get("/api/tasks?status=all", headers=headers)
    assert all_resp.status_code == 200
    titles = [item["title"] for item in all_resp.json()["items"]]
    assert titles.count("Backup Task") >= 2


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
