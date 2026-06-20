"""イベントと対象者解決（docs/mvp-design.md §3/§4.2）。"""
from __future__ import annotations

from .models import Event, Member, TargetScopeKind
from .repository import Repository


def resolve_targets(repo: Repository, event: Event) -> list[Member]:
    """イベントの対象範囲から配信対象の会員一覧を返す（配信可能な会員のみ）。"""
    members = [m for m in repo.list_members() if m.is_deliverable]
    scope = event.target_scope

    if scope.kind == TargetScopeKind.all:
        return members
    if scope.kind == TargetScopeKind.committee:
        return [m for m in members if m.committee in scope.value]
    if scope.kind == TargetScopeKind.officer:
        return [m for m in members if m.officer_role in scope.value]
    if scope.kind == TargetScopeKind.custom:
        return [m for m in members if m.member_id in scope.value]
    return members
