from __future__ import annotations
import uuid
from datetime import datetime
from enum import Enum
from typing import Any
from sqlalchemy import UniqueConstraint
from sqlmodel import SQLModel, Field, Column, JSON


class SuggestionStatus(str, Enum):
    pending = "pending"
    accepted = "accepted"
    snoozed = "snoozed"
    dismissed = "dismissed"


class AISignal(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("signal_type", "signal_value", "action", "target", "account_id"),
    )
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    signal_type: str = Field(index=True)
    signal_value: str = Field(default="")
    action: str = Field(default="")
    target: str = Field(default="")
    count: int = Field(default=1)
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    account_id: str | None = Field(default=None, nullable=True)


class RuleSuggestion(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("signal_type", "signal_value", "action", "target", "account_id"),
    )
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    signal_type: str = Field(default="")
    signal_value: str = Field(default="")
    action: str = Field(default="")
    target: str = Field(default="")
    suggested_conditions: list[dict[str, Any]] = Field(
        default_factory=list, sa_column=Column(JSON)
    )
    suggested_rule_name: str = Field(default="")
    status: SuggestionStatus = Field(default=SuggestionStatus.pending, index=True)
    snooze_until: datetime | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    account_id: str | None = Field(default=None, nullable=True)


class RuleSuggestionRead(SQLModel):
    id: str
    signal_type: str
    signal_value: str
    action: str
    target: str
    suggested_conditions: list[dict[str, Any]]
    suggested_rule_name: str
    status: SuggestionStatus
    snooze_until: datetime | None
    created_at: datetime
    account_id: str | None
