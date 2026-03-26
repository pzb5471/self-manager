"""Additional pytest unit tests for TaskService using in-memory SQLite."""

import sys
from pathlib import Path
from uuid import uuid4

import pytest

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from service import TaskService

pytestmark = pytest.mark.unit


@pytest.fixture
def service_with_users():
    db_path = f"file:unit_extra_{uuid4().hex}?mode=memory&cache=shared"
    service = TaskService(db_path=db_path)
    user_a = service.register_user("carol", "carol123")
    user_b = service.register_user("dave", "dave1234")
    yield {
        "service": service,
        "user_a_id": user_a["id"],
        "user_b_id": user_b["id"],
        "db_path": db_path,
    }
    service.close()


def test_crud_lifecycle_with_status_toggle(service_with_users):
    service = service_with_users["service"]
    user_a_id = service_with_users["user_a_id"]

    created = service.add_task(
        user_id=user_a_id,
        title="Read book",
        description="chapter 1",
        category="学习",
        quadrant=2,
    )
    assert created["title"] == "Read book"
    assert created["completed"] is False

    loaded = service.get_task_by_id(created["id"], user_a_id)
    assert loaded is not None
    assert loaded["description"] == "chapter 1"

    updated = service.update_task(
        task_id=created["id"],
        user_id=user_a_id,
        title="Read book deeply",
        description="chapter 1 and 2",
        category="学习",
        quadrant=1,
        completed=True,
    )
    assert updated is True

    after_update = service.get_task_by_id(created["id"], user_a_id)
    assert after_update is not None
    assert after_update["title"] == "Read book deeply"
    assert after_update["quadrant"] == 1
    assert after_update["completed"] is True

    assert service.delete_task(created["id"], user_a_id) is True
    assert service.get_task_by_id(created["id"], user_a_id) is None


def test_category_crud_and_filtering(service_with_users):
    service = service_with_users["service"]
    user_a_id = service_with_users["user_a_id"]
    user_b_id = service_with_users["user_b_id"]

    category = service.create_category(user_a_id, "副业", "#AA5500")
    assert category["name"] == "副业"

    service.add_task(user_a_id, "Task A", "", "副业", 1)
    service.add_task(user_a_id, "Task B", "", "副业", 2)
    service.add_task(user_b_id, "Task C", "", "工作", 1)

    filtered = service.filter_tasks(user_id=user_a_id, category="副业", quadrant=1, status="pending")
    assert len(filtered) == 1
    assert filtered[0]["title"] == "Task A"

    renamed = service.update_category(category["id"], user_a_id, "副业项目", "#0055AA")
    assert renamed is not None
    assert renamed["name"] == "副业项目"

    all_tasks = service.get_all_tasks(user_a_id, status="all")
    assert {task["category"] for task in all_tasks} == {"副业项目"}


def test_completed_status_queries_are_isolated(service_with_users):
    service = service_with_users["service"]
    user_a_id = service_with_users["user_a_id"]
    user_b_id = service_with_users["user_b_id"]

    task_a = service.add_task(user_a_id, "Alpha", "", "工作", 1)
    task_b = service.add_task(user_b_id, "Beta", "", "生活", 3)

    assert service.set_task_completed(task_a["id"], user_a_id, True) is True

    completed_a = service.get_all_tasks(user_a_id, status="completed")
    pending_a = service.get_all_tasks(user_a_id, status="pending")
    completed_b = service.get_all_tasks(user_b_id, status="completed")
    pending_b = service.get_all_tasks(user_b_id, status="pending")

    assert [task["id"] for task in completed_a] == [task_a["id"]]
    assert pending_a == []
    assert completed_b == []
    assert [task["id"] for task in pending_b] == [task_b["id"]]
