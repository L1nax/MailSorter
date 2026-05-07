from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from sqlmodel import Session, select
from ..models.rule import Rule
from ..models.account import MailAccount
from ..models.settings import Settings
from ..models.suggestion import AISignal, RuleSuggestion


def _parse_dt(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    dt = datetime.fromisoformat(value)
    return dt.replace(tzinfo=None) if dt.tzinfo else dt

ALL_SECTIONS = ("rules", "accounts", "settings", "suggestions")


def export_data(session: Session, sections: list[str]) -> dict[str, Any]:
    data: dict[str, Any] = {
        "version": 1,
        "exported_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "sections": sections,
    }
    if "rules" in sections:
        data["rules"] = [_rule_to_dict(r) for r in session.exec(select(Rule).order_by(Rule.priority)).all()]
    if "accounts" in sections:
        data["accounts"] = [_account_to_dict(a) for a in session.exec(select(MailAccount).order_by(MailAccount.created_at)).all()]
    if "settings" in sections:
        data["settings"] = {s.key: s.value for s in session.exec(select(Settings)).all()}
    if "suggestions" in sections:
        data["suggestions"] = {
            "ai_signals": [_signal_to_dict(s) for s in session.exec(select(AISignal)).all()],
            "rule_suggestions": [_suggestion_to_dict(s) for s in session.exec(select(RuleSuggestion)).all()],
        }
    return data


def import_data(session: Session, data: dict[str, Any], mode: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    if mode not in ("merge", "replace"):
        raise ValueError(f"Ungültiger Modus: {mode!r}")
    sections = data.get("sections", [])
    if "rules" in sections:
        counts["rules"] = _import_rules(session, data.get("rules", []), mode)
    if "accounts" in sections:
        counts["accounts"] = _import_accounts(session, data.get("accounts", []), mode)
    if "settings" in sections:
        counts["settings"] = _import_settings(session, data.get("settings", {}), mode)
    if "suggestions" in sections:
        sug = data.get("suggestions", {})
        counts["ai_signals"] = _import_ai_signals(session, sug.get("ai_signals", []), mode)
        counts["rule_suggestions"] = _import_rule_suggestions(session, sug.get("rule_suggestions", []), mode)
    session.commit()
    return counts


def _import_rules(session: Session, items: list[dict], mode: str) -> int:
    if mode == "replace":
        for r in session.exec(select(Rule)).all():
            session.delete(r)
        session.flush()
    count = 0
    for d in items:
        if mode == "merge" and session.get(Rule, d["id"]):
            continue
        row = {**d, "created_at": _parse_dt(d.get("created_at"))}
        session.add(Rule(**row))
        count += 1
    return count


def _import_accounts(session: Session, items: list[dict], mode: str) -> int:
    if mode == "replace":
        for a in session.exec(select(MailAccount)).all():
            session.delete(a)
        session.flush()
    count = 0
    for d in items:
        if mode == "merge" and session.get(MailAccount, d["id"]):
            continue
        row = {**d, "created_at": _parse_dt(d.get("created_at"))}
        session.add(MailAccount(**row))
        count += 1
    return count


def _import_settings(session: Session, items: dict[str, str], mode: str) -> int:
    if mode == "replace":
        for s in session.exec(select(Settings)).all():
            session.delete(s)
        session.flush()
    count = 0
    for key, value in items.items():
        if mode == "merge" and session.get(Settings, key):
            continue
        session.add(Settings(key=key, value=str(value)))
        count += 1
    return count


def _import_ai_signals(session: Session, items: list[dict], mode: str) -> int:
    if mode == "replace":
        for s in session.exec(select(AISignal)).all():
            session.delete(s)
        session.flush()
    count = 0
    for d in items:
        if mode == "merge" and session.get(AISignal, d["id"]):
            continue
        row = {
            **d,
            "created_at": _parse_dt(d.get("created_at")),
            "last_seen": _parse_dt(d.get("last_seen")),
        }
        session.add(AISignal(**row))
        count += 1
    return count


def _import_rule_suggestions(session: Session, items: list[dict], mode: str) -> int:
    if mode == "replace":
        for s in session.exec(select(RuleSuggestion)).all():
            session.delete(s)
        session.flush()
    count = 0
    for d in items:
        if mode == "merge" and session.get(RuleSuggestion, d["id"]):
            continue
        row = {
            **d,
            "created_at": _parse_dt(d.get("created_at")),
            "snooze_until": _parse_dt(d.get("snooze_until")),
        }
        session.add(RuleSuggestion(**row))
        count += 1
    return count


def _rule_to_dict(r: Rule) -> dict:
    return {
        "id": r.id, "name": r.name, "priority": r.priority,
        "enabled": r.enabled, "conditions": r.conditions,
        "action": r.action, "action_params": r.action_params,
        "account_id": r.account_id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _account_to_dict(a: MailAccount) -> dict:
    return {
        "id": a.id, "name": a.name, "imap_host": a.imap_host,
        "imap_port": a.imap_port, "imap_user": a.imap_user,
        "imap_password": a.imap_password, "imap_tls": a.imap_tls,
        "imap_folder": a.imap_folder, "trash_folder": a.trash_folder,
        "poll_interval_seconds": a.poll_interval_seconds,
        "use_idle": a.use_idle, "enabled": a.enabled,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _signal_to_dict(s: AISignal) -> dict:
    return {
        "id": s.id, "signal_type": s.signal_type, "signal_value": s.signal_value,
        "action": s.action, "target": s.target, "count": s.count,
        "last_seen": s.last_seen.isoformat() if s.last_seen else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "account_id": s.account_id,
    }


def _suggestion_to_dict(s: RuleSuggestion) -> dict:
    return {
        "id": s.id, "signal_type": s.signal_type, "signal_value": s.signal_value,
        "action": s.action, "target": s.target,
        "suggested_conditions": s.suggested_conditions,
        "suggested_rule_name": s.suggested_rule_name,
        "status": s.status,
        "snooze_until": s.snooze_until.isoformat() if s.snooze_until else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "account_id": s.account_id,
    }
