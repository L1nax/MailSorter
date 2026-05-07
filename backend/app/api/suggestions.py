# backend/app/api/suggestions.py
from __future__ import annotations
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select, func, or_
from ..db import get_session
from ..models.suggestion import RuleSuggestion, RuleSuggestionRead, SuggestionStatus
from ..models.rule import Rule, ActionType

router = APIRouter(prefix="/api/suggestions", tags=["suggestions"])


class SnoozeRequest(BaseModel):
    days: int = 30


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
    return session.exec(query.order_by(RuleSuggestion.created_at.desc())).all()


@router.get("/count")
def count_suggestions(session: Session = Depends(get_session)):
    n = session.exec(
        select(func.count(RuleSuggestion.id)).where(
            RuleSuggestion.status == SuggestionStatus.pending
        )
    ).one()
    return {"count": n}


@router.post("/{suggestion_id}/accept", response_model=RuleSuggestionRead)
def accept_suggestion(suggestion_id: str, session: Session = Depends(get_session)):
    obj = _get_or_404(suggestion_id, session)
    if obj.status != SuggestionStatus.pending:
        raise HTTPException(status_code=400, detail="Suggestion is not pending")

    max_priority = session.exec(select(func.max(Rule.priority))).one() or 0
    new_priority = (max_priority or 0) + 1

    action_type = ActionType(obj.action)
    action_params: dict = {}
    if obj.target:
        action_params["folder"] = obj.target

    rule = Rule(
        name=obj.suggested_rule_name,
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
    obj.snooze_until = datetime.utcnow() + timedelta(days=days)
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
