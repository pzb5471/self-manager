import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from service import TaskService
import service as service_module


pytestmark = pytest.mark.unit


@pytest.fixture
def habit_service():
    db_path = f"file:habit_service_{uuid4().hex}?mode=memory&cache=shared"
    service = TaskService(db_path=db_path)
    user = service.register_user("habit_user", "secure123")
    try:
        yield service, user["id"]
    finally:
        service.close()


def test_workstation_checkins_are_recorded_and_deduplicated(habit_service):
    service, user_id = habit_service

    morning = service.record_workstation_checkin(user_id, "morning", "2026-04-09")
    noon = service.record_workstation_checkin(user_id, "noon", "2026-04-09")

    assert morning["period"] == "morning"
    assert noon["period"] == "noon"
    items = service.list_workstation_checkins(user_id, days=1, end_date="2026-04-09")
    assert [item["period"] for item in items] == ["noon", "morning"]

    with pytest.raises(ValueError):
        service.record_workstation_checkin(user_id, "morning", "2026-04-09")


def test_workstation_checkin_defaults_to_local_time(habit_service, monkeypatch):
    service, user_id = habit_service

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            local_tz = timezone(timedelta(hours=8))
            current = cls(2026, 4, 14, 0, 30, 15, tzinfo=local_tz)
            return current if tz is None else current.astimezone(tz)

    monkeypatch.setattr(service_module, "datetime", FrozenDateTime)

    record = service.record_workstation_checkin(user_id, "morning")

    assert record["checkin_date"] == "2026-04-14"
    assert record["created_at"] == "2026-04-14 00:30:15"


def test_phone_focus_records_and_user_isolation(habit_service):
    service, user_id = habit_service
    other = service.register_user("other_habit", "secure123")

    focus = service.record_phone_focus(
        user_id,
        duration_minutes=45,
        note="focus on weekly report",
        resisted_at="2026-04-09 14:30",
    )
    assert focus["duration_minutes"] == 45
    assert focus["note"] == "focus on weekly report"

    own_items = service.list_phone_focus_records(user_id, days=1, end_date="2026-04-09")
    other_items = service.list_phone_focus_records(other["id"], days=1, end_date="2026-04-09")
    assert len(own_items) == 1
    assert other_items == []


def test_habit_dashboard_computes_achievements_and_streak(habit_service):
    service, user_id = habit_service

    for date in ("2026-04-07", "2026-04-08", "2026-04-09"):
        for period in ("morning", "noon", "evening"):
            service.record_workstation_checkin(user_id, period, date)

    service.record_phone_focus(user_id, 30, "first focus", "2026-04-08 10:00")
    service.record_phone_focus(user_id, 40, "second focus", "2026-04-09 16:00")

    dashboard = service.get_habit_dashboard(user_id, today="2026-04-09")

    assert dashboard["today"]["periods"] == {"morning": True, "noon": True, "evening": True}
    assert dashboard["summary"]["checkin_days"] == 3
    assert dashboard["summary"]["full_day_count"] == 3
    assert dashboard["summary"]["full_day_streak"] == 3
    assert dashboard["summary"]["total_phone_minutes"] == 70

    achievements = {item["key"]: item for item in dashboard["achievements"]}
    assert achievements["first_checkin"]["unlocked"] is True
    assert achievements["full_day"]["unlocked"] is True
    assert achievements["steady_worker"]["unlocked"] is True
    assert achievements["phone_hour"]["unlocked"] is True
    assert achievements["discipline_master"]["unlocked"] is True
