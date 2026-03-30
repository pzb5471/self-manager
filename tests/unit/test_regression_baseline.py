import sys
from pathlib import Path
from uuid import uuid4

import pytest

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from service import TaskService

pytestmark = pytest.mark.unit


@pytest.fixture
def baseline_service_ctx():
    db_path = f"file:baseline_unit_{uuid4().hex}?mode=memory&cache=shared"
    service = TaskService(db_path=db_path)
    user = service.register_user("baseline_user", "secure123")
    service.login_user("baseline_user", "secure123")

    ctx = {
        "service": service,
        "user_id": user["id"],
        "categories": service.get_categories(),
    }
    try:
        yield ctx
    finally:
        service.close()


def test_add_task(baseline_service_ctx):
    service = baseline_service_ctx["service"]
    user_id = baseline_service_ctx["user_id"]
    category = baseline_service_ctx["categories"][0]

    created = service.add_task(
        user_id=user_id,
        title="Baseline add",
        description="unit baseline",
        category=category,
        quadrant=1,
        due_at="2026-05-01 09:00",
    )

    assert created["title"] == "Baseline add"
    assert created["category"] == category
    assert created["due_at"] == "2026-05-01 09:00:00"


def test_update_task(baseline_service_ctx):
    service = baseline_service_ctx["service"]
    user_id = baseline_service_ctx["user_id"]
    categories = baseline_service_ctx["categories"]

    task = service.add_task(user_id, "Before update", "", categories[0], 1)
    updated = service.update_task(
        task_id=task["id"],
        user_id=user_id,
        title="After update",
        category=categories[1],
        quadrant=2,
        recurrence_rule="weekly",
    )

    latest = service.get_task_by_id(task["id"], user_id)
    assert updated is True
    assert latest is not None
    assert latest["title"] == "After update"
    assert latest["category"] == categories[1]
    assert latest["quadrant"] == 2
    assert latest["recurrence_rule"] == "weekly"


def test_delete_task(baseline_service_ctx):
    service = baseline_service_ctx["service"]
    user_id = baseline_service_ctx["user_id"]
    category = baseline_service_ctx["categories"][0]

    task = service.add_task(user_id, "Delete me", "", category, 3)
    deleted = service.delete_task(task["id"], user_id)

    assert deleted is True
    assert service.get_task_by_id(task["id"], user_id) is None
