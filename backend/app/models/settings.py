from __future__ import annotations
from sqlmodel import SQLModel, Field


class Settings(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str = Field(default="")


class SettingsRead(SQLModel):
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""  # masked in responses
    imap_tls: bool = True
    imap_folder: str = "INBOX"
    poll_interval_seconds: int = 60
    use_idle: bool = False
    trash_folder: str = "Trash"
    paperless_url: str = ""
    paperless_token: str = ""  # masked
    ai_enabled: bool = False
    ai_api_key: str = ""  # masked
    ai_model: str = "claude-sonnet-4-20250514"
    ai_system_prompt: str = (
        "Classify this email into one of the provided folders. "
        "Respond with only the folder name."
    )
    ai_provider: str = "claude"
    ai_base_url: str = ""
    audit_retention_days: int = 90
    api_key: str = ""  # optional UI protection, masked


class SettingsUpdate(SQLModel):
    imap_host: str | None = None
    imap_port: int | None = None
    imap_user: str | None = None
    imap_password: str | None = None
    imap_tls: bool | None = None
    imap_folder: str | None = None
    poll_interval_seconds: int | None = None
    use_idle: bool | None = None
    trash_folder: str | None = None
    paperless_url: str | None = None
    paperless_token: str | None = None
    ai_enabled: bool | None = None
    ai_api_key: str | None = None
    ai_model: str | None = None
    ai_system_prompt: str | None = None
    ai_provider: str | None = None
    ai_base_url: str | None = None
    audit_retention_days: int | None = None
    api_key: str | None = None
