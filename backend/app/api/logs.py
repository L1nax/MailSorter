from __future__ import annotations
import csv
import io
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from ..db import get_session
from ..models import AuditLog, AuditLogRead, AuditStatus

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("", response_model=dict)
def list_logs(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    action: str | None = None,
    rule_name: str | None = None,
    status: AuditStatus | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    session: Session = Depends(get_session),
):
    q = select(AuditLog).order_by(AuditLog.timestamp.desc())
    if date_from:
        q = q.where(AuditLog.timestamp >= date_from)
    if date_to:
        q = q.where(AuditLog.timestamp <= date_to)
    if action:
        q = q.where(AuditLog.action == action)
    if rule_name:
        q = q.where(AuditLog.rule_name == rule_name)
    if status:
        q = q.where(AuditLog.status == status)
    if search:
        like = f"%{search}%"
        q = q.where(
            (AuditLog.from_address.like(like))
            | (AuditLog.subject.like(like))
            | (AuditLog.message_id.like(like))
        )

    total = len(session.exec(q).all())
    items = session.exec(q.offset((page - 1) * page_size).limit(page_size)).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [AuditLogRead.model_validate(i) for i in items]}


@router.get("/export")
def export_logs(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    session: Session = Depends(get_session),
):
    q = select(AuditLog).order_by(AuditLog.timestamp.desc())
    if date_from:
        q = q.where(AuditLog.timestamp >= date_from)
    if date_to:
        q = q.where(AuditLog.timestamp <= date_to)
    rows = session.exec(q).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "timestamp", "message_id", "from_address", "subject", "rule_name", "action", "target", "status", "error_msg"])
    for r in rows:
        writer.writerow([r.id, r.timestamp, r.message_id, r.from_address, r.subject, r.rule_name, r.action, r.target, r.status, r.error_msg])

    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=mailsort-audit.csv"})


@router.delete("", status_code=204)
def purge_logs(older_than_days: int = Query(90, ge=1), session: Session = Depends(get_session)):
    cutoff = datetime.utcnow() - timedelta(days=older_than_days)
    rows = session.exec(select(AuditLog).where(AuditLog.timestamp < cutoff)).all()
    for row in rows:
        session.delete(row)
    session.commit()
