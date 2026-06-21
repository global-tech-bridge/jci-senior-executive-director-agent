"""議案ライフサイクルAPI（docs/dashboard-design.md §4.1/§5, F6）。"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from .audit import write_audit
from .deps import get_repo
from .format_check import run_format_check
from .models import (
    Proposal,
    ProposalDeadlines,
    ProposalHistory,
    ProposalStage,
)

router = APIRouter(tags=["proposals"])


def _actor(email: str | None) -> str:
    return email or "unknown"


class ProposalCreate(BaseModel):
    title: str
    number: str | None = None
    committee: str | None = None
    owner_member_id: str | None = None
    event_id: str | None = None
    doc_type: str = "事業計画書"
    content: str | None = None
    storage_uri: str | None = None
    deadlines: ProposalDeadlines = ProposalDeadlines()
    stage: ProposalStage = ProposalStage.entry


class ProposalUpdate(BaseModel):
    title: str | None = None
    number: str | None = None
    committee: str | None = None
    owner_member_id: str | None = None
    event_id: str | None = None
    doc_type: str | None = None
    content: str | None = None
    storage_uri: str | None = None
    deadlines: ProposalDeadlines | None = None


@router.get("/proposals")
def list_proposals(status: str | None = None):
    return get_repo().list_proposals(status=status)


@router.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: str):
    p = get_repo().get_proposal(proposal_id)
    if p is None:
        raise HTTPException(status_code=404, detail="proposal not found")
    return p


@router.post("/proposals")
def create_proposal(
    payload: ProposalCreate,
    x_goog_authenticated_user_email: str | None = Header(default=None),
):
    repo = get_repo()
    now = datetime.now()
    actor = _actor(x_goog_authenticated_user_email)
    proposal = Proposal(
        proposal_id=f"prop_{uuid.uuid4().hex[:10]}",
        **payload.model_dump(),
        history=[ProposalHistory(at=now, stage=payload.stage, by=actor)],
    )
    repo.upsert_proposal(proposal)
    write_audit(
        repo,
        actor=actor,
        action="proposal.create",
        target=proposal.proposal_id,
        detail=proposal.title,
    )
    return proposal


@router.put("/proposals/{proposal_id}")
def update_proposal(proposal_id: str, payload: ProposalUpdate):
    repo = get_repo()
    p = repo.get_proposal(proposal_id)
    if p is None:
        raise HTTPException(status_code=404, detail="proposal not found")
    data = payload.model_dump(exclude_unset=True)
    updated = p.model_copy(update=data)
    repo.upsert_proposal(updated)
    return updated


@router.post("/proposals/{proposal_id}/format-check")
def format_check(proposal_id: str):
    repo = get_repo()
    p = repo.get_proposal(proposal_id)
    if p is None:
        raise HTTPException(status_code=404, detail="proposal not found")
    result = run_format_check(p)
    result.checked_at = datetime.now()
    p.format_check = result
    repo.upsert_proposal(p)
    return result


class StageUpdate(BaseModel):
    stage: ProposalStage


@router.post("/proposals/{proposal_id}/stage")
def set_stage(
    proposal_id: str,
    payload: StageUpdate,
    x_goog_authenticated_user_email: str | None = Header(default=None),
):
    repo = get_repo()
    p = repo.get_proposal(proposal_id)
    if p is None:
        raise HTTPException(status_code=404, detail="proposal not found")
    actor = _actor(x_goog_authenticated_user_email)
    now = datetime.now()
    p.stage = payload.stage
    p.history.append(ProposalHistory(at=now, stage=payload.stage, by=actor))
    repo.upsert_proposal(p)
    write_audit(
        repo, actor=actor, action="proposal.stage",
        target=proposal_id, detail=payload.stage.value,
    )
    return p
