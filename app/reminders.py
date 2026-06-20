"""催促スケジューラ（docs/mvp-design.md §5）。

締切基準の逓増催促。理事会の締切ルール(7/5/3日前)・例会の出欠催促を
ポリシーとして表現し、発火時刻を過ぎた未送信ステージのジョブを生成する。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .attendance import aggregate
from .events import resolve_targets
from .models import (
    AttendanceStatus,
    DeliveryJob,
    DeliveryStatus,
    Event,
    EventType,
    ReminderPolicy,
    ReminderStage,
)
from .repository import Repository

DAY = 24 * 60

# 例会出欠の標準催促ポリシー（締切前 7日/3日/1日）
EXAMPLE_MEETING_POLICY = ReminderPolicy(
    policy_id="rp_例会_default",
    event_type=EventType.例会,
    stages=[
        ReminderStage(name="依頼", offset_minutes=-7 * DAY, audience="all", template="req"),
        ReminderStage(name="リマインド", offset_minutes=-3 * DAY, audience="unanswered",
                      template="remind"),
        ReminderStage(name="最終", offset_minutes=-1 * DAY, audience="unanswered",
                      template="final"),
    ],
)

# 理事会の標準催促ポリシー（資料/出欠の締切前 7日/5日/3日: drive-analysis §2）
BOARD_POLICY = ReminderPolicy(
    policy_id="rp_理事会_default",
    event_type=EventType.理事会,
    stages=[
        ReminderStage(name="エントリー", offset_minutes=-7 * DAY, audience="all", template="entry"),
        ReminderStage(name="資料提出", offset_minutes=-5 * DAY, audience="unanswered",
                      template="material"),
        ReminderStage(name="最終", offset_minutes=-3 * DAY, audience="unanswered",
                      template="final"),
    ],
)


def default_policies() -> list[ReminderPolicy]:
    return [EXAMPLE_MEETING_POLICY, BOARD_POLICY]


def fire_time(event: Event, stage: ReminderStage) -> datetime:
    """ステージの発火時刻（締切 + オフセット）。締切未設定なら開催日時を基準。"""
    base = event.attendance_deadline or event.datetime_start
    return base + timedelta(minutes=stage.offset_minutes)


def due_stages(policy: ReminderPolicy, event: Event, now: datetime) -> list[ReminderStage]:
    return [s for s in policy.stages if fire_time(event, s) <= now]


def resolve_audience(repo: Repository, event: Event, audience: str) -> list[str]:
    targets = resolve_targets(repo, event)
    if audience == "all":
        return [m.member_id for m in targets]
    if audience == "unanswered":
        return aggregate(repo, event.event_id).unanswered_member_ids
    if audience == "attendees":
        present = {AttendanceStatus.出席, AttendanceStatus.WEB出席}
        answered = {a.member_id: a.status for a in repo.list_attendances(event.event_id)}
        return [m.member_id for m in targets if answered.get(m.member_id) in present]
    return [m.member_id for m in targets]


def stage_job_id(event_id: str, stage_name: str) -> str:
    """ステージ単位の冪等キー（同一イベント×ステージは一度だけ）。"""
    return f"{event_id}:{stage_name}"


def plan_reminders(repo: Repository, now: datetime) -> list[DeliveryJob]:
    """発火時刻を過ぎた未送信ステージの配信ジョブを生成・保存して返す。"""
    jobs: list[DeliveryJob] = []
    from .models import EventStatus

    for event in repo.list_events(status=EventStatus.open):
        if not event.reminder_policy_id:
            continue
        policy = repo.get_policy(event.reminder_policy_id)
        if policy is None:
            continue
        for stage in due_stages(policy, event, now):
            job_id = stage_job_id(event.event_id, stage.name)
            if repo.get_delivery_job(job_id) is not None:
                continue  # 既に発火済み（冪等）
            targets = resolve_audience(repo, event, stage.audience)
            job = DeliveryJob(
                job_id=job_id,
                type="reminder",
                event_id=event.event_id,
                stage=stage.name,
                targets=targets,
                template_id=stage.template,
                scheduled_at=now,
                status=DeliveryStatus.queued,
                idempotency_key=job_id,
            )
            repo.save_delivery_job(job)
            jobs.append(job)
    return jobs
