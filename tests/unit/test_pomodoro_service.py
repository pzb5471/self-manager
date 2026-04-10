import sqlite3
import sys
from pathlib import Path
from uuid import uuid4

import pytest

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from service import TaskService


pytestmark = pytest.mark.unit


@pytest.fixture
def pomodoro_service():
    db_path = f"file:pomodoro_service_{uuid4().hex}?mode=memory&cache=shared"
    service = TaskService(db_path=db_path)
    user = service.register_user("pomodoro_user", "secure123")
    try:
        yield service, user["id"], db_path
    finally:
        service.close()


def test_pomodoro_schema_created(pomodoro_service):
    _, _, db_path = pomodoro_service
    conn = sqlite3.connect(db_path, uri=True)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pomodoro_sessions'")
    assert cursor.fetchone() is not None

    for index_name in ("idx_pomodoro_sessions_user_date", "idx_pomodoro_sessions_user_type"):
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name=?", (index_name,))
        assert cursor.fetchone() is not None
    conn.close()


def test_record_and_list_pomodoro_sessions(pomodoro_service):
    service, user_id, _ = pomodoro_service

    work = service.record_pomodoro_session(user_id, "work", 25, completed=True, session_date="2026-04-10", note="deep work")
    short_break = service.record_pomodoro_session(user_id, "short_break", 5, completed=True, session_date="2026-04-10")
    long_break = service.record_pomodoro_session(user_id, "long_break", 15, completed=False, session_date="2026-04-10")

    assert work["session_type"] == "work"
    assert short_break["duration_minutes"] == 5
    assert long_break["completed"] is False

    items = service.list_pomodoro_sessions(user_id, start_date="2026-04-10", end_date="2026-04-10")
    assert len(items) == 3
    assert {item["session_type"] for item in items} == {"work", "short_break", "long_break"}


def test_pomodoro_stats_focus_work_sessions_only(pomodoro_service):
    service, user_id, _ = pomodoro_service

    sessions = [
        ("work", 25, True, "2026-04-08", "task A"),
        ("work", 25, False, "2026-04-08", "task B"),
        ("short_break", 5, True, "2026-04-08", ""),
        ("long_break", 15, True, "2026-04-09", ""),
    ]
    for session_type, duration, completed, date, note in sessions:
        service.record_pomodoro_session(user_id, session_type, duration, completed=completed, session_date=date, note=note)

    stats = service.get_pomodoro_stats(user_id, start_date="2026-04-08", end_date="2026-04-09")

    assert stats["summary"]["total_sessions"] == 4
    assert stats["summary"]["completed_sessions"] == 3
    assert stats["summary"]["focus_sessions"] == 1
    assert stats["summary"]["focus_minutes"] == 25
    assert stats["by_type"]["work"]["count"] == 2
    assert stats["by_type"]["work"]["completed"] == 1
    assert stats["by_date"]["2026-04-08"]["work"]["count"] == 2
    assert stats["by_date"]["2026-04-08"]["work"]["completed_count"] == 1
    assert stats["by_date"]["2026-04-08"]["work"]["completed_minutes"] == 25


def test_pomodoro_invalid_range_rejected(pomodoro_service):
    service, user_id, _ = pomodoro_service

    with pytest.raises(ValueError):
        service.list_pomodoro_sessions(user_id, start_date="2026-04-10", end_date="2026-04-09")

