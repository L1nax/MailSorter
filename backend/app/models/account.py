from __future__ import annotations
import uuid
from datetime import datetime
from sqlmodel import SQLModel, Field


class MailAccount(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    imap_tls: bool = True
    imap_folder: str = "INBOX"
    trash_folder: str = "Trash"
    poll_interval_seconds: int = 60
    use_idle: bool = False
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MailAccountCreate(SQLModel):
    name: str
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    imap_tls: bool = True
    imap_folder: str = "INBOX"
    trash_folder: str = "Trash"
    poll_interval_seconds: int = 60
    use_idle: bool = False
    enabled: bool = True


class MailAccountUpdate(SQLModel):
    name: str | None = None
    imap_host: str | None = None
    imap_port: int | None = None
    imap_user: str | None = None
    imap_password: str | None = None
    imap_tls: bool | None = None
    imap_folder: str | None = None
    trash_folder: str | None = None
    poll_interval_seconds: int | None = None
    use_idle: bool | None = None
    enabled: bool | None = None


class MailAccountRead(SQLModel):
    id: str
    name: str
    imap_host: str
    imap_port: int
    imap_user: str
    imap_password: str
    imap_tls: bool
    imap_folder: str
    trash_folder: str
    poll_interval_seconds: int
    use_idle: bool
    enabled: bool
    created_at: datetime
