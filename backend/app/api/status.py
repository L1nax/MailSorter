from __future__ import annotations
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func
from ..db import get_session
from ..models import AuditLog

router = APIRouter(prefix="/api", tags=["status"])

# Imported at runtime to avoid circular imports
_worker_ref: object = None


def set_worker(worker) -> None:
    global _worker_ref
    _worker_ref = worker


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

    worker_running = bool(_worker_ref and getattr(_worker_ref, "running", False))

    return {
        "worker_running": worker_running,
        "mails_today": mails_today,
        "mails_week": mails_week,
        "timestamp": now.isoformat(),
    }


@router.post("/worker/start", status_code=204)
def start_worker():
    if _worker_ref:
        _worker_ref.start()


@router.post("/worker/stop", status_code=204)
def stop_worker():
    if _worker_ref:
        _worker_ref.stop()


@router.post("/worker/process-now", status_code=204)
async def process_now():
    if _worker_ref:
        await _worker_ref.process_once()
