"""Pytest tests for TaskService authentication and per-user SQLite behavior."""

import hashlib
import sqlite3
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from service import TaskService

pytestmark = pytest.mark.unit


@pytest.fixture
def service_ctx():
    db_path = f"file:unit_service_{uuid4().hex}?mode=memory&cache=shared"
    service = TaskService(db_path=db_path)

    user_a = service.register_user("alice", "alice123")
    user_b = service.register_user("bob", "bob12345")

    login_a = service.login_user("alice", "alice123")
    login_b = service.login_user("bob", "bob12345")
    assert login_a is not None
    assert login_b is not None

    ctx = {
        "service": service,
        "db_path": db_path,
        "user_a": user_a,
        "user_b": user_b,
        "token_a": login_a["token"],
        "token_b": login_b["token"],
        "user_a_id": user_a["id"],
        "user_b_id": user_b["id"],
        "categories": service.get_categories(),
    }

    try:
        yield ctx
    finally:
        service.close()


def test_database_file_and_schema_created(service_ctx):
    db_path = service_ctx["db_path"]
    conn = sqlite3.connect(db_path, uri=True)
    cursor = conn.cursor()

    for table_name in ("tasks", "users", "auth_tokens", "categories"):
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        assert cursor.fetchone() is not None, f"Missing table: {table_name}"

    for index_name in (
        "idx_tasks_category",
        "idx_tasks_quadrant",
        "idx_tasks_created_at",
        "idx_tasks_user_id",
        "idx_tasks_user_completed",
        "idx_tasks_category_id",
        "idx_categories_user_name",
        "idx_auth_tokens_token",
        "idx_auth_tokens_token_hash",
    ):
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name=?", (index_name,))
        assert cursor.fetchone() is not None, f"Missing index: {index_name}"
    conn.close()


def test_register_duplicate_user_rejected(service_ctx):
    service = service_ctx["service"]
    with pytest.raises(ValueError):
        service.register_user("alice", "anotherpass")


def test_login_verify_and_logout(service_ctx):
    service = service_ctx["service"]
    token_a = service_ctx["token_a"]

    verified = service.verify_token(token_a)
    assert verified is not None
    assert verified["username"] == "alice"

    assert service.logout(token_a) is True
    assert service.verify_token(token_a) is None


def test_auth_token_stores_hash_not_plaintext(service_ctx):
    service = service_ctx["service"]
    db_path = service_ctx["db_path"]
    user_a_id = service_ctx["user_a_id"]
    token_a = service_ctx["token_a"]

    conn = sqlite3.connect(db_path, uri=True)
    cursor = conn.cursor()
    cursor.execute("SELECT token, token_hash FROM auth_tokens WHERE user_id = ?", (user_a_id,))
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row[0] != token_a
    assert row[1] == hashlib.sha256(token_a.encode("utf-8")).hexdigest()


