import sys
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
def workflow_ctx():
    db_dir = project_root / "tests" / "integration" / ".tmp"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / f"workflow_{uuid4().hex}.db"

    app = create_app(db_path=str(db_path))
    client = TestClient(app)

    username = f"workflow_{uuid4().hex[:8]}"
    assert client.post("/api/auth/register", json={"username": username, "password": "secure123"}).status_code == 200
    login_resp = client.post("/api/auth/login", json={"username": username, "password": "secure123"})
    assert login_resp.status_code == 200
    headers = auth_headers(login_resp.json()["token"])

    alpha_resp = client.post("/api/categories", headers=headers, json={"name": "FlowAlpha", "color": "#1188AA"})
    beta_resp = client.post("/api/categories", headers=headers, json={"name": "FlowBeta", "color": "#AA6611"})
    assert alpha_resp.status_code == 200
    assert beta_resp.status_code == 200

    try:
        yield {
            "client": client,
            "headers": headers,
            "categories": {
                "alpha": alpha_resp.json()["item"]["name"],
                "beta": beta_resp.json()["item"]["name"],
            },
        }
    finally:
        client.close()
        if db_path.exists():
            db_path.unlink()


def test_complete_task_workflow(workflow_ctx):
    client = workflow_ctx["client"]
    headers = workflow_ctx["headers"]
    alpha = workflow_ctx["categories"]["alpha"]
    beta = workflow_ctx["categories"]["beta"]

    create_resp = client.post(
        "/api/tasks",
        headers=headers,
        json={
            "title": "Complete Workflow",
            "description": "baseline integration",
            "category": alpha,
            "quadrant": 1,
            "due_at": "2026-05-02T09:00",
            "recurrence_rule": "none",
        },
    )
    assert create_resp.status_code == 200
    task_id = create_resp.json()["item"]["id"]

    query_resp = client.get("/api/tasks?status=all", headers=headers)
    assert query_resp.status_code == 200
    assert any(item["id"] == task_id for item in query_resp.json()["items"])

    update_resp = client.put(
        f"/api/tasks/{task_id}",
        headers=headers,
        json={
            "title": "Complete Workflow Updated",
            "description": "updated integration",
            "category": beta,
            "quadrant": 2,
            "due_at": "",
            "recurrence_rule": "weekly",
        },
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["item"]["title"] == "Complete Workflow Updated"

    delete_resp = client.delete(f"/api/tasks/{task_id}", headers=headers)
    assert delete_resp.status_code == 200

    after_delete = client.get("/api/tasks?status=all", headers=headers)
    assert after_delete.status_code == 200
    assert not any(item["id"] == task_id for item in after_delete.json()["items"])


def test_task_filtering(workflow_ctx):
    client = workflow_ctx["client"]
    headers = workflow_ctx["headers"]
    alpha = workflow_ctx["categories"]["alpha"]
    beta = workflow_ctx["categories"]["beta"]

    payloads = [
        {"title": "Alpha Q1", "description": "", "category": alpha, "quadrant": 1, "due_at": "", "recurrence_rule": "none"},
        {"title": "Beta Q2", "description": "", "category": beta, "quadrant": 2, "due_at": "", "recurrence_rule": "none"},
        {"title": "Beta Q1", "description": "", "category": beta, "quadrant": 1, "due_at": "", "recurrence_rule": "none"},
    ]
    for payload in payloads:
        resp = client.post("/api/tasks", headers=headers, json=payload)
        assert resp.status_code == 200

    by_category = client.get(f"/api/tasks?category={beta}&status=all", headers=headers)
    assert by_category.status_code == 200
    assert {item["title"] for item in by_category.json()["items"]} == {"Beta Q2", "Beta Q1"}

    by_quadrant = client.get("/api/tasks?quadrant=1&status=all", headers=headers)
    assert by_quadrant.status_code == 200
    assert {item["title"] for item in by_quadrant.json()["items"]} == {"Alpha Q1", "Beta Q1"}
