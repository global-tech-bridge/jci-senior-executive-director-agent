"""管理APIのユニットテスト（TestClient + InMemoryRepository）。"""
import pytest
from fastapi.testclient import TestClient

from app import main
from app.deps import set_repo
from app.models import AttendanceStatus, Member
from app.repository import InMemoryRepository

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def repo():
    r = InMemoryRepository()
    r.upsert_member(Member(member_id="m1", name="太郎", line_user_id="U1", committee="総務委員会"))
    r.upsert_member(Member(member_id="m2", name="次郎", line_user_id="U2", committee="総務委員会"))
    set_repo(r)
    yield r
    set_repo(None)


def create_event(**over):
    payload = {
        "type": "例会",
        "title": "6月例会",
        "datetime_start": "2026-06-25T19:00:00",
        "location": "会館",
        "target_scope": {"kind": "all", "value": []},
        "status": "open",
    }
    payload.update(over)
    res = client.post("/admin/events", json=payload)
    assert res.status_code == 200
    return res.json()


def test_create_and_get_event():
    ev = create_event()
    assert ev["event_id"].startswith("ev_")
    res = client.get(f"/admin/events/{ev['event_id']}")
    assert res.status_code == 200
    body = res.json()
    assert body["summary"]["total_targets"] == 2
    assert body["summary"]["unanswered"] == 2


def test_list_events():
    create_event()
    create_event(title="理事会", type="理事会")
    res = client.get("/admin/events")
    assert len(res.json()) == 2


def test_update_attendance_and_summary():
    ev = create_event()
    eid = ev["event_id"]
    res = client.put(
        f"/admin/events/{eid}/attendances/m1",
        json={"status": AttendanceStatus.出席.value},
    )
    assert res.status_code == 200
    summary = client.get(f"/admin/events/{eid}/attendances").json()["summary"]
    assert summary["answered"] == 1
    assert summary["attendance_rate"] == 0.5


def test_csv_export():
    ev = create_event()
    eid = ev["event_id"]
    client.put(f"/admin/events/{eid}/attendances/m1", json={"status": "出席"})
    res = client.get(f"/admin/events/{eid}/attendances.csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "m1" in res.text and "出席" in res.text


def test_manual_remind_targets_unanswered():
    ev = create_event()
    eid = ev["event_id"]
    client.put(f"/admin/events/{eid}/attendances/m1", json={"status": "出席"})
    res = client.post(f"/admin/events/{eid}/remind")
    assert res.status_code == 200
    assert res.json()["targets"] == ["m2"]


def test_settings_get_put():
    assert client.get("/admin/settings").json()["kill_switch"] is False
    res = client.put("/admin/settings", json={"kill_switch": True})
    assert res.status_code == 200
    assert client.get("/admin/settings").json()["kill_switch"] is True


def test_members_and_invite():
    assert len(client.get("/admin/members").json()) == 2
    res = client.post("/admin/members/m1/invite")
    assert res.status_code == 200
    assert res.json()["member_id"] == "m1"
    assert len(res.json()["code"]) == 8
    # 存在しない会員
    assert client.post("/admin/members/zzz/invite").status_code == 404


def test_event_not_found():
    assert client.get("/admin/events/nope").status_code == 404