def test_legacy_tasks_not_auto_claimed_on_login(service_ctx):
    service = service_ctx["service"]
    db_path = service_ctx["db_path"]
    categories = service_ctx["categories"]
    user_a_id = service_ctx["user_a_id"]
    user_b_id = service_ctx["user_b_id"]

    conn = sqlite3.connect(db_path, uri=True)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO tasks (user_id, title, description, category, quadrant, created_at, updated_at)
        VALUES (NULL, 'legacy task', '', ?, 1, datetime('now'), datetime('now'))
        """,
        (categories[0],),
    )
    conn.commit()
    conn.close()

    # Re-login should not auto-claim legacy rows.
    assert service.login_user("alice", "alice123") is not None

    tasks_a = service.get_all_tasks(user_a_id)
    tasks_b = service.get_all_tasks(user_b_id)
    assert not any(t["title"] == "legacy task" for t in tasks_a)
    assert not any(t["title"] == "legacy task" for t in tasks_b)


def test_add_task_and_get_by_id(service_ctx):
    service = service_ctx["service"]
    user_a_id = service_ctx["user_a_id"]
    categories = service_ctx["categories"]

    created = service.add_task(
        user_id=user_a_id,
        title="Quarterly review",
        description="Prepare KPI summary",
        category=categories[0],
        quadrant=1,
    )

    loaded = service.get_task_by_id(created["id"], user_a_id)
    assert loaded is not None
    assert loaded["title"] == "Quarterly review"
    assert loaded["description"] == "Prepare KPI summary"
    assert loaded["user_id"] == user_a_id


def test_user_isolation_between_tasks(service_ctx):
    service = service_ctx["service"]
    user_a_id = service_ctx["user_a_id"]
    user_b_id = service_ctx["user_b_id"]
    categories = service_ctx["categories"]

    task_a = service.add_task(user_a_id, "A task", "", categories[0], 1)
    service.add_task(user_b_id, "B task", "", categories[1], 2)

    list_a = service.get_all_tasks(user_a_id)
    list_b = service.get_all_tasks(user_b_id)

    assert len(list_a) == 1
    assert len(list_b) == 1
    assert list_a[0]["title"] == "A task"
    assert list_b[0]["title"] == "B task"
    assert service.get_task_by_id(task_a["id"], user_b_id) is None


def test_validation_errors(service_ctx):
    service = service_ctx["service"]
    user_a_id = service_ctx["user_a_id"]
    categories = service_ctx["categories"]

    with pytest.raises(ValueError):
        service.add_task(user_a_id, "", "", categories[0], 1)
    with pytest.raises(ValueError):
        service.add_task(user_a_id, "a", "", categories[0], 1)
    with pytest.raises(ValueError):
        service.add_task(user_a_id, "Valid title", "", "invalid", 1)
    with pytest.raises(ValueError):
        service.add_task(user_a_id, "Valid title", "", categories[0], 9)
    with pytest.raises(ValueError):
        service.add_task(0, "Valid title", "", categories[0], 1)


def test_update_task_success(service_ctx):
    service = service_ctx["service"]
    user_a_id = service_ctx["user_a_id"]
    categories = service_ctx["categories"]

    task = service.add_task(user_a_id, "Initial title", "Initial desc", categories[1], 2)
    updated = service.update_task(
        task_id=task["id"],
        user_id=user_a_id,
        title="Updated title",
        description="Updated desc",
        category=categories[2],
        quadrant=4,
    )

    assert updated is True
    latest = service.get_task_by_id(task["id"], user_a_id)
    assert latest["title"] == "Updated title"
    assert latest["description"] == "Updated desc"
    assert latest["category"] == categories[2]
    assert latest["quadrant"] == 4


def test_update_task_returns_false_when_not_exists_or_not_owner(service_ctx):
    service = service_ctx["service"]
    user_a_id = service_ctx["user_a_id"]
    user_b_id = service_ctx["user_b_id"]
    categories = service_ctx["categories"]

    assert service.update_task(task_id=999999, user_id=user_a_id, title="new") is False

    task = service.add_task(user_a_id, "Owned by A", "", categories[0], 1)
    assert service.update_task(task_id=task["id"], user_id=user_b_id, title="hijack") is False


def test_delete_task_success(service_ctx):
    service = service_ctx["service"]
    user_a_id = service_ctx["user_a_id"]
    categories = service_ctx["categories"]

    task = service.add_task(user_a_id, "To delete", "", categories[2], 3)
    assert service.delete_task(task["id"], user_a_id) is True
    assert service.get_task_by_id(task["id"], user_a_id) is None


def test_delete_task_not_owner(service_ctx):
    service = service_ctx["service"]
    user_a_id = service_ctx["user_a_id"]
    user_b_id = service_ctx["user_b_id"]
    categories = service_ctx["categories"]

    task = service.add_task(user_a_id, "Keep me", "", categories[0], 1)
    assert service.delete_task(task["id"], user_b_id) is False


def test_filter_tasks_by_category_and_quadrant(service_ctx):
    service = service_ctx["service"]
    user_a_id = service_ctx["user_a_id"]
    categories = service_ctx["categories"]

    service.add_task(user_a_id, "Task A", "", categories[0], 1)
    service.add_task(user_a_id, "Task B", "", categories[0], 2)
    service.add_task(user_a_id, "Task C", "", categories[1], 1)

    filtered = service.filter_tasks(user_id=user_a_id, category=categories[0], quadrant=1)
    assert len(filtered) == 1
    assert filtered[0]["title"] == "Task A"


def test_category_crud_and_task_completion_filter(service_ctx):
    service = service_ctx["service"]
    user_a_id = service_ctx["user_a_id"]

    initial_categories = service.list_categories(user_a_id)
    assert len(initial_categories) >= 4

    created_category = service.create_category(user_a_id, "家庭", "#FF8800")
    assert created_category["name"] == "家庭"
    assert created_category["color"] == "#FF8800"

    updated_category = service.update_category(created_category["id"], user_a_id, "家庭事务", "#0088FF")
    assert updated_category is not None
    assert updated_category["name"] == "家庭事务"
    assert updated_category["color"] == "#0088FF"

    task = service.add_task(user_a_id, "拖地", "周末整理", "家庭事务", 3)
    assert task["category"] == "家庭事务"
    assert task["completed"] is False

    pending_tasks = service.get_all_tasks(user_a_id, status="pending")
    assert any(item["id"] == task["id"] for item in pending_tasks)

    assert service.set_task_completed(task["id"], user_a_id, True) is True
    completed_task = service.get_task_by_id(task["id"], user_a_id)
    assert completed_task is not None
    assert completed_task["completed"] is True

    pending_after = service.get_all_tasks(user_a_id, status="pending")
    completed_after = service.get_all_tasks(user_a_id, status="completed")
    assert not any(item["id"] == task["id"] for item in pending_after)
    assert any(item["id"] == task["id"] for item in completed_after)

    with pytest.raises(ValueError):
        service.delete_category(updated_category["id"], user_a_id)

    assert service.delete_task(task["id"], user_a_id) is True
    assert service.delete_category(updated_category["id"], user_a_id) is True


def test_statistics(service_ctx):
    service = service_ctx["service"]
    user_a_id = service_ctx["user_a_id"]
    user_b_id = service_ctx["user_b_id"]
    categories = service_ctx["categories"]

    service.add_task(user_a_id, "t1", "", categories[0], 1)
    service.add_task(user_a_id, "t2", "", categories[1], 2)
    service.add_task(user_a_id, "t3", "", categories[1], 2)
    service.add_task(user_b_id, "t4", "", categories[1], 2)

    stats = service.get_statistics(user_a_id)
    assert stats["total"] == 3
    assert stats["by_category"][categories[0]] == 1
    assert stats["by_category"][categories[1]] == 2
    assert stats["by_quadrant"][1] == 1
    assert stats["by_quadrant"][2] == 2


def test_sql_injection_is_blocked(service_ctx):
    service = service_ctx["service"]
    db_path = service_ctx["db_path"]
    user_a_id = service_ctx["user_a_id"]
    categories = service_ctx["categories"]

    malicious_title = "test'; DROP TABLE tasks; --"
    service.add_task(user_a_id, malicious_title, "", categories[0], 1)

    conn = sqlite3.connect(db_path, uri=True)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tasks")
    count = cursor.fetchone()[0]
    conn.close()
    assert count == 1


def test_search_tasks_by_title_and_description(service_ctx):
    service = service_ctx["service"]
    user_a_id = service_ctx["user_a_id"]
    user_b_id = service_ctx["user_b_id"]
    categories = service_ctx["categories"]

    service.add_task(user_a_id, "Project report", "Monthly report details", categories[0], 1)
    service.add_task(user_a_id, "Python study", "Online lessons", categories[1], 2)
    service.add_task(user_b_id, "Project hidden", "Not visible", categories[0], 1)

    by_title = service.search_tasks(user_a_id, "Project")
    by_desc = service.search_tasks(user_a_id, "lessons")

    assert len(by_title) == 1
    assert by_title[0]["title"] == "Project report"
    assert len(by_desc) == 1
    assert by_desc[0]["title"] == "Python study"


def test_search_tasks_empty_keyword_returns_all(service_ctx):
    service = service_ctx["service"]
    user_a_id = service_ctx["user_a_id"]
    categories = service_ctx["categories"]

    service.add_task(user_a_id, "task1", "", categories[0], 1)
    service.add_task(user_a_id, "task2", "", categories[1], 2)
    assert len(service.search_tasks(user_a_id, "")) == 2
    assert len(service.search_tasks(user_a_id, "   ")) == 2


def test_sort_tasks_created(service_ctx):
    service = service_ctx["service"]
    user_a_id = service_ctx["user_a_id"]
    categories = service_ctx["categories"]

    t1 = service.add_task(user_a_id, "task1", "", categories[0], 1)
    t2 = service.add_task(user_a_id, "task2", "", categories[0], 1)
    t3 = service.add_task(user_a_id, "task3", "", categories[0], 1)

    desc_ids = [t["id"] for t in service.get_sorted_tasks(user_a_id, "created_desc")]
    asc_ids = [t["id"] for t in service.get_sorted_tasks(user_a_id, "created_asc")]

    assert desc_ids == [t3["id"], t2["id"], t1["id"]]
    assert asc_ids == [t1["id"], t2["id"], t3["id"]]


def test_sort_tasks_updated_desc(service_ctx):
    service = service_ctx["service"]
    user_a_id = service_ctx["user_a_id"]
    categories = service_ctx["categories"]

    t1 = service.add_task(user_a_id, "task1", "", categories[0], 1)
    t2 = service.add_task(user_a_id, "task2", "", categories[0], 1)

    time.sleep(1.1)
    service.update_task(t1["id"], user_a_id, description="updated")

    results = service.get_sorted_tasks(user_a_id, "updated_desc")
    assert results[0]["id"] == t1["id"]
    assert results[1]["id"] == t2["id"]


def test_sort_tasks_invalid_option_falls_back(service_ctx):
    service = service_ctx["service"]
    user_a_id = service_ctx["user_a_id"]
    categories = service_ctx["categories"]

    service.add_task(user_a_id, "task1", "", categories[0], 1)
    results = service.get_sorted_tasks(user_a_id, "invalid_option")
    assert len(results) == 1


def test_sort_tasks_isolation(service_ctx):
    service = service_ctx["service"]
    user_a_id = service_ctx["user_a_id"]
    user_b_id = service_ctx["user_b_id"]
    categories = service_ctx["categories"]

    service.add_task(user_a_id, "a1", "", categories[0], 1)
    service.add_task(user_b_id, "b1", "", categories[1], 2)
    results_a = service.get_sorted_tasks(user_a_id, "created_desc")
    results_b = service.get_sorted_tasks(user_b_id, "created_desc")
    assert len(results_a) == 1
    assert len(results_b) == 1
    assert results_a[0]["title"] == "a1"
    assert results_b[0]["title"] == "b1"


def test_get_tasks_grouped_by_quadrant(service_ctx):
    service = service_ctx["service"]
    user_a_id = service_ctx["user_a_id"]
    categories = service_ctx["categories"]

    service.add_task(user_a_id, "q1", "", categories[0], 1)
    service.add_task(user_a_id, "q2", "", categories[1], 2)
    service.add_task(user_a_id, "q2b", "", categories[2], 2)

    grouped = service.get_tasks_grouped_by_quadrant(user_a_id)
    assert set(grouped.keys()) == {1, 2, 3, 4}
    assert len(grouped[1]) == 1
    assert len(grouped[2]) == 2
    assert len(grouped[3]) == 0
    assert len(grouped[4]) == 0


def test_get_tasks_grouped_by_category(service_ctx):
    service = service_ctx["service"]
    user_a_id = service_ctx["user_a_id"]
    categories = service_ctx["categories"]

    service.add_task(user_a_id, "work", "", categories[0], 1)
    service.add_task(user_a_id, "study", "", categories[1], 2)
    service.add_task(user_a_id, "life", "", categories[2], 3)

    grouped = service.get_tasks_grouped_by_category(user_a_id)
    assert set(grouped.keys()) == set(categories)
    assert len(grouped[categories[0]]) == 1
    assert len(grouped[categories[1]]) == 1
    assert len(grouped[categories[2]]) == 1
    assert len(grouped[categories[3]]) == 0


def test_clear_all_tasks(service_ctx):
    service = service_ctx["service"]
    user_a_id = service_ctx["user_a_id"]
    user_b_id = service_ctx["user_b_id"]
    categories = service_ctx["categories"]

    service.add_task(user_a_id, "task1", "", categories[0], 1)
    service.add_task(user_a_id, "task2", "", categories[1], 2)
    service.add_task(user_b_id, "other-user", "", categories[0], 1)

    assert len(service.get_all_tasks(user_a_id)) == 2
    assert len(service.get_all_tasks(user_b_id)) == 1

    service.clear_all_tasks(user_a_id)

    assert len(service.get_all_tasks(user_a_id)) == 0
    assert len(service.get_all_tasks(user_b_id)) == 1


def test_verify_token_with_invalid_input(service_ctx):
    service = service_ctx["service"]
    assert service.verify_token("") is None
    assert service.verify_token("not-exists-token") is None


def test_verify_token_with_expired_token(service_ctx):
    service = service_ctx["service"]
    db_path = service_ctx["db_path"]
    user_a_id = service_ctx["user_a_id"]

    expired_token = "expired-token-raw"
    expired_hash = hashlib.sha256(expired_token.encode("utf-8")).hexdigest()

    conn = sqlite3.connect(db_path, uri=True)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO auth_tokens (user_id, token, token_hash, expires_at, created_at)
        VALUES (?, ?, ?, datetime('now', '-1 day'), datetime('now', '-2 day'))
        """,
        (user_a_id, "placeholder", expired_hash),
    )
    conn.commit()
    conn.close()

    assert service.verify_token(expired_token) is None
