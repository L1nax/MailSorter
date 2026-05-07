from __future__ import annotations
from sqlmodel import SQLModel, Field


class Settings(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str = Field(default="")


class SettingsRead(SQLModel):
    paperless_url: str = ""
    paperless_token: str = ""
    ai_enabled: bool = False
    ai_api_key: str = ""
    ai_model: str = "claude-sonnet-4-20250514"
    ai_system_prompt: str = (
        "Classify this email into one of the provided folders. "
        "Respond with only the folder name."
    )
    ai_provider: str = "claude"
    ai_base_url: str = ""
    audit_retention_days: int = 90
    api_key: str = ""


class SettingsUpdate(SQLModel):
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
