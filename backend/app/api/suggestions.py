# backend/app/api/suggestions.py
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select, func, or_
from ..db import get_session
from ..models.suggestion import RuleSuggestion, RuleSuggestionRead, SuggestionStatus
from ..models.rule import Rule, ActionType
from ..models.account import MailAccount
from .rules import check_rule_conflict

router = APIRouter(prefix="/api/suggestions", tags=["suggestions"])


class SnoozeRequest(BaseModel):
    days: int = 30


class AcceptRequest(BaseModel):
    name: str | None = None
    target: str | None = None


def _get_or_404(suggestion_id: str, session: Session) -> RuleSuggestion:
    obj = session.get(RuleSuggestion, suggestion_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return obj


@router.get("", response_model=list[RuleSuggestionRead])
def list_suggestions(
    status: str | None = None,
    session: Session = Depends(get_session),
):
    if status:
        query = select(RuleSuggestion).where(RuleSuggestion.status == status)
    else:
        query = select(RuleSuggestion).where(
            RuleSuggestion.status == SuggestionStatus.pending
        )
    rows = session.exec(query.order_by(RuleSuggestion.created_at.desc())).all()

    account_ids = {r.account_id for r in rows if r.account_id}
    accounts = {
        a.id: a.name
        for a in session.exec(select(MailAccount).where(MailAccount.id.in_(account_ids))).all()
    } if account_ids else {}

    result = []
    for r in rows:
        data = RuleSuggestionRead.model_validate(r)
        data.account_name = accounts.get(r.account_id) if r.account_id else None
        result.append(data)
    return result


@router.get("/count")
def count_suggestions(session: Session = Depends(get_session)):
    n = session.exec(
        select(func.count(RuleSuggestion.id)).where(
            RuleSuggestion.status == SuggestionStatus.pending
        )
    ).one()
    return {"count": n}


@router.post("/{suggestion_id}/accept", response_model=RuleSuggestionRead)
def accept_suggestion(
    suggestion_id: str,
    body: AcceptRequest = AcceptRequest(),
    session: Session = Depends(get_session),
):
    obj = _get_or_404(suggestion_id, session)
    if obj.status != SuggestionStatus.pending:
        raise HTTPException(status_code=400, detail="Suggestion is not pending")

    max_priority = session.exec(select(func.max(Rule.priority))).one() or 0
    new_priority = (max_priority or 0) + 1

    raw_action = obj.action
    if "." in raw_action:
        raw_action = raw_action.split(".")[-1]
    action_type = ActionType(raw_action)
    effective_target = body.target if body.target is not None else obj.target
    action_params: dict = {}
    if action_type == ActionType.move and effective_target:
        action_params["folder"] = effective_target
    elif action_type == ActionType.paperless and effective_target:
        action_params["folder"] = effective_target

    check_rule_conflict(session, obj.suggested_conditions, action_type.value, action_params, obj.account_id)

    rule = Rule(
        name=body.name if body.name else obj.suggested_rule_name,
        priority=new_priority,
        enabled=True,
        conditions=obj.suggested_conditions,
        action=action_type,
        action_params=action_params,
        account_id=obj.account_id,
    )
    session.add(rule)
    obj.status = SuggestionStatus.accepted
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


@router.post("/{suggestion_id}/snooze", response_model=RuleSuggestionRead)
def snooze_suggestion(
    suggestion_id: str,
    body: SnoozeRequest,
    session: Session = Depends(get_session),
):
    obj = _get_or_404(suggestion_id, session)
    days = body.days
    obj.status = SuggestionStatus.snoozed
    obj.snooze_until = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=days)
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


@router.post("/{suggestion_id}/dismiss", response_model=RuleSuggestionRead)
def dismiss_suggestion(suggestion_id: str, session: Session = Depends(get_session)):
    obj = _get_or_404(suggestion_id, session)
    obj.status = SuggestionStatus.dismissed
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj
