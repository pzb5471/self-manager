"""Unit tests for TaskService authentication and per-user SQLite behavior."""

import sqlite3
import time
import unittest
import hashlib
from pathlib import Path
from uuid import uuid4

from service import TaskService


class TestTaskServiceSQLite(unittest.TestCase):
    """Validate auth flow, per-user isolation and task behavior."""

    def setUp(self):
        project_root = Path(__file__).resolve().parents[2]
        db_dir = project_root / "tests" / ".tmp"
        db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = str(db_dir / f"test_{uuid4().hex}.db")
        self.service = TaskService(db_path=self.db_path)

        self.user_a = self.service.register_user("alice", "alice123")
        self.user_b = self.service.register_user("bob", "bob12345")

        login_a = self.service.login_user("alice", "alice123")
        login_b = self.service.login_user("bob", "bob12345")
        self.assertIsNotNone(login_a)
        self.assertIsNotNone(login_b)

        self.token_a = login_a["token"]
        self.token_b = login_b["token"]

        self.user_a_id = self.user_a["id"]
        self.user_b_id = self.user_b["id"]
        self.categories = self.service.get_categories()

    def tearDown(self):
        db_file = Path(self.db_path)
        if db_file.exists():
            db_file.unlink()

    def test_database_file_and_schema_created(self):
        self.assertTrue(Path(self.db_path).exists())

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for table_name in ("tasks", "users", "auth_tokens"):
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
            )
            self.assertIsNotNone(cursor.fetchone(), msg=f"Missing table: {table_name}")

        for index_name in (
            "idx_tasks_category",
            "idx_tasks_quadrant",
            "idx_tasks_created_at",
            "idx_tasks_user_id",
            "idx_auth_tokens_token",
            "idx_auth_tokens_token_hash",
        ):
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?", (index_name,)
            )
            self.assertIsNotNone(cursor.fetchone(), msg=f"Missing index: {index_name}")
        conn.close()

    def test_register_duplicate_user_rejected(self):
        with self.assertRaises(ValueError):
            self.service.register_user("alice", "anotherpass")

    def test_login_verify_and_logout(self):
        verified = self.service.verify_token(self.token_a)
        self.assertIsNotNone(verified)
        self.assertEqual(verified["username"], "alice")

        self.assertTrue(self.service.logout(self.token_a))
        self.assertIsNone(self.service.verify_token(self.token_a))

    def test_auth_token_stores_hash_not_plaintext(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT token, token_hash FROM auth_tokens WHERE user_id = ?", (self.user_a_id,))
        row = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertNotEqual(row[0], self.token_a)
        self.assertEqual(row[1], hashlib.sha256(self.token_a.encode("utf-8")).hexdigest())

    def test_legacy_tasks_not_auto_claimed_on_login(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tasks (user_id, title, description, category, quadrant, created_at, updated_at)
            VALUES (NULL, 'legacy task', '', ?, 1, datetime('now'), datetime('now'))
            """,
            (self.categories[0],),
        )
        conn.commit()
        conn.close()

        # Re-login should not auto-claim legacy rows.
        self.assertIsNotNone(self.service.login_user("alice", "alice123"))

        tasks_a = self.service.get_all_tasks(self.user_a_id)
        tasks_b = self.service.get_all_tasks(self.user_b_id)
        self.assertFalse(any(t["title"] == "legacy task" for t in tasks_a))
        self.assertFalse(any(t["title"] == "legacy task" for t in tasks_b))

    def test_add_task_and_get_by_id(self):
        created = self.service.add_task(
            user_id=self.user_a_id,
            title="Quarterly review",
            description="Prepare KPI summary",
            category=self.categories[0],
            quadrant=1,
        )

        loaded = self.service.get_task_by_id(created["id"], self.user_a_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["title"], "Quarterly review")
        self.assertEqual(loaded["description"], "Prepare KPI summary")
        self.assertEqual(loaded["user_id"], self.user_a_id)

    def test_user_isolation_between_tasks(self):
        task_a = self.service.add_task(self.user_a_id, "A task", "", self.categories[0], 1)
        self.service.add_task(self.user_b_id, "B task", "", self.categories[1], 2)

        list_a = self.service.get_all_tasks(self.user_a_id)
        list_b = self.service.get_all_tasks(self.user_b_id)

        self.assertEqual(len(list_a), 1)
        self.assertEqual(len(list_b), 1)
        self.assertEqual(list_a[0]["title"], "A task")
        self.assertEqual(list_b[0]["title"], "B task")

        # Cross-user read is blocked.
        self.assertIsNone(self.service.get_task_by_id(task_a["id"], self.user_b_id))

    def test_validation_errors(self):
        with self.assertRaises(ValueError):
            self.service.add_task(self.user_a_id, "", "", self.categories[0], 1)
        with self.assertRaises(ValueError):
            self.service.add_task(self.user_a_id, "a", "", self.categories[0], 1)
        with self.assertRaises(ValueError):
            self.service.add_task(self.user_a_id, "Valid title", "", "invalid", 1)
        with self.assertRaises(ValueError):
            self.service.add_task(self.user_a_id, "Valid title", "", self.categories[0], 9)
        with self.assertRaises(ValueError):
            self.service.add_task(0, "Valid title", "", self.categories[0], 1)

    def test_update_task_success(self):
        task = self.service.add_task(self.user_a_id, "Initial title", "Initial desc", self.categories[1], 2)

        updated = self.service.update_task(
            task_id=task["id"],
            user_id=self.user_a_id,
            title="Updated title",
            description="Updated desc",
            category=self.categories[2],
            quadrant=4,
        )

        self.assertTrue(updated)
        latest = self.service.get_task_by_id(task["id"], self.user_a_id)
        self.assertEqual(latest["title"], "Updated title")
        self.assertEqual(latest["description"], "Updated desc")
        self.assertEqual(latest["category"], self.categories[2])
        self.assertEqual(latest["quadrant"], 4)

    def test_update_task_returns_false_when_not_exists_or_not_owner(self):
        self.assertFalse(self.service.update_task(task_id=999999, user_id=self.user_a_id, title="new"))

        task = self.service.add_task(self.user_a_id, "Owned by A", "", self.categories[0], 1)
        self.assertFalse(self.service.update_task(task_id=task["id"], user_id=self.user_b_id, title="hijack"))

    def test_delete_task_success(self):
        task = self.service.add_task(self.user_a_id, "To delete", "", self.categories[2], 3)
        self.assertTrue(self.service.delete_task(task["id"], self.user_a_id))
        self.assertIsNone(self.service.get_task_by_id(task["id"], self.user_a_id))

    def test_delete_task_not_owner(self):
        task = self.service.add_task(self.user_a_id, "Keep me", "", self.categories[0], 1)
        self.assertFalse(self.service.delete_task(task["id"], self.user_b_id))

    def test_filter_tasks_by_category_and_quadrant(self):
        self.service.add_task(self.user_a_id, "Task A", "", self.categories[0], 1)
        self.service.add_task(self.user_a_id, "Task B", "", self.categories[0], 2)
        self.service.add_task(self.user_a_id, "Task C", "", self.categories[1], 1)

        filtered = self.service.filter_tasks(user_id=self.user_a_id, category=self.categories[0], quadrant=1)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["title"], "Task A")

    def test_statistics(self):
        self.service.add_task(self.user_a_id, "t1", "", self.categories[0], 1)
        self.service.add_task(self.user_a_id, "t2", "", self.categories[1], 2)
        self.service.add_task(self.user_a_id, "t3", "", self.categories[1], 2)
        self.service.add_task(self.user_b_id, "t4", "", self.categories[1], 2)

        stats = self.service.get_statistics(self.user_a_id)
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["by_category"][self.categories[0]], 1)
        self.assertEqual(stats["by_category"][self.categories[1]], 2)
        self.assertEqual(stats["by_quadrant"][1], 1)
        self.assertEqual(stats["by_quadrant"][2], 2)

    def test_sql_injection_is_blocked(self):
        malicious_title = "test'; DROP TABLE tasks; --"
        self.service.add_task(self.user_a_id, malicious_title, "", self.categories[0], 1)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tasks")
        count = cursor.fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)

    def test_search_tasks_by_title_and_description(self):
        self.service.add_task(self.user_a_id, "Project report", "Monthly report details", self.categories[0], 1)
        self.service.add_task(self.user_a_id, "Python study", "Online lessons", self.categories[1], 2)
        self.service.add_task(self.user_b_id, "Project hidden", "Not visible", self.categories[0], 1)

        by_title = self.service.search_tasks(self.user_a_id, "Project")
        by_desc = self.service.search_tasks(self.user_a_id, "lessons")

        self.assertEqual(len(by_title), 1)
        self.assertEqual(by_title[0]["title"], "Project report")
        self.assertEqual(len(by_desc), 1)
        self.assertEqual(by_desc[0]["title"], "Python study")

    def test_search_tasks_empty_keyword_returns_all(self):
        self.service.add_task(self.user_a_id, "task1", "", self.categories[0], 1)
        self.service.add_task(self.user_a_id, "task2", "", self.categories[1], 2)
        self.assertEqual(len(self.service.search_tasks(self.user_a_id, "")), 2)
        self.assertEqual(len(self.service.search_tasks(self.user_a_id, "   ")), 2)

    def test_sort_tasks_created(self):
        t1 = self.service.add_task(self.user_a_id, "task1", "", self.categories[0], 1)
        t2 = self.service.add_task(self.user_a_id, "task2", "", self.categories[0], 1)
        t3 = self.service.add_task(self.user_a_id, "task3", "", self.categories[0], 1)

        desc_ids = [t["id"] for t in self.service.get_sorted_tasks(self.user_a_id, "created_desc")]
        asc_ids = [t["id"] for t in self.service.get_sorted_tasks(self.user_a_id, "created_asc")]

        self.assertEqual(desc_ids, [t3["id"], t2["id"], t1["id"]])
        self.assertEqual(asc_ids, [t1["id"], t2["id"], t3["id"]])

    def test_sort_tasks_updated_desc(self):
        t1 = self.service.add_task(self.user_a_id, "task1", "", self.categories[0], 1)
        t2 = self.service.add_task(self.user_a_id, "task2", "", self.categories[0], 1)

        time.sleep(1.1)
        self.service.update_task(t1["id"], self.user_a_id, description="updated")

        results = self.service.get_sorted_tasks(self.user_a_id, "updated_desc")
        self.assertEqual(results[0]["id"], t1["id"])
        self.assertEqual(results[1]["id"], t2["id"])

    def test_sort_tasks_invalid_option_falls_back(self):
        self.service.add_task(self.user_a_id, "task1", "", self.categories[0], 1)
        results = self.service.get_sorted_tasks(self.user_a_id, "invalid_option")
        self.assertEqual(len(results), 1)

    def test_sort_tasks_isolation(self):
        self.service.add_task(self.user_a_id, "a1", "", self.categories[0], 1)
        self.service.add_task(self.user_b_id, "b1", "", self.categories[1], 2)
        results_a = self.service.get_sorted_tasks(self.user_a_id, "created_desc")
        results_b = self.service.get_sorted_tasks(self.user_b_id, "created_desc")
        self.assertEqual(len(results_a), 1)
        self.assertEqual(len(results_b), 1)
        self.assertEqual(results_a[0]["title"], "a1")
        self.assertEqual(results_b[0]["title"], "b1")

    def test_get_tasks_grouped_by_quadrant(self):
        self.service.add_task(self.user_a_id, "q1", "", self.categories[0], 1)
        self.service.add_task(self.user_a_id, "q2", "", self.categories[1], 2)
        self.service.add_task(self.user_a_id, "q2b", "", self.categories[2], 2)

        grouped = self.service.get_tasks_grouped_by_quadrant(self.user_a_id)
        self.assertEqual(set(grouped.keys()), {1, 2, 3, 4})
        self.assertEqual(len(grouped[1]), 1)
        self.assertEqual(len(grouped[2]), 2)
        self.assertEqual(len(grouped[3]), 0)
        self.assertEqual(len(grouped[4]), 0)

    def test_get_tasks_grouped_by_category(self):
        self.service.add_task(self.user_a_id, "work", "", self.categories[0], 1)
        self.service.add_task(self.user_a_id, "study", "", self.categories[1], 2)
        self.service.add_task(self.user_a_id, "life", "", self.categories[2], 3)

        grouped = self.service.get_tasks_grouped_by_category(self.user_a_id)
        self.assertEqual(set(grouped.keys()), set(self.categories))
        self.assertEqual(len(grouped[self.categories[0]]), 1)
        self.assertEqual(len(grouped[self.categories[1]]), 1)
        self.assertEqual(len(grouped[self.categories[2]]), 1)
        self.assertEqual(len(grouped[self.categories[3]]), 0)

    def test_clear_all_tasks(self):
        self.service.add_task(self.user_a_id, "task1", "", self.categories[0], 1)
        self.service.add_task(self.user_a_id, "task2", "", self.categories[1], 2)
        self.service.add_task(self.user_b_id, "other-user", "", self.categories[0], 1)
        self.assertEqual(len(self.service.get_all_tasks(self.user_a_id)), 2)
        self.assertEqual(len(self.service.get_all_tasks(self.user_b_id)), 1)

        self.service.clear_all_tasks(self.user_a_id)
        self.assertEqual(len(self.service.get_all_tasks(self.user_a_id)), 0)
        self.assertEqual(len(self.service.get_all_tasks(self.user_b_id)), 1)

    def test_verify_token_with_invalid_input(self):
        self.assertIsNone(self.service.verify_token(""))
        self.assertIsNone(self.service.verify_token("not-exists-token"))

    def test_verify_token_with_expired_token(self):
        expired_token = "expired-token-raw"
        expired_hash = hashlib.sha256(expired_token.encode("utf-8")).hexdigest()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO auth_tokens (user_id, token, token_hash, expires_at, created_at)
            VALUES (?, ?, ?, datetime('now', '-1 day'), datetime('now', '-2 day'))
            """,
            (self.user_a_id, "placeholder", expired_hash),
        )
        conn.commit()
        conn.close()

        self.assertIsNone(self.service.verify_token(expired_token))


if __name__ == "__main__":
    unittest.main(verbosity=2)
