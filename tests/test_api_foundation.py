"""管理サービス基盤(/api・監査ログ・SPA配信)のテスト。"""
import pytest
from fastapi.testclient import TestClient

from app import main
from app.deps import set_repo
from app.models import Member
from app.repository import InMemoryRepository
from tests.conftest import ADMIN_AUTH

client = TestClient(main.app, headers=ADMIN_AUTH)
IAP = {"X-Goog-Authenticated-User-Email": "sed@10to10.co.jp"}


@pytest.fixture(autouse=True)
def repo():
    r = InMemoryRepository()
    r.upsert_member(Member(member_id="m1", name="太郎", line_user_id="U1"))
    set_repo(r)
    yield r
    set_repo(None)


def test_api_alias_works():
    # 同じハンドラが /api でも /admin でも応答
    assert client.get("/api/members").status_code == 200
    assert client.get("/admin/members").status_code == 200


def test_api_is_protected():
    noauth = TestClient(main.app)
    assert noauth.get("/api/members").status_code == 401


def test_iap_header_authorizes():
    iap_client = TestClient(main.app)
    assert iap_client.get("/api/members", headers=IAP).status_code == 200


def test_settings_update_writes_audit(repo):
    body = {
        "kill_switch": True,
        "quiet_hours": {"start": "21:00", "end": "08:00", "tz": "Asia/Tokyo"},
        "rate_limit": {"per_member_per_day": 3, "global_per_min": 30},
    }
    res = client.put("/api/settings", json=body, headers=IAP)
    assert res.status_code == 200
    logs = repo.list_audit()
    assert any(a.action == "settings.update" and a.actor == "sed@10to10.co.jp" for a in logs)
    # 監査API
    assert client.get("/api/audit-logs").status_code == 200
