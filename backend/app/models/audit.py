from __future__ import annotations
import uuid
from datetime import datetime
from enum import Enum
from sqlmodel import SQLModel, Field


class AuditStatus(str, Enum):
    success = "success"
    error = "error"


class AuditLog(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    message_id: str = Field(default="", index=True)
    from_address: str = Field(default="")
    subject: str = Field(default="")
    rule_id: str | None = Field(default=None, foreign_key="rule.id", nullable=True)
    rule_name: str | None = None
    action: str = Field(default="")
    target: str | None = None
    status: AuditStatus = AuditStatus.success
    error_msg: str | None = None


class AuditLogRead(SQLModel):
    id: str
    timestamp: datetime
    message_id: str
    from_address: str
    subject: str
    rule_id: str | None
    rule_name: str | None
    action: str
    target: str | None
    status: AuditStatus
    error_msg: str | None


class AuditLogFilter(SQLModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    action: str | None = None
    rule_name: str | None = None
    status: AuditStatus | None = None
    search: str | None = None
    page: int = 1
    page_size: int = 50
