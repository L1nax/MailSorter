from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from ..db import get_session
from ..models import Rule, RuleCreate, RuleUpdate, RuleRead, RuleReorder, RuleTestRequest
from ..core.rule_engine import RuleEngine, MailData

router = APIRouter(prefix="/api/rules", tags=["rules"])


def _get_rule_or_404(rule_id: str, session: Session) -> Rule:
    rule = session.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.get("", response_model=list[RuleRead])
def list_rules(session: Session = Depends(get_session)):
    return session.exec(select(Rule).order_by(Rule.priority)).all()


@router.post("", response_model=RuleRead, status_code=201)
def create_rule(body: RuleCreate, session: Session = Depends(get_session)):
    rule = Rule(**body.model_dump())
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.put("/{rule_id}", response_model=RuleRead)
def update_rule(rule_id: str, body: RuleUpdate, session: Session = Depends(get_session)):
    rule = _get_rule_or_404(rule_id, session)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(rule, k, v)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: str, session: Session = Depends(get_session)):
    rule = _get_rule_or_404(rule_id, session)
    session.delete(rule)
    session.commit()


@router.post("/reorder", status_code=204)
def reorder_rules(body: RuleReorder, session: Session = Depends(get_session)):
    for priority, rule_id in enumerate(body.ids):
        rule = _get_rule_or_404(rule_id, session)
        rule.priority = priority
        session.add(rule)
    session.commit()


@router.post("/test")
def test_rule(body: RuleTestRequest, session: Session = Depends(get_session)):
    rules = session.exec(select(Rule).where(Rule.enabled == True).order_by(Rule.priority)).all()
    mail = MailData(
        from_address=body.from_address,
        subject=body.subject,
        to_address=body.to_address,
        has_attachment=body.has_attachment,
        attachment_types=body.attachment_types,
        body=body.body,
    )
    engine = RuleEngine(rules)
    matched = engine.evaluate(mail)
    if matched:
        return {"matched": True, "rule_id": matched.id, "rule_name": matched.name, "action": matched.action, "action_params": matched.action_params}
    return {"matched": False}
