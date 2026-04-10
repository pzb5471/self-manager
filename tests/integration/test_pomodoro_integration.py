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
def pomodoro_ctx():
    db_dir = project_root / "tests" / "integration" / ".tmp"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / f"pomodoro_{uuid4().hex}.db"

    app = create_app(db_path=str(db_path))
    client = TestClient(app)

    username = f"pomodoro_{uuid4().hex[:8]}"
    assert client.post("/api/auth/register", json={"username": username, "password": "secure123"}).status_code == 200
    login_resp = client.post("/api/auth/login", json={"username": username, "password": "secure123"})
    assert login_resp.status_code == 200

    try:
        yield {"client": client, "headers": auth_headers(login_resp.json()["token"])}
    finally:
        client.close()
        if db_path.exists():
            db_path.unlink()


def test_pomodoro_date_range_statistics(pomodoro_ctx):
    client = pomodoro_ctx["client"]
    headers = pomodoro_ctx["headers"]

    payloads = [
        {"session_type": "work", "duration_minutes": 25, "completed": True, "session_date": "2026-04-08"},
        {"session_type": "work", "duration_minutes": 25, "completed": True, "session_date": "2026-04-09"},
        {"session_type": "short_break", "duration_minutes": 5, "completed": True, "session_date": "2026-04-09"},
        {"session_type": "long_break", "duration_minutes": 15, "completed": False, "session_date": "2026-04-10"},
    ]
    for payload in payloads:
        resp = client.post("/api/pomodoro/sessions", headers=headers, json=payload)
        assert resp.status_code == 200

    stats = client.get("/api/pomodoro/stats?start_date=2026-04-08&end_date=2026-04-10", headers=headers)
    assert stats.status_code == 200
    body = stats.json()

    assert body["summary"]["total_sessions"] == 4
    assert body["summary"]["completed_sessions"] == 3
    assert body["summary"]["focus_sessions"] == 2
    assert body["summary"]["focus_minutes"] == 50
    assert body["by_date"]["2026-04-09"]["focus_count"] == 1
    assert body["by_date"]["2026-04-09"]["focus_minutes"] == 25
    assert body["by_date"]["2026-04-10"]["long_break"]["count"] == 1

