from __future__ import annotations
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func, col
from ..db import get_session
from ..models import AuditLog, AuditStatus
from ..models.account import MailAccount

router = APIRouter(prefix="/api", tags=["status"])

_manager_ref = None


def set_account_manager(manager) -> None:
    global _manager_ref
    _manager_ref = manager


@router.get("/status")
def get_status(session: Session = Depends(get_session)):
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    mails_today = session.exec(
        select(func.count(AuditLog.id)).where(AuditLog.timestamp >= today)
    ).one()
    mails_week = session.exec(
        select(func.count(AuditLog.id)).where(AuditLog.timestamp >= week_ago)
    ).one()
    ai_count_week = session.exec(
        select(func.count(AuditLog.id))
        .where(AuditLog.timestamp >= week_ago)
        .where(AuditLog.rule_name == "AI")
    ).one()

    top_rules_rows = session.exec(
        select(AuditLog.rule_name, func.count(col(AuditLog.id)).label("cnt"))
        .where(AuditLog.timestamp >= week_ago)
        .where(AuditLog.rule_name != None)
        .where(AuditLog.rule_name != "AI")
        .where(AuditLog.rule_name != "no match")
        .where(AuditLog.status == AuditStatus.success)
        .group_by(AuditLog.rule_name)
        .order_by(func.count(col(AuditLog.id)).desc())
        .limit(5)
    ).all()
    top_rules = [{"name": name, "count": cnt} for name, cnt in top_rules_rows]

    accounts = session.exec(select(MailAccount).where(MailAccount.enabled == True)).all()
    worker_running = bool(_manager_ref and _manager_ref.running and _manager_ref._tasks)
    imap_configured = bool(accounts)
    idle_mode = any(a.use_idle for a in accounts)

    from ..config import get_setting
    paperless_configured = all([
        get_setting(session, "paperless_url"),
        get_setting(session, "paperless_token"),
    ])

    return {
        "worker_running": worker_running,
        "idle_mode": idle_mode,
        "imap_configured": imap_configured,
        "paperless_configured": paperless_configured,
        "mails_today": mails_today,
        "mails_week": mails_week,
        "ai_count_week": ai_count_week,
        "top_rules": top_rules,
        "timestamp": now.isoformat(),
    }


@router.post("/worker/start", status_code=204)
async def start_worker():
    if _manager_ref:
        _manager_ref.start()


@router.post("/worker/stop", status_code=204)
def stop_worker():
    if _manager_ref:
        _manager_ref.stop()


@router.post("/worker/process-now", status_code=204)
async def process_now():
    if _manager_ref:
        await _manager_ref.process_all_now()
