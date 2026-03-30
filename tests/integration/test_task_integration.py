import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from main import create_app


pytestmark = pytest.mark.integration


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def integration_ctx():
    db_dir = project_root / "tests" / "integration" / ".tmp"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / f"integration_{uuid4().hex}.db"

    app = create_app(db_path=str(db_path))
    client = TestClient(app)

    username = f"integration_user_{uuid4().hex[:8]}"
    register_resp = client.post(
        "/api/auth/register",
        json={"username": username, "password": "secure123"},
    )
    assert register_resp.status_code == 200

    login_resp = client.post(
        "/api/auth/login",
        json={"username": username, "password": "secure123"},
    )
    assert login_resp.status_code == 200

    token = login_resp.json()["token"]
    headers = auth_headers(token)

    category_alpha = client.post(
        "/api/categories",
        headers=headers,
        json={"name": "AlphaCat", "color": "#1188AA"},
    )
    assert category_alpha.status_code == 200

    category_beta = client.post(
        "/api/categories",
        headers=headers,
        json={"name": "BetaCat", "color": "#AA6611"},
    )
    assert category_beta.status_code == 200

    try:
        yield {
            "app": app,
            "client": client,
            "headers": headers,
            "db_path": db_path,
            "categories": {
                "alpha": category_alpha.json()["item"]["name"],
                "beta": category_beta.json()["item"]["name"],
            },
        }
    finally:
        client.close()
        if db_path.exists():
            db_path.unlink()


