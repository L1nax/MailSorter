from __future__ import annotations
import uuid
from datetime import datetime
from enum import Enum
from typing import Any
from sqlmodel import SQLModel, Field, Column, JSON


class ConditionType(str, Enum):
    from_domain = "from_domain"
    from_address = "from_address"
    subject_contains = "subject_contains"
    subject_regex = "subject_regex"
    has_attachment = "has_attachment"
    attachment_type = "attachment_type"
    body_contains = "body_contains"
    to_address = "to_address"


class ActionType(str, Enum):
    move = "move"
    label = "label"
    paperless = "paperless"
    webhook = "webhook"
    keep = "keep"
    trash = "trash"


class RuleBase(SQLModel):
    name: str
    priority: int = 100
    enabled: bool = True
    conditions: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    action: ActionType
    action_params: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class Rule(RuleBase, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RuleCreate(RuleBase):
    pass


class RuleUpdate(SQLModel):
    name: str | None = None
    priority: int | None = None
    enabled: bool | None = None
    conditions: list[dict[str, Any]] | None = None
    action: ActionType | None = None
    action_params: dict[str, Any] | None = None


class RuleRead(RuleBase):
    id: str
    created_at: datetime


class RuleReorder(SQLModel):
    ids: list[str]


class RuleTestRequest(SQLModel):
    from_address: str = ""
    subject: str = ""
    to_address: str = ""
    has_attachment: bool = False
    attachment_types: list[str] = Field(default_factory=list)
    body: str = ""
    # Optional: Conditions der aktuell im Editor offenen Regel (noch nicht gespeichert)
    conditions: list[dict[str, Any]] | None = None
