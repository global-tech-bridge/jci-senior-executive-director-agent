"""連携済みメンバーの対話応答のユニットテスト。"""
from datetime import datetime

from app.member_menu import handle_member_text
from app.models import (
    AttendanceStatus,
    Event,
    EventStatus,
    EventType,
    Member,
    TargetScope,
    TargetScopeKind,
)
from app.repository import InMemoryRepository

NOW = datetime(2026, 6, 20, 10, 0)


def setup():
    repo = InMemoryRepository()
    member = Member(member_id="m1", name="太郎", line_user_id="U1")
    repo.upsert_member(member)
    repo.upsert_event(Event(
        event_id="e1", type=EventType.例会, title="6月例会",
        datetime_start=datetime(2026, 6, 25, 19, 0), location="会館",
        attendance_deadline=datetime(2026, 6, 25, 23, 59),
        target_scope=TargetScope(kind=TargetScopeKind.all),
        status=EventStatus.open,
    ))
    return repo, member


def test_schedule_query():
    repo, member = setup()
    msgs = handle_member_text(repo, member, "次回の予定", now=NOW)
    assert "6月例会" in msgs[0].text
    assert "会館" in msgs[0].text


def test_my_attendance_unanswered():
    repo, member = setup()
    msgs = handle_member_text(repo, member, "自分の出欠状況", now=NOW)
    assert "未回答" in msgs[0].text


def test_my_attendance_after_answer():
    repo, member = setup()
    from app.attendance import record_attendance
    record_attendance(repo, "e1", "m1", AttendanceStatus.出席, now=NOW)
    msgs = handle_member_text(repo, member, "自分の出欠状況", now=NOW)
    assert "出席" in msgs[0].text


def test_answer_prompt_returns_attendance_request():
    repo, member = setup()
    msgs = handle_member_text(repo, member, "出欠を回答", now=NOW)
    labels = [i.action.label for i in msgs[0].quick_reply.items]
    assert labels == ["出席", "Web出席", "欠席"]


def test_contact_records_escalation():
    repo, member = setup()
    msgs = handle_member_text(repo, member, "事務局に連絡", now=NOW)
    assert "受け付け" in msgs[0].text
    escalations = repo.list_escalations()
    assert len(escalations) == 1
    assert escalations[0].member_id == "m1"


def test_menu_postback_value():
    repo, member = setup()
    msgs = handle_member_text(repo, member, "menu|次回の予定", now=NOW)
    assert "6月例会" in msgs[0].text


def test_unknown_input_shows_menu():
    repo, member = setup()
    msgs = handle_member_text(repo, member, "ありがとう", now=NOW)
    assert msgs[0].quick_reply is not None


def test_menu_keyword():
    repo, member = setup()
    msgs = handle_member_text(repo, member, "メニュー", now=NOW)
    labels = [i.action.label for i in msgs[0].quick_reply.items]
    assert "次回の予定" in labels and "事務局に連絡" in labels
