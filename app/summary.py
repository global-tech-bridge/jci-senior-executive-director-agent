"""イベント集計サマリと五役向け通知（docs/mvp-design.md §10/§12）。"""
from __future__ import annotations

from datetime import datetime

from .attendance import aggregate
from .models import (
    AttendanceStatus,
    DeliveryJob,
    DeliveryStatus,
    EventStatus,
)
from .repository import Repository

# サマリ通知先（五役）の役職
OFFICER_ROLES = {"理事長", "直前理事長", "副理事長", "専務理事", "監事"}


def close_event(repo: Repository, event_id: str, *, now: datetime) -> bool:
    event = repo.get_event(event_id)
    if event is None:
        return False
    event.status = EventStatus.closed
    repo.upsert_event(event)
    return True


def officer_member_ids(repo: Repository) -> list[str]:
    return [
        m.member_id
        for m in repo.list_members()
        if m.is_deliverable and m.officer_role in OFFICER_ROLES
    ]


def build_summary_text(repo: Repository, event_id: str) -> str:
    event = repo.get_event(event_id)
    if event is None:
        return "(イベントが見つかりません)"
    s = aggregate(repo, event_id)
    names = {m.member_id: m.name for m in repo.list_members()}
    unanswered = "、".join(names.get(mid, mid) for mid in s.unanswered_member_ids) or "なし"

    c = s.counts
    return (
        f"【出欠集計】{event.title}\n"
        f"対象 {s.total_targets}名 / 回答 {s.answered}名（回答率 "
        f"{round(s.answered / s.total_targets * 100) if s.total_targets else 0}%）\n"
        f"出席 {c.get('出席', 0)} / Web出席 {c.get('Web出席', 0)} / "
        f"欠席 {c.get('欠席', 0)} / 未回答 {c.get('未回答', 0)}\n"
        f"出席率 {round(s.attendance_rate * 100)}%\n"
        f"未回答者: {unanswered}"
    )


def plan_summary_notification(repo: Repository, event_id: str, *, now: datetime) -> DeliveryJob:
    """五役へのサマリ通知ジョブを作成して保存する。"""
    targets = officer_member_ids(repo)
    job = DeliveryJob(
        job_id=f"{event_id}:summary",
        type="summary",
        event_id=event_id,
        stage="summary",
        targets=targets,
        scheduled_at=now,
        status=DeliveryStatus.queued,
    )
    repo.save_delivery_job(job)
    return job


def present_count(repo: Repository, event_id: str) -> int:
    s = aggregate(repo, event_id)
    return s.counts.get(AttendanceStatus.出席.value, 0) + s.counts.get(
        AttendanceStatus.WEB出席.value, 0
    )