def test_task_full_lifecycle(integration_ctx):
    client = integration_ctx["client"]
    headers = integration_ctx["headers"]
    categories = integration_ctx["categories"]

    create_resp = client.post(
        "/api/tasks",
        headers=headers,
        json={
            "title": "Integration Task",
            "description": "created in integration test",
            "category": categories["alpha"],
            "quadrant": 1,
            "due_at": "2026-04-01T10:00",
            "recurrence_rule": "none",
        },
    )
    assert create_resp.status_code == 200
    task_id = create_resp.json()["item"]["id"]
    assert create_resp.json()["item"]["due_at"] == "2026-04-01 10:00:00"

    query_resp = client.get("/api/tasks?status=all", headers=headers)
    assert query_resp.status_code == 200
    assert any(item["id"] == task_id for item in query_resp.json()["items"])

    update_resp = client.put(
        f"/api/tasks/{task_id}",
        headers=headers,
        json={
            "title": "Integration Task Updated",
            "description": "updated in integration test",
            "category": categories["beta"],
            "quadrant": 2,
            "due_at": "",
            "recurrence_rule": "weekly",
        },
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["item"]["title"] == "Integration Task Updated"
    assert update_resp.json()["item"]["recurrence_rule"] == "weekly"

    delete_resp = client.delete(f"/api/tasks/{task_id}", headers=headers)
    assert delete_resp.status_code == 200

    after_delete_resp = client.get("/api/tasks?status=all", headers=headers)
    assert after_delete_resp.status_code == 200
    assert not any(item["id"] == task_id for item in after_delete_resp.json()["items"])


def test_task_filtering_by_category_and_quadrant(integration_ctx):
    client = integration_ctx["client"]
    headers = integration_ctx["headers"]
    categories = integration_ctx["categories"]

    payloads = [
        {"title": "Alpha-Q1", "description": "", "category": categories["alpha"], "quadrant": 1},
        {"title": "Beta-Q2", "description": "", "category": categories["beta"], "quadrant": 2},
        {"title": "Beta-Q1", "description": "", "category": categories["beta"], "quadrant": 1},
    ]
    for payload in payloads:
        resp = client.post("/api/tasks", headers=headers, json=payload)
        assert resp.status_code == 200

    category_resp = client.get(f"/api/tasks?category={categories['beta']}&status=all", headers=headers)
    assert category_resp.status_code == 200
    category_titles = {item["title"] for item in category_resp.json()["items"]}
    assert category_titles == {"Beta-Q2", "Beta-Q1"}

    quadrant_resp = client.get("/api/tasks?quadrant=1&status=all", headers=headers)
    assert quadrant_resp.status_code == 200
    quadrant_titles = {item["title"] for item in quadrant_resp.json()["items"]}
    assert quadrant_titles == {"Alpha-Q1", "Beta-Q1"}


def test_concurrent_add_multiple_tasks(integration_ctx):
    app = integration_ctx["app"]
    headers = integration_ctx["headers"]
    category = integration_ctx["categories"]["alpha"]

    def create_task(index: int):
        with TestClient(app) as worker_client:
            response = worker_client.post(
                "/api/tasks",
                headers=headers,
                json={
                    "title": f"Concurrent-{index}",
                    "description": f"payload-{index}",
                    "category": category,
                    "quadrant": (index % 4) + 1,
                },
            )
            assert response.status_code == 200
            return response.json()["item"]["id"]

    with ThreadPoolExecutor(max_workers=5) as executor:
        task_ids = list(executor.map(create_task, range(8)))

    client = integration_ctx["client"]
    list_resp = client.get("/api/tasks?status=all", headers=headers)
    assert list_resp.status_code == 200
    returned_ids = {item["id"] for item in list_resp.json()["items"]}
    assert len(task_ids) == 8
    assert len(set(task_ids)) == 8
    assert set(task_ids).issubset(returned_ids)


def test_task_data_consistency_across_queries(integration_ctx):
    client = integration_ctx["client"]
    headers = integration_ctx["headers"]
    categories = integration_ctx["categories"]

    create_resp = client.post(
        "/api/tasks",
        headers=headers,
        json={
            "title": "Consistency Task",
            "description": "same task via multiple queries",
            "category": categories["beta"],
            "quadrant": 3,
        },
    )
    assert create_resp.status_code == 200
    created_item = create_resp.json()["item"]

    all_resp = client.get("/api/tasks?status=all", headers=headers)
    keyword_resp = client.get("/api/tasks?keyword=Consistency&status=all", headers=headers)
    combo_resp = client.get(
        f"/api/tasks?category={categories['beta']}&quadrant=3&status=all",
        headers=headers,
    )

    assert all_resp.status_code == 200
    assert keyword_resp.status_code == 200
    assert combo_resp.status_code == 200

    def pick_item(payload: dict):
        return next(item for item in payload["items"] if item["id"] == created_item["id"])

    item_from_all = pick_item(all_resp.json())
    item_from_keyword = pick_item(keyword_resp.json())
    item_from_combo = pick_item(combo_resp.json())

    assert item_from_all == item_from_keyword == item_from_combo == created_item


def test_combined_filter_by_category_and_quadrant(integration_ctx):
    client = integration_ctx["client"]
    headers = integration_ctx["headers"]
    categories = integration_ctx["categories"]

    payloads = [
        {"title": "Target-1", "description": "", "category": categories["alpha"], "quadrant": 4},
        {"title": "Target-2", "description": "", "category": categories["alpha"], "quadrant": 4},
        {"title": "OffCategory", "description": "", "category": categories["beta"], "quadrant": 4},
        {"title": "OffQuadrant", "description": "", "category": categories["alpha"], "quadrant": 2},
    ]
    for payload in payloads:
        resp = client.post("/api/tasks", headers=headers, json=payload)
        assert resp.status_code == 200

    filtered_resp = client.get(
        f"/api/tasks?category={categories['alpha']}&quadrant=4&status=all",
        headers=headers,
    )
    assert filtered_resp.status_code == 200
    filtered_titles = {item["title"] for item in filtered_resp.json()["items"]}
    assert filtered_titles == {"Target-1", "Target-2"}


def test_schedule_overview_and_calendar(integration_ctx):
    client = integration_ctx["client"]
    headers = integration_ctx["headers"]
    categories = integration_ctx["categories"]

    payloads = [
        {
            "title": "One shot",
            "description": "",
            "category": categories["alpha"],
            "quadrant": 1,
            "due_at": "2026-03-30T11:00",
            "recurrence_rule": "none",
        },
        {
            "title": "Recurring",
            "description": "",
            "category": categories["beta"],
            "quadrant": 2,
            "due_at": "2026-03-29T08:00",
            "recurrence_rule": "daily",
        },
        {
            "title": "No deadline",
            "description": "",
            "category": categories["beta"],
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
    today_titles = {item["title"] for item in overview.json()["today"]}
    assert "One shot" in today_titles
    assert "Recurring" in today_titles
    assert "No deadline" not in today_titles

    calendar = client.get("/api/schedule/calendar?start_date=2026-03-30&days=7", headers=headers)
    assert calendar.status_code == 200
    body = calendar.json()
    assert body["start_date"] == "2026-03-30"
    assert "2026-03-30" in body["by_date"]
    assert all(item["title"] != "No deadline" for item in body["items"])


def test_csv_backup_export_and_import(integration_ctx):
    client = integration_ctx["client"]
    headers = integration_ctx["headers"]
    category = integration_ctx["categories"]["alpha"]

    create_resp = client.post(
        "/api/tasks",
        headers=headers,
        json={
            "title": "CSV Backup",
            "description": "round trip",
            "category": category,
            "quadrant": 2,
            "due_at": "2026-04-20T08:00",
            "recurrence_rule": "monthly",
        },
    )
    assert create_resp.status_code == 200

    export_resp = client.get("/api/tasks/export", headers=headers)
    assert export_resp.status_code == 200
    csv_text = export_resp.text
    assert "CSV Backup" in csv_text

    import_resp = client.post("/api/tasks/import", headers=headers, json={"csv_text": csv_text})
    assert import_resp.status_code == 200
    assert import_resp.json()["imported"] >= 1
