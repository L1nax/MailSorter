from __future__ import annotations
from sqlmodel import Session, select
from .models.settings import Settings, SettingsRead

DEFAULTS: dict[str, str] = {
    "paperless_url": "",
    "paperless_token": "",
    "ai_enabled": "false",
    "ai_api_key": "",
    "ai_model": "claude-sonnet-4-20250514",
    "ai_system_prompt": (
        "Du bist ein intelligenter E-Mail-Sortier-Assistent.\n\n"
        "Antworte ausschließlich mit einer Aktion aus der angezeigten Liste – kein weiterer Text.\n\n"
        "Vorgehensweise:\n"
        "1. Passt die Mail zu einem vorhandenen Ordner → move:<Ordner>\n"
        "2. Mail enthält PDF-Anhänge, die archiviert gehören (Rechnungen, Verträge, Dokumente) → paperless:<Ordner> oder paperless\n"
        "3. Kein passender Ordner, aber ein neuer wäre sinnvoll → move:<neuer-Ordner> (kurz, Deutsch, Bindestriche)\n"
        "4. Werbung oder Spam ohne Mehrwert → trash\n"
        "5. Sonst → keep"
    ),
    "ai_provider": "claude",
    "ai_base_url": "",
    "audit_retention_days": "90",
    "api_key": "",
    "suggestion_threshold": "3",
    "suggestion_snooze_days": "30",
}

MASKED_KEYS = {"paperless_token", "ai_api_key", "api_key"}


def get_setting(session: Session, key: str) -> str:
    row = session.get(Settings, key)
    if row is None:
        return DEFAULTS.get(key, "")
    return row.value


def set_setting(session: Session, key: str, value: str) -> None:
    row = session.get(Settings, key)
    if row is None:
        row = Settings(key=key, value=value)
        session.add(row)
    else:
        row.value = value
    session.commit()


def get_all_settings(session: Session) -> SettingsRead:
    def g(k: str) -> str:
        return get_setting(session, k)

    return SettingsRead(
        paperless_url=g("paperless_url"),
        paperless_token="***" if g("paperless_token") else "",
        ai_enabled=g("ai_enabled") == "true",
        ai_api_key="***" if g("ai_api_key") else "",
        ai_model=g("ai_model"),
        ai_system_prompt=g("ai_system_prompt"),
        ai_provider=g("ai_provider"),
        ai_base_url=g("ai_base_url"),
        audit_retention_days=int(g("audit_retention_days")),
        api_key="***" if g("api_key") else "",
        suggestion_threshold=int(g("suggestion_threshold") or "3"),
        suggestion_snooze_days=int(g("suggestion_snooze_days") or "30"),
    )
