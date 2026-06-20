"""管理ダッシュボードのユニットテスト。"""
from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)  # 認証ヘッダなし（/dashboard は公開）


def test_dashboard_public_html():
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    body = res.text
    assert "管理ダッシュボード" in body
    # 管理操作はクライアントからトークンヘッダで叩く設計
    assert "X-Admin-Token" in body
    # 秘密値は埋め込まない
    assert "test-admin-secret" not in body


def test_dashboard_not_behind_guard():
    # /admin は 401 だが /dashboard は公開
    assert client.get("/admin/members").status_code == 401
    assert client.get("/dashboard").status_code == 200
