# backend/app/core/suggestion_service.py
from __future__ import annotations
import logging
from datetime import datetime, timezone
from sqlmodel import Session, select
from ..models.suggestion import AISignal, RuleSuggestion, SuggestionStatus
from ..config import get_setting

log = logging.getLogger(__name__)


def process_signals(
    signals: list[dict],
    action: str,
    target: str,
    account_id: str | None,
    session: Session,
) -> None:
    if not signals:
        return
    threshold = int(get_setting(session, "suggestion_threshold") or "3")

    for signal in signals:
        sig_type = signal.get("type", "")
        sig_value = signal.get("value", "")
        if not sig_type or not sig_value:
            continue
        _upsert_and_check(sig_type, sig_value, action, target, account_id, threshold, session)


def _upsert_and_check(
    sig_type: str,
    sig_value: str,
    action: str,
    target: str,
    account_id: str | None,
    threshold: int,
    session: Session,
) -> None:
    existing = session.exec(
        select(AISignal).where(
            AISignal.signal_type == sig_type,
            AISignal.signal_value == sig_value,
            AISignal.action == action,
            AISignal.target == target,
            AISignal.account_id == account_id,
        )
    ).first()

    if existing:
        existing.count += 1
        existing.last_seen = datetime.now(timezone.utc).replace(tzinfo=None)
        session.add(existing)
    else:
        existing = AISignal(
            signal_type=sig_type,
            signal_value=sig_value,
            action=action,
            target=target,
            account_id=account_id,
        )
        session.add(existing)
    session.commit()
    session.refresh(existing)

    if existing.count < threshold:
        return

    _maybe_create_suggestion(sig_type, sig_value, action, target, account_id, session)


def _maybe_create_suggestion(
    sig_type: str,
    sig_value: str,
    action: str,
    target: str,
    account_id: str | None,
    session: Session,
) -> None:
    from ..models.rule import Rule
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    rules = session.exec(select(Rule).where(Rule.enabled == True)).all()
    for rule in rules:
        for cond in (rule.conditions or []):
            if cond.get("type") == sig_type and cond.get("value") == sig_value:
                return

    existing = session.exec(
        select(RuleSuggestion).where(
            RuleSuggestion.signal_type == sig_type,
            RuleSuggestion.signal_value == sig_value,
            RuleSuggestion.action == action,
            RuleSuggestion.target == target,
            RuleSuggestion.account_id == account_id,
        )
    ).first()

    if existing:
        if existing.status == SuggestionStatus.dismissed:
            return
        if existing.status == SuggestionStatus.pending:
            return
        if existing.status == SuggestionStatus.accepted:
            return
        if existing.status == SuggestionStatus.snoozed:
            if existing.snooze_until and existing.snooze_until > now:
                return
            existing.status = SuggestionStatus.pending
            existing.snooze_until = None
            session.add(existing)
            session.commit()
            log.info("Regelvorschlag reaktiviert: %s → %s", sig_value, target)
        return

    conditions = [{"type": sig_type, "value": sig_value, "operator": "contains"}]
    suggestion = RuleSuggestion(
        signal_type=sig_type,
        signal_value=sig_value,
        action=action,
        target=target,
        suggested_conditions=conditions,
        suggested_rule_name=f"[KI] {sig_value} → {target}",
        account_id=account_id,
    )
    session.add(suggestion)
    session.commit()
    log.info("Regelvorschlag erstellt: %s → %s", sig_value, target)
