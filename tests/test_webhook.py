"""M0 LINE Webhook 疎通のユニットテスト。"""
import base64
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from app import main
from tests.conftest import TEST_CHANNEL_SECRET

client = TestClient(main.app)


def sign(body: str) -> str:
    digest = hmac.new(TEST_CHANNEL_SECRET.encode(), body.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _event_envelope(event: dict) -> str:
    return json.dumps({"destination": "Xdummy", "events": [event]})


FOLLOW_EVENT = {
    "type": "follow",
    "mode": "active",
    "timestamp": 1700000000000,
    "source": {"type": "user", "userId": "U_test_user"},
    "replyToken": "reply-token-follow",
    "webhookEventId": "evt-1",
    "deliveryContext": {"isRedelivery": False},
    "follow": {"isUnblocked": True},  # LINE SDK v3 で FollowEvent に必須
}

MESSAGE_EVENT = {
    "type": "message",
    "mode": "active",
    "timestamp": 1700000000000,
    "source": {"type": "user", "userId": "U_test_user"},
    "replyToken": "reply-token-msg",
    "webhookEventId": "evt-2",
    "deliveryContext": {"isRedelivery": False},
    "message": {"type": "text", "id": "msg-1", "text": "こんにちは", "quoteToken": "qt-1"},
}


def test_root():
    res = client.get("/")
    assert res.status_code == 200
    assert res.json()["service"] == "jci-sed-agent"


def test_healthz():
    res = client.get("/healthz")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["channel_secret_loaded"] is True
    # conftest はトークンを PLACEHOLDER にしているため未ロード扱い
    assert body["access_token_loaded"] is False


def test_webhook_rejects_invalid_signature():
    body = _event_envelope(FOLLOW_EVENT)
    res = client.post(
        "/line/webhook",
        content=body,
        headers={"X-Line-Signature": "invalid"},
    )
    assert res.status_code == 400


def test_webhook_follow_triggers_welcome(monkeypatch):
    captured = []
    monkeypatch.setattr(main, "reply", lambda token, text: captured.append((token, text)) or True)

    body = _event_envelope(FOLLOW_EVENT)
    res = client.post(
        "/line/webhook",
        content=body,
        headers={"X-Line-Signature": sign(body)},
    )
    assert res.status_code == 200
    assert len(captured) == 1
    token, text = captured[0]
    assert token == "reply-token-follow"
    assert "招待コード" in text


def test_webhook_message_echo_for_linked_member(monkeypatch):
    from app.models import Member
    from app.repository import InMemoryRepository

    repo = InMemoryRepository()
    repo.upsert_member(Member(member_id="m1", name="猪苗代 太郎", line_user_id="U_test_user"))
    monkeypatch.setattr(main, "get_repo", lambda: repo)

    captured = []
    monkeypatch.setattr(main, "reply", lambda token, text: captured.append((token, text)) or True)

    body = _event_envelope(MESSAGE_EVENT)
    res = client.post(
        "/line/webhook",
        content=body,
        headers={"X-Line-Signature": sign(body)},
    )
    assert res.status_code == 200
    assert len(captured) == 1
    token, text = captured[0]
    assert token == "reply-token-msg"
    assert "こんにちは" in text
    assert "猪苗代 太郎" in text


def test_webhook_message_unlinked_user_treated_as_code(monkeypatch):
    from app.repository import InMemoryRepository

    repo = InMemoryRepository()  # コード未登録 → 無効扱い
    monkeypatch.setattr(main, "get_repo", lambda: repo)

    captured = []
    monkeypatch.setattr(main, "reply", lambda token, text: captured.append((token, text)) or True)

    body = _event_envelope(MESSAGE_EVENT)
    res = client.post(
        "/line/webhook",
        content=body,
        headers={"X-Line-Signature": sign(body)},
    )
    assert res.status_code == 200
    assert "無効" in captured[0][1]


def test_reply_skips_when_token_placeholder():
    # PLACEHOLDER のときは送信せず False
    assert main.reply("rt", "test") is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
