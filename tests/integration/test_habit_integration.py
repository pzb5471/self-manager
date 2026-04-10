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
def habit_ctx():
    db_dir = project_root / "tests" / "integration" / ".tmp"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / f"habit_{uuid4().hex}.db"

    app = create_app(db_path=str(db_path))
    client = TestClient(app)

    username = f"habit_{uuid4().hex[:8]}"
    assert client.post("/api/auth/register", json={"username": username, "password": "secure123"}).status_code == 200
    login_resp = client.post("/api/auth/login", json={"username": username, "password": "secure123"})
    assert login_resp.status_code == 200

    try:
        yield {"client": client, "headers": auth_headers(login_resp.json()["token"])}
    finally:
        client.close()
        if db_path.exists():
            db_path.unlink()


def test_habit_page_workflow_builds_records_and_achievements(habit_ctx):
    client = habit_ctx["client"]
    headers = habit_ctx["headers"]

    for date in ("2026-04-07", "2026-04-08", "2026-04-09"):
        for period in ("morning", "noon", "evening"):
            resp = client.post("/api/habits/checkins", headers=headers, json={"period": period, "checkin_date": date})
            assert resp.status_code == 200

    for minutes in (20, 25, 35, 40, 45):
        resp = client.post(
            "/api/habits/phone-focus",
            headers=headers,
            json={"duration_minutes": minutes, "note": f"focus {minutes}", "resisted_at": "2026-04-09 18:00"},
        )
        assert resp.status_code == 200

    dashboard = client.get("/api/habits/dashboard?today=2026-04-09", headers=headers)
    assert dashboard.status_code == 200
    body = dashboard.json()

    assert body["summary"]["checkin_days"] == 3
    assert body["summary"]["full_day_streak"] == 3
    assert body["summary"]["total_phone_sessions"] == 5
    assert body["summary"]["total_phone_minutes"] == 165

    achievements = {item["key"]: item for item in body["achievements"]}
    assert achievements["steady_worker"]["unlocked"] is True
    assert achievements["phone_hour"]["unlocked"] is True
    assert achievements["phone_guard"]["unlocked"] is True
    assert achievements["discipline_master"]["unlocked"] is True
