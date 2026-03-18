"""Unit tests for TaskService SQLite behavior."""

import sqlite3
import time
import unittest
from pathlib import Path
from uuid import uuid4

from service import TaskService


class TestTaskServiceSQLite(unittest.TestCase):
    """Validate persistence, CRUD, filtering, searching and sorting behavior."""

    def setUp(self):
        project_root = Path(__file__).resolve().parents[2]
        db_dir = project_root / "tests" / ".tmp"
        db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = str(db_dir / f"test_{uuid4().hex}.db")
        self.service = TaskService(db_path=self.db_path)
        self.categories = self.service.get_categories()

    def tearDown(self):
        db_file = Path(self.db_path)
        if db_file.exists():
            db_file.unlink()

    def test_database_file_and_schema_created(self):
        self.assertTrue(Path(self.db_path).exists())

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'")
        self.assertIsNotNone(cursor.fetchone())

        for index_name in ("idx_tasks_category", "idx_tasks_quadrant", "idx_tasks_created_at"):
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name=?", (index_name,)
            )
            self.assertIsNotNone(cursor.fetchone(), msg=f"Missing index: {index_name}")
        conn.close()

    def test_default_categories_copy_is_isolated(self):
        original = self.service.get_categories()
        original.append("new")
        self.assertEqual(self.service.get_categories(), self.categories)

    def test_add_task_and_get_by_id(self):
        created = self.service.add_task(
            title="Quarterly review",
            description="Prepare KPI summary",
            category=self.categories[0],
            quadrant=1,
        )

        loaded = self.service.get_task_by_id(created["id"])
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["title"], "Quarterly review")
        self.assertEqual(loaded["description"], "Prepare KPI summary")

    def test_validation_errors(self):
        with self.assertRaises(ValueError):
            self.service.add_task("", "", self.categories[0], 1)
        with self.assertRaises(ValueError):
            self.service.add_task("a", "", self.categories[0], 1)
        with self.assertRaises(ValueError):
            self.service.add_task("Valid title", "", "invalid", 1)
        with self.assertRaises(ValueError):
            self.service.add_task("Valid title", "", self.categories[0], 9)

    def test_update_task_success(self):
        task = self.service.add_task("Initial title", "Initial desc", self.categories[1], 2)

        updated = self.service.update_task(
            task_id=task["id"],
            title="Updated title",
            description="Updated desc",
            category=self.categories[2],
            quadrant=4,
        )

        self.assertTrue(updated)
        latest = self.service.get_task_by_id(task["id"])
        self.assertEqual(latest["title"], "Updated title")
        self.assertEqual(latest["description"], "Updated desc")
        self.assertEqual(latest["category"], self.categories[2])
        self.assertEqual(latest["quadrant"], 4)

    def test_update_task_returns_false_when_not_exists(self):
        self.assertFalse(self.service.update_task(task_id=999999, title="new"))

    def test_delete_task_success(self):
        task = self.service.add_task("To delete", "", self.categories[2], 3)
        self.assertTrue(self.service.delete_task(task["id"]))
        self.assertIsNone(self.service.get_task_by_id(task["id"]))

    def test_filter_tasks_by_category_and_quadrant(self):
        self.service.add_task("Task A", "", self.categories[0], 1)
        self.service.add_task("Task B", "", self.categories[0], 2)
        self.service.add_task("Task C", "", self.categories[1], 1)

        filtered = self.service.filter_tasks(category=self.categories[0], quadrant=1)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["title"], "Task A")

    def test_statistics(self):
        self.service.add_task("t1", "", self.categories[0], 1)
        self.service.add_task("t2", "", self.categories[1], 2)
        self.service.add_task("t3", "", self.categories[1], 2)

        stats = self.service.get_statistics()
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["by_category"][self.categories[0]], 1)
        self.assertEqual(stats["by_category"][self.categories[1]], 2)
        self.assertEqual(stats["by_quadrant"][1], 1)
        self.assertEqual(stats["by_quadrant"][2], 2)

    def test_sql_injection_is_blocked(self):
        malicious_title = "test'; DROP TABLE tasks; --"
        self.service.add_task(malicious_title, "", self.categories[0], 1)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tasks")
        count = cursor.fetchone()[0]
        conn.close()
        self.assertEqual(count, 1)

    def test_search_tasks_by_title_and_description(self):
        self.service.add_task("Project report", "Monthly report details", self.categories[0], 1)
        self.service.add_task("Python study", "Online lessons", self.categories[1], 2)

        by_title = self.service.search_tasks("Project")
        by_desc = self.service.search_tasks("lessons")

        self.assertEqual(len(by_title), 1)
        self.assertEqual(by_title[0]["title"], "Project report")
        self.assertEqual(len(by_desc), 1)
        self.assertEqual(by_desc[0]["title"], "Python study")

    def test_search_tasks_empty_keyword_returns_all(self):
        self.service.add_task("task1", "", self.categories[0], 1)
        self.service.add_task("task2", "", self.categories[1], 2)
        self.assertEqual(len(self.service.search_tasks("")), 2)
        self.assertEqual(len(self.service.search_tasks("   ")), 2)

    def test_sort_tasks_created(self):
        t1 = self.service.add_task("task1", "", self.categories[0], 1)
        t2 = self.service.add_task("task2", "", self.categories[0], 1)
        t3 = self.service.add_task("task3", "", self.categories[0], 1)

        desc_ids = [t["id"] for t in self.service.get_sorted_tasks("created_desc")]
        asc_ids = [t["id"] for t in self.service.get_sorted_tasks("created_asc")]

        self.assertEqual(desc_ids, [t3["id"], t2["id"], t1["id"]])
        self.assertEqual(asc_ids, [t1["id"], t2["id"], t3["id"]])

    def test_sort_tasks_updated_desc(self):
        t1 = self.service.add_task("task1", "", self.categories[0], 1)
        t2 = self.service.add_task("task2", "", self.categories[0], 1)

        time.sleep(1.1)
        self.service.update_task(t1["id"], description="updated")

        results = self.service.get_sorted_tasks("updated_desc")
        self.assertEqual(results[0]["id"], t1["id"])
        self.assertEqual(results[1]["id"], t2["id"])

    def test_sort_tasks_invalid_option_falls_back(self):
        self.service.add_task("task1", "", self.categories[0], 1)
        results = self.service.get_sorted_tasks("invalid_option")
        self.assertEqual(len(results), 1)

    def test_get_tasks_grouped_by_quadrant(self):
        self.service.add_task("q1", "", self.categories[0], 1)
        self.service.add_task("q2", "", self.categories[1], 2)
        self.service.add_task("q2b", "", self.categories[2], 2)

        grouped = self.service.get_tasks_grouped_by_quadrant()
        self.assertEqual(set(grouped.keys()), {1, 2, 3, 4})
        self.assertEqual(len(grouped[1]), 1)
        self.assertEqual(len(grouped[2]), 2)
        self.assertEqual(len(grouped[3]), 0)
        self.assertEqual(len(grouped[4]), 0)

    def test_get_tasks_grouped_by_category(self):
        self.service.add_task("work", "", self.categories[0], 1)
        self.service.add_task("study", "", self.categories[1], 2)
        self.service.add_task("life", "", self.categories[2], 3)

        grouped = self.service.get_tasks_grouped_by_category()
        self.assertEqual(set(grouped.keys()), set(self.categories))
        self.assertEqual(len(grouped[self.categories[0]]), 1)
        self.assertEqual(len(grouped[self.categories[1]]), 1)
        self.assertEqual(len(grouped[self.categories[2]]), 1)
        self.assertEqual(len(grouped[self.categories[3]]), 0)

    def test_clear_all_tasks(self):
        self.service.add_task("task1", "", self.categories[0], 1)
        self.service.add_task("task2", "", self.categories[1], 2)
        self.assertEqual(len(self.service.get_all_tasks()), 2)

        self.service.clear_all_tasks()
        self.assertEqual(len(self.service.get_all_tasks()), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
