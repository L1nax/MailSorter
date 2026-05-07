# Multi-Account-Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mehrere IMAP-Accounts gleichzeitig verwalten und verarbeiten – jeder Account läuft in einem eigenen asyncio-Task, Regeln können global oder account-spezifisch sein, das Audit-Log zeigt den Account.

**Architecture:** Neue `MailAccount`-SQLModel-Tabelle; `AccountManager` startet/stoppt je einen `IMAPWorker` pro Account; `IMAPWorker` bekommt den Account als Parameter statt Settings aus der DB zu lesen. Migration beim App-Start überträgt alte IMAP-Settings als ersten Account.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, SQLite, React, TypeScript, Tailwind CSS, Vite

---

## Dateiübersicht

| Datei | Neu/Geändert | Zweck |
|-------|-------------|-------|
| `backend/app/models/account.py` | Neu | MailAccount SQLModel + CRUD-Schemas |
| `backend/app/core/account_manager.py` | Neu | Startet/stoppt Worker pro Account |
| `backend/app/api/accounts.py` | Neu | REST-Endpoints für Accounts |
| `frontend/src/pages/AccountsPage.tsx` | Neu | Account-Verwaltungs-UI |
| `backend/app/models/__init__.py` | Geändert | MailAccount exportieren |
| `backend/app/models/rule.py` | Geändert | `account_id` Feld |
| `backend/app/models/audit.py` | Geändert | `account_id`, `account_name` Felder |
| `backend/app/db.py` | Geändert | Migration: Spalten + Settings-Migration |
| `backend/app/core/imap_worker.py` | Geändert | Nimmt MailAccount statt Settings zu lesen |
| `backend/app/main.py` | Geändert | AccountManager statt IMAPWorker |
| `backend/app/api/settings.py` | Geändert | IMAP-Felder entfernen |
| `backend/app/models/settings.py` | Geändert | IMAP-Felder entfernen |
| `backend/app/config.py` | Geändert | IMAP-Defaults entfernen |
| `backend/app/api/status.py` | Geändert | AccountManager statt Worker-Ref |
| `frontend/src/api/client.ts` | Geändert | Accounts API + typen aktualisiert |
| `frontend/src/App.tsx` | Geändert | `/accounts` Route |
| `frontend/src/components/layout/Layout.tsx` | Geändert | Accounts Nav-Eintrag |
| `frontend/src/pages/Rules.tsx` | Geändert | Account-Dropdown im Regel-Editor |
| `frontend/src/pages/Logs.tsx` | Geändert | Account-Spalte |
| `frontend/src/pages/SettingsPage.tsx` | Geändert | IMAP-Sektion entfernen |

---

## Task 1: MailAccount Datenmodell

**Files:**
- Create: `backend/app/models/account.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Datei anlegen**

```python
# backend/app/models/account.py
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
```

- [ ] **Step 2: `__init__.py` aktualisieren**

Ersetze den Inhalt von `backend/app/models/__init__.py`:

```python
from .rule import Rule, RuleCreate, RuleUpdate, RuleRead, RuleReorder, RuleTestRequest, ActionType, ConditionType
from .audit import AuditLog, AuditLogRead, AuditLogFilter, AuditStatus
from .settings import Settings, SettingsRead, SettingsUpdate
from .account import MailAccount, MailAccountCreate, MailAccountUpdate, MailAccountRead

__all__ = [
    "Rule", "RuleCreate", "RuleUpdate", "RuleRead", "RuleReorder", "RuleTestRequest",
    "ActionType", "ConditionType",
    "AuditLog", "AuditLogRead", "AuditLogFilter", "AuditStatus",
    "Settings", "SettingsRead", "SettingsUpdate",
    "MailAccount", "MailAccountCreate", "MailAccountUpdate", "MailAccountRead",
]
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/account.py backend/app/models/__init__.py
git commit -m "feat: add MailAccount model"
```

---

## Task 2: DB-Migration (neue Spalten + Settings-Migration)

**Files:**
- Modify: `backend/app/db.py`

- [ ] **Step 1: `db.py` vollständig ersetzen**

```python
from __future__ import annotations
import logging
import os
from sqlmodel import SQLModel, Session, create_engine

log = logging.getLogger(__name__)

DATA_DIR = os.environ.get("MAILSORT_DATA_DIR", "/data")
DB_PATH = os.path.join(DATA_DIR, "mailsort.db")

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


def init_db() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    # Alle Models importieren damit SQLModel.metadata sie kennt
    from . import models  # noqa: F401
    SQLModel.metadata.create_all(engine)
    _migrate()


def _migrate() -> None:
    from sqlalchemy import text
    with engine.connect() as conn:
        for table, column, col_type in [
            ("rule", "account_id", "TEXT"),
            ("auditlog", "account_id", "TEXT"),
            ("auditlog", "account_name", "TEXT"),
        ]:
            cols = [row[1] for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()]
            if column not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                conn.commit()
                log.info("Migration: Spalte %s.%s hinzugefügt", table, column)

    # Alte IMAP-Settings als ersten Account migrieren
    from sqlmodel import select, func
    from .models.account import MailAccount
    from .models.settings import Settings
    from .config import get_setting

    with Session(engine) as s:
        count = s.exec(select(func.count(MailAccount.id))).one()
        if count == 0:
            host = get_setting(s, "imap_host")
            if host:
                account = MailAccount(
                    name="Standard",
                    imap_host=host,
                    imap_port=int(get_setting(s, "imap_port") or "993"),
                    imap_user=get_setting(s, "imap_user"),
                    imap_password=get_setting(s, "imap_password"),
                    imap_tls=get_setting(s, "imap_tls") == "true",
                    imap_folder=get_setting(s, "imap_folder") or "INBOX",
                    trash_folder=get_setting(s, "trash_folder") or "Trash",
                    poll_interval_seconds=int(get_setting(s, "poll_interval_seconds") or "60"),
                    use_idle=get_setting(s, "use_idle") == "true",
                )
                s.add(account)
                for key in [
                    "imap_host", "imap_port", "imap_user", "imap_password",
                    "imap_tls", "imap_folder", "trash_folder",
                    "poll_interval_seconds", "use_idle",
                ]:
                    row = s.get(Settings, key)
                    if row:
                        s.delete(row)
                s.commit()
                log.info("Migration: Account 'Standard' aus alten IMAP-Settings angelegt")


def get_session():
    with Session(engine) as session:
        yield session
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/db.py
git commit -m "feat: db migration for multi-account (columns + settings import)"
```

---

## Task 3: Rule-Modell um account_id erweitern

**Files:**
- Modify: `backend/app/models/rule.py`

- [ ] **Step 1: `account_id` zu Rule-Klassen hinzufügen**

In `backend/app/models/rule.py` die Klasse `RuleBase` um `account_id` erweitern, und `RuleUpdate` ebenfalls:

```python
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
    account_id: str | None = Field(default=None, nullable=True)


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
    account_id: str | None = None


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
    conditions: list[dict[str, Any]] | None = None
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/models/rule.py
git commit -m "feat: add account_id to Rule model"
```

---

## Task 4: AuditLog-Modell um account_id und account_name erweitern

**Files:**
- Modify: `backend/app/models/audit.py`

- [ ] **Step 1: Neue Felder hinzufügen**

Ersetze `backend/app/models/audit.py`:

```python
from __future__ import annotations
import uuid
from datetime import datetime
from enum import Enum
from sqlmodel import SQLModel, Field


class AuditStatus(str, Enum):
    processing = "processing"
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
    account_id: str | None = Field(default=None, nullable=True)
    account_name: str | None = Field(default=None, nullable=True)


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
    account_id: str | None
    account_name: str | None


class AuditLogFilter(SQLModel):
    date_from: datetime | None = None
    date_to: datetime | None = None
    action: str | None = None
    rule_name: str | None = None
    status: AuditStatus | None = None
    search: str | None = None
    page: int = 1
    page_size: int = 50
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/models/audit.py
git commit -m "feat: add account_id/account_name to AuditLog model"
```

---

## Task 5: IMAPWorker auf MailAccount umstellen

**Files:**
- Modify: `backend/app/core/imap_worker.py`

Die wichtigsten Änderungen:
- `__init__` bekommt `account: MailAccount` statt Settings zu lesen
- `start()`/`stop()` werden entfernt, neues `run()` als Task-Einstiegspunkt
- Regeln werden nach `account_id` gefiltert
- Log-Einträge enthalten `account_id` und `account_name`

- [ ] **Step 1: Datei vollständig ersetzen**

```python
from __future__ import annotations
import asyncio
import email
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from email import policy
from email.utils import parseaddr
from typing import Any
from imapclient import IMAPClient
from sqlmodel import Session, select, or_
from ..db import engine
from ..config import get_setting
from ..models import Rule, AuditLog, AuditStatus
from ..models.account import MailAccount
from .rule_engine import RuleEngine, MailData
from .action_executor import ActionExecutor

log = logging.getLogger(__name__)


@dataclass
class RawMail:
    uid: int
    message_id: str
    from_address: str
    subject: str
    to_address: str
    body: str
    has_attachment: bool
    attachment_types: list[str]
    raw_attachments: list[tuple[str, bytes]] = field(default_factory=list)


def _extract_body(msg: email.message.Message) -> str:
    plain = None
    html = None
    for part in msg.walk():
        ct = part.get_content_type()
        if ct == "text/plain" and plain is None:
            plain = part.get_payload(decode=True).decode(errors="replace")
        elif ct == "text/html" and html is None:
            html = part.get_payload(decode=True).decode(errors="replace")
    if plain:
        return plain
    if html:
        try:
            from bs4 import BeautifulSoup
            return BeautifulSoup(html, "html.parser").get_text(separator="\n")
        except Exception:
            return html
    return ""


def _parse_mail(uid: int, raw: bytes) -> RawMail:
    msg = email.message_from_bytes(raw, policy=policy.compat32)
    _, from_addr = parseaddr(msg.get("From", ""))
    _, to_addr = parseaddr(msg.get("To", ""))
    subject = msg.get("Subject", "")
    message_id = msg.get("Message-ID", "")
    body = _extract_body(msg)

    attachment_types: list[str] = []
    raw_attachments: list[tuple[str, bytes]] = []
    for part in msg.walk():
        if part.get_content_disposition() == "attachment":
            ct = part.get_content_type()
            attachment_types.append(ct)
            filename = part.get_filename() or "attachment"
            data = part.get_payload(decode=True) or b""
            raw_attachments.append((filename, data))

    return RawMail(
        uid=uid,
        message_id=message_id,
        from_address=from_addr,
        subject=subject,
        to_address=to_addr,
        body=body,
        has_attachment=bool(attachment_types),
        attachment_types=attachment_types,
        raw_attachments=raw_attachments,
    )


def test_imap_connection(host: str, port: int, user: str, password: str, tls: bool) -> tuple[bool, str]:
    missing = [name for name, val in [("Host", host), ("Benutzer", user), ("Passwort", password)] if not val]
    if missing:
        return False, f"IMAP nicht vollständig konfiguriert – fehlt: {', '.join(missing)}"
    try:
        with IMAPClient(host, port=port, ssl=tls) as imap:
            imap.login(user, password)
        return True, "Connection successful"
    except Exception as exc:
        return False, str(exc)


class IMAPWorker:
    def __init__(self, account: MailAccount) -> None:
        self.account = account
        self.running = False
        self._process_event = threading.Event()

    async def run(self) -> None:
        self.running = True
        try:
            await self._run()
        except asyncio.CancelledError:
            pass
        finally:
            self.running = False

    async def _run(self) -> None:
        while self.running:
            if self.account.use_idle:
                try:
                    await asyncio.to_thread(self._run_idle_sync)
                except Exception:
                    log.exception("IDLE error for account '%s', reconnecting in 30s", self.account.name)
                    await asyncio.sleep(30)
            else:
                try:
                    await self.process_once()
                except Exception:
                    log.exception("IMAPWorker loop error for account '%s'", self.account.name)
                await asyncio.sleep(self.account.poll_interval_seconds)

    async def process_once(self) -> None:
        if self.account.use_idle and self.running:
            self._process_event.set()
            return

        if not self.account.imap_host or not self.account.imap_user or not self.account.imap_password:
            log.debug("Account '%s' not configured, skipping", self.account.name)
            return

        with Session(engine) as session:
            ai_enabled = get_setting(session, "ai_enabled") == "true"
            ai_key = get_setting(session, "ai_api_key")
            ai_model = get_setting(session, "ai_model")
            ai_prompt = get_setting(session, "ai_system_prompt")

        try:
            await asyncio.to_thread(
                self._process_imap,
                self.account.imap_host,
                self.account.imap_port,
                self.account.imap_user,
                self.account.imap_password,
                self.account.imap_tls,
                self.account.imap_folder,
                self.account.trash_folder,
                ai_enabled, ai_key, ai_model, ai_prompt,
            )
        except Exception:
            log.exception("IMAP processing error for account '%s'", self.account.name)

    def _process_imap(
        self,
        host: str, port: int, user: str, password: str, tls: bool,
        folder: str, trash: str,
        ai_enabled: bool, ai_key: str, ai_model: str, ai_prompt: str,
    ) -> None:
        with IMAPClient(host, port=port, ssl=tls) as imap:
            imap.login(user, password)
            imap.select_folder(folder, readonly=False)
            self._process_imap_session(imap, folder, trash, ai_enabled, ai_key, ai_model, ai_prompt)

    def _process_imap_session(
        self,
        imap: IMAPClient,
        folder: str, trash: str,
        ai_enabled: bool, ai_key: str, ai_model: str, ai_prompt: str,
    ) -> None:
        uids = imap.search(["UNSEEN"])
        if not uids:
            return
        log.info("Account '%s': %d ungelesene Mails gefunden", self.account.name, len(uids))

        with Session(engine) as session:
            rules = session.exec(
                select(Rule)
                .where(Rule.enabled == True)
                .where(or_(Rule.account_id == None, Rule.account_id == self.account.id))
                .order_by(Rule.priority)
            ).all()

        rule_engine = RuleEngine(list(rules))
        executor = ActionExecutor(imap, trash_folder=trash)

        rule_folders = [
            r.action_params.get("folder")
            for r in rules
            if r.action == "move" and r.action_params and r.action_params.get("folder")
        ]
        if rule_folders:
            executor.subscribe_rule_folders(rule_folders)

        for uid in uids:
            try:
                raw_data = imap.fetch([uid], ["BODY.PEEK[]"])
                raw_bytes = raw_data[uid][b"BODY[]"]
                mail = _parse_mail(uid, raw_bytes)
                self._process_single(mail, rule_engine, executor, imap, ai_enabled, ai_key, ai_model, ai_prompt, folder)
            except Exception:
                log.exception("Error processing UID %s on account '%s'", uid, self.account.name)

    def _run_idle_sync(self) -> None:
        IDLE_REFRESH_SECS = 20 * 60
        IDLE_CHECK_SECS = 30

        host = self.account.imap_host
        port = self.account.imap_port
        user = self.account.imap_user
        password = self.account.imap_password
        tls = self.account.imap_tls
        folder = self.account.imap_folder
        trash = self.account.trash_folder

        if not host or not user or not password:
            log.debug("Account '%s' not configured, skipping IDLE", self.account.name)
            return

        with Session(engine) as s:
            ai_enabled = get_setting(s, "ai_enabled") == "true"
            ai_key = get_setting(s, "ai_api_key")
            ai_model = get_setting(s, "ai_model")
            ai_prompt = get_setting(s, "ai_system_prompt")

        with IMAPClient(host, port=port, ssl=tls) as imap:
            imap.login(user, password)
            imap.select_folder(folder, readonly=False)
            self._process_imap_session(imap, folder, trash, ai_enabled, ai_key, ai_model, ai_prompt)

            log.info("Account '%s': IDLE-Modus aktiv", self.account.name)
            imap.idle()
            idle_start = time.monotonic()

            while self.running:
                try:
                    responses = imap.idle_check(timeout=IDLE_CHECK_SECS)
                except Exception:
                    log.exception("IDLE: idle_check fehlgeschlagen für '%s'", self.account.name)
                    return

                elapsed = time.monotonic() - idle_start
                has_new = any(
                    typ == b"EXISTS"
                    for entry in (responses or [])
                    for _, typ in [entry[:2]]
                )
                force = self._process_event.is_set()

                if has_new or elapsed >= IDLE_REFRESH_SECS or force:
                    try:
                        imap.idle_done()
                    except Exception:
                        log.exception("IDLE: idle_done fehlgeschlagen für '%s'", self.account.name)
                        return

                    self._process_event.clear()

                    if has_new or force:
                        try:
                            imap.select_folder(folder, readonly=False)
                            self._process_imap_session(imap, folder, trash, ai_enabled, ai_key, ai_model, ai_prompt)
                        except Exception:
                            log.exception("IDLE: Verarbeitung fehlgeschlagen für '%s'", self.account.name)
                            return
                    else:
                        log.info("IDLE: Verbindung für '%s' nach %.0fs erneuert", self.account.name, elapsed)

                    try:
                        imap.select_folder(folder, readonly=False)
                        imap.idle()
                        idle_start = time.monotonic()
                    except Exception:
                        log.exception("IDLE: Neustart fehlgeschlagen für '%s'", self.account.name)
                        return

            try:
                imap.idle_done()
            except Exception:
                pass

    def _process_single(
        self,
        mail: RawMail,
        rule_engine: RuleEngine,
        executor: ActionExecutor,
        imap: IMAPClient,
        ai_enabled: bool,
        ai_key: str,
        ai_model: str,
        ai_prompt: str,
        inbox_folder: str,
    ) -> None:
        mail_data = MailData(
            from_address=mail.from_address,
            subject=mail.subject,
            to_address=mail.to_address,
            body=mail.body,
            has_attachment=mail.has_attachment,
            attachment_types=mail.attachment_types,
        )

        matched_rule = rule_engine.evaluate(mail_data)
        rule_id: str | None = None
        rule_name: str | None = None
        action_type: Any = None
        action_params: dict[str, Any] = {}
        ai_warning = ""

        if matched_rule:
            rule_id = matched_rule.id
            rule_name = matched_rule.name
            action_type = matched_rule.action
            action_params = matched_rule.action_params or {}
        elif ai_enabled:
            import asyncio as _asyncio
            with Session(engine) as s:
                from .providers import get_provider as _get_provider
                from sqlmodel import select as _select
                _provider = _get_provider(s)
                target_folders = [r.action_params.get("folder", "") for r in s.exec(_select(Rule)).all() if r.action_params.get("folder")]
            ai_result = _asyncio.run(_provider.classify(mail, target_folders, ai_prompt))
            rule_name = "AI"
            action_type = ai_result.action
            action_params = ai_result.params
            ai_warning = ai_result.warning

        if action_type is None:
            action_type = "keep"
            rule_name = rule_name or "no match"

        log_id = self._create_log_entry(
            mail, rule_id, rule_name, str(action_type),
            self.account.id, self.account.name,
        )

        mark_as_read: bool = action_params.get("mark_as_read", False)

        if str(action_type) == "keep":
            if mark_as_read:
                imap.set_flags(mail.uid, [b"\\Seen"])
            self._finalize_log_entry(log_id, inbox_folder, AuditStatus.success, ai_warning)
            return

        if str(action_type) == "paperless":
            from ..services.paperless import upload_pdf_sync
            with Session(engine) as s:
                paperless_url = get_setting(s, "paperless_url")
                paperless_token = get_setting(s, "paperless_token")
            for filename, data in mail.raw_attachments:
                if filename.lower().endswith(".pdf"):
                    ok, err = upload_pdf_sync(paperless_url, paperless_token, filename, data, mail)
                    if not ok:
                        self._finalize_log_entry(log_id, filename, AuditStatus.error, err)
                        return

        if str(action_type) == "webhook":
            from ..services.webhook import fire_webhook_sync
            url = action_params.get("url", "")
            fire_webhook_sync(url, mail)

        exec_result = executor.execute(mail, action_type, action_params)
        status = AuditStatus.success if exec_result.success else AuditStatus.error
        self._finalize_log_entry(log_id, exec_result.target, status, exec_result.error or ai_warning)

        if exec_result.success and mark_as_read:
            imap.set_flags(mail.uid, [b"\\Seen"])

    @staticmethod
    def _create_log_entry(
        mail: RawMail,
        rule_id: str | None,
        rule_name: str | None,
        action: str,
        account_id: str = "",
        account_name: str = "",
    ) -> str:
        with Session(engine) as s:
            entry = AuditLog(
                timestamp=datetime.utcnow(),
                message_id=mail.message_id,
                from_address=mail.from_address,
                subject=mail.subject,
                rule_id=rule_id,
                rule_name=rule_name,
                action=action,
                status=AuditStatus.processing,
                account_id=account_id or None,
                account_name=account_name or None,
            )
            s.add(entry)
            s.commit()
            s.refresh(entry)
            return entry.id

    @staticmethod
    def _finalize_log_entry(
        log_id: str,
        target: str | None,
        status: AuditStatus,
        error_msg: str,
    ) -> None:
        with Session(engine) as s:
            entry = s.get(AuditLog, log_id)
            if entry:
                entry.target = target or None
                entry.status = status
                entry.error_msg = error_msg or None
                s.add(entry)
                s.commit()
```

- [ ] **Step 2: Bestehende Tests ausführen**

```bash
cd /Users/andreengele/PycharmProjects/MailSorter
.venv/bin/pytest backend/tests/ -v
```

Erwartet: alle Tests grün (die Tests betreffen Rule Engine, AI Classifier, Providers – nicht den Worker direkt).

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/imap_worker.py
git commit -m "feat: IMAPWorker accepts MailAccount instead of reading settings"
```

---

## Task 6: AccountManager erstellen

**Files:**
- Create: `backend/app/core/account_manager.py`

- [ ] **Step 1: Datei anlegen**

```python
from __future__ import annotations
import asyncio
import logging
from sqlmodel import Session, select
from ..db import engine
from ..models.account import MailAccount
from .imap_worker import IMAPWorker

log = logging.getLogger(__name__)


class AccountManager:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}
        self._workers: dict[str, IMAPWorker] = {}
        self.running = False

    def start(self) -> None:
        self.running = True
        loop = asyncio.get_running_loop()
        with Session(engine) as s:
            accounts = s.exec(select(MailAccount).where(MailAccount.enabled == True)).all()
        for account in accounts:
            self._launch(account, loop)
        log.info("AccountManager gestartet mit %d Accounts", len(accounts))

    def stop(self) -> None:
        self.running = False
        for worker in self._workers.values():
            worker.running = False
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
        self._workers.clear()
        log.info("AccountManager gestoppt")

    def start_account(self, account: MailAccount) -> None:
        loop = asyncio.get_running_loop()
        self._launch(account, loop)

    def stop_account(self, account_id: str) -> None:
        if account_id in self._workers:
            self._workers[account_id].running = False
        if account_id in self._tasks:
            self._tasks[account_id].cancel()
            del self._tasks[account_id]
        self._workers.pop(account_id, None)
        log.info("AccountManager: Worker für Account %s gestoppt", account_id)

    def restart_account(self, account: MailAccount) -> None:
        self.stop_account(account.id)
        if account.enabled:
            self.start_account(account)

    def _launch(self, account: MailAccount, loop: asyncio.AbstractEventLoop) -> None:
        worker = IMAPWorker(account)
        task = loop.create_task(worker.run())
        self._tasks[account.id] = task
        self._workers[account.id] = worker
        log.info("AccountManager: Worker für '%s' (%s) gestartet", account.name, account.id)

    async def process_all_now(self) -> None:
        with Session(engine) as s:
            accounts = s.exec(select(MailAccount).where(MailAccount.enabled == True)).all()
        await asyncio.gather(
            *[IMAPWorker(account).process_once() for account in accounts],
            return_exceptions=True,
        )

    async def process_account_now(self, account_id: str) -> None:
        if account_id in self._workers:
            await self._workers[account_id].process_once()
        else:
            with Session(engine) as s:
                account = s.get(MailAccount, account_id)
            if account:
                await IMAPWorker(account).process_once()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/core/account_manager.py
git commit -m "feat: add AccountManager for multi-account worker lifecycle"
```

---

## Task 7: Accounts API erstellen

**Files:**
- Create: `backend/app/api/accounts.py`

- [ ] **Step 1: Datei anlegen**

```python
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from ..db import get_session
from ..models.account import MailAccount, MailAccountCreate, MailAccountUpdate, MailAccountRead
from ..core.imap_worker import test_imap_connection

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

_SENTINEL = "***"
_manager_ref = None


def set_account_manager(manager) -> None:
    global _manager_ref
    _manager_ref = manager


def _mask(account: MailAccount) -> MailAccountRead:
    return MailAccountRead(
        id=account.id,
        name=account.name,
        imap_host=account.imap_host,
        imap_port=account.imap_port,
        imap_user=account.imap_user,
        imap_password="***" if account.imap_password else "",
        imap_tls=account.imap_tls,
        imap_folder=account.imap_folder,
        trash_folder=account.trash_folder,
        poll_interval_seconds=account.poll_interval_seconds,
        use_idle=account.use_idle,
        enabled=account.enabled,
        created_at=account.created_at,
    )


def _get_or_404(account_id: str, session: Session) -> MailAccount:
    account = session.get(MailAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.get("", response_model=list[MailAccountRead])
def list_accounts(session: Session = Depends(get_session)):
    accounts = session.exec(select(MailAccount).order_by(MailAccount.created_at)).all()
    return [_mask(a) for a in accounts]


@router.post("", response_model=MailAccountRead, status_code=201)
def create_account(body: MailAccountCreate, session: Session = Depends(get_session)):
    account = MailAccount(**body.model_dump())
    session.add(account)
    session.commit()
    session.refresh(account)
    if _manager_ref and account.enabled:
        _manager_ref.start_account(account)
    return _mask(account)


@router.put("/{account_id}", response_model=MailAccountRead)
def update_account(account_id: str, body: MailAccountUpdate, session: Session = Depends(get_session)):
    account = _get_or_404(account_id, session)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        if k == "imap_password" and v == _SENTINEL:
            continue
        setattr(account, k, v)
    session.add(account)
    session.commit()
    session.refresh(account)
    if _manager_ref:
        _manager_ref.restart_account(account)
    return _mask(account)


@router.delete("/{account_id}", status_code=204)
def delete_account(account_id: str, session: Session = Depends(get_session)):
    account = _get_or_404(account_id, session)
    if _manager_ref:
        _manager_ref.stop_account(account_id)
    session.delete(account)
    session.commit()


@router.post("/{account_id}/test-imap")
def test_account_imap(account_id: str, session: Session = Depends(get_session)):
    account = _get_or_404(account_id, session)
    ok, msg = test_imap_connection(
        account.imap_host, account.imap_port,
        account.imap_user, account.imap_password,
        account.imap_tls,
    )
    return {"ok": ok, "message": msg}


@router.post("/test-imap")
def test_imap_params(body: dict, session: Session = Depends(get_session)):
    """Verbindungstest mit beliebigen Parametern (vor dem Speichern)."""
    ok, msg = test_imap_connection(
        body.get("imap_host", ""),
        int(body.get("imap_port", 993)),
        body.get("imap_user", ""),
        body.get("imap_password", ""),
        bool(body.get("imap_tls", True)),
    )
    return {"ok": ok, "message": msg}


@router.post("/{account_id}/process-now", status_code=204)
async def process_account_now(account_id: str, session: Session = Depends(get_session)):
    _get_or_404(account_id, session)
    if _manager_ref:
        await _manager_ref.process_account_now(account_id)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/api/accounts.py
git commit -m "feat: add accounts REST API"
```

---

## Task 8: main.py, settings API, status API aktualisieren

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/settings.py`
- Modify: `backend/app/models/settings.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/api/status.py`

- [ ] **Step 1: `main.py` auf AccountManager umstellen**

```python
from __future__ import annotations
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .db import init_db
from .core.account_manager import AccountManager
from .api import rules, logs, settings
from .api.accounts import router as accounts_router, set_account_manager
from .api.status import router as status_router, set_account_manager as set_status_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

account_manager = AccountManager()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    set_account_manager(account_manager)
    set_status_manager(account_manager)
    account_manager.start()
    yield
    account_manager.stop()


app = FastAPI(title="MailSort", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rules.router)
app.include_router(logs.router)
app.include_router(settings.router)
app.include_router(accounts_router)
app.include_router(status_router)


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        from sqlmodel import Session
        from .db import engine
        from .config import get_setting
        with Session(engine) as s:
            required_key = get_setting(s, "api_key")
        if required_key:
            provided = request.headers.get("X-API-Key", "")
            if provided != required_key:
                raise HTTPException(status_code=401, detail="Invalid API key")
    return await call_next(request)


if os.path.isdir(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        index = os.path.join(STATIC_DIR, "index.html")
        return FileResponse(index)
```

- [ ] **Step 2: `config.py` IMAP-Defaults entfernen**

```python
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
        "Classify this email into one of the provided folders. "
        "Respond with only the folder name."
    ),
    "ai_provider": "claude",
    "ai_base_url": "",
    "audit_retention_days": "90",
    "api_key": "",
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
    )
```

- [ ] **Step 3: `models/settings.py` IMAP-Felder entfernen**

```python
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
```

- [ ] **Step 4: `api/settings.py` IMAP-Endpoints entfernen**

```python
from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session
from ..db import get_session
from ..models import SettingsRead, SettingsUpdate
from ..config import get_all_settings, get_setting, set_setting, MASKED_KEYS

router = APIRouter(prefix="/api/settings", tags=["settings"])

_SENTINEL = "***"


class AiTestRequest(BaseModel):
    ai_provider: str = "claude"
    ai_api_key: str = ""
    ai_model: str = ""
    ai_base_url: str = ""


class PaperlessTestRequest(BaseModel):
    paperless_url: str = ""
    paperless_token: str = ""


@router.get("", response_model=SettingsRead)
def read_settings(session: Session = Depends(get_session)):
    return get_all_settings(session)


@router.put("", response_model=SettingsRead)
def update_settings(body: SettingsUpdate, session: Session = Depends(get_session)):
    data = body.model_dump(exclude_none=True)
    for key, value in data.items():
        if key in MASKED_KEYS and value == _SENTINEL:
            continue
        if isinstance(value, bool):
            set_setting(session, key, "true" if value else "false")
        else:
            set_setting(session, key, str(value))
    return get_all_settings(session)


@router.post("/test-paperless")
async def test_paperless(body: PaperlessTestRequest, session: Session = Depends(get_session)):
    from ..services.paperless import test_paperless_connection
    url = body.paperless_url or get_setting(session, "paperless_url")
    token = (
        get_setting(session, "paperless_token")
        if body.paperless_token in (_SENTINEL, "")
        else body.paperless_token
    )
    ok, msg = await test_paperless_connection(url, token)
    return {"ok": ok, "message": msg}


@router.get("/ai-models")
async def list_ai_models(
    provider: str = "claude",
    api_key: str = "",
    base_url: str = "",
    session: Session = Depends(get_session),
):
    from ..core.providers import make_provider
    resolved_key = (
        get_setting(session, "ai_api_key")
        if api_key in (_SENTINEL, "")
        else api_key
    )
    resolved_base_url = base_url or get_setting(session, "ai_base_url")
    prov = make_provider(provider, resolved_key, "", resolved_base_url)
    models = await prov.list_models()
    return {"models": models}


@router.post("/test-ai")
async def test_ai(body: AiTestRequest, session: Session = Depends(get_session)):
    from ..core.providers import make_provider
    api_key = (
        get_setting(session, "ai_api_key")
        if body.ai_api_key in (_SENTINEL, "")
        else body.ai_api_key
    )
    model = body.ai_model or get_setting(session, "ai_model")
    provider_name = body.ai_provider or get_setting(session, "ai_provider") or "claude"
    base_url = body.ai_base_url or get_setting(session, "ai_base_url")
    provider = make_provider(provider_name, api_key, model, base_url)
    ok, msg = await provider.test_connection()
    return {"ok": ok, "message": msg}
```

- [ ] **Step 5: `api/status.py` auf AccountManager umstellen**

```python
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
```

- [ ] **Step 6: Backend starten und prüfen**

```bash
cd /Users/andreengele/PycharmProjects/MailSorter
MAILSORT_DATA_DIR=backend/data .venv/bin/uvicorn backend.app.main:app --reload --port 8000
```

Erwartetes Verhalten: Server startet ohne Fehler, Migration läuft durch (prüfen in Logs). Dann `Ctrl+C`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/main.py backend/app/config.py backend/app/models/settings.py backend/app/api/settings.py backend/app/api/status.py
git commit -m "feat: wire AccountManager, remove IMAP from settings"
```

---

## Task 9: Frontend API-Client aktualisieren

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: `client.ts` vollständig ersetzen**

```typescript
const BASE = '/api'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const apiKey = localStorage.getItem('mailsort_api_key') ?? ''
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(apiKey ? { 'X-API-Key': apiKey } : {}),
      ...options.headers,
    },
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status}: ${text}`)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

// Rules
export type ConditionType = 'from_domain' | 'from_address' | 'subject_contains' | 'subject_regex' | 'has_attachment' | 'attachment_type' | 'body_contains' | 'to_address'
export type ActionType = 'move' | 'label' | 'paperless' | 'webhook' | 'keep' | 'trash'

export interface Condition {
  type: ConditionType
  value: string
}

export interface Rule {
  id: string
  name: string
  priority: number
  enabled: boolean
  conditions: Condition[]
  action: ActionType
  action_params: Record<string, string | boolean>
  account_id: string | null
  created_at: string
}

export interface RuleCreate {
  name: string
  priority: number
  enabled: boolean
  conditions: Condition[]
  action: ActionType
  action_params: Record<string, string | boolean>
  account_id?: string | null
}

export const rulesApi = {
  list: () => request<Rule[]>('/rules'),
  create: (data: RuleCreate) => request<Rule>('/rules', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<RuleCreate>) => request<Rule>(`/rules/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) => request<void>(`/rules/${id}`, { method: 'DELETE' }),
  reorder: (ids: string[]) => request<void>('/rules/reorder', { method: 'POST', body: JSON.stringify({ ids }) }),
  test: (data: object) => request<object>('/rules/test', { method: 'POST', body: JSON.stringify(data) }),
}

// Audit Logs
export interface AuditLog {
  id: string
  timestamp: string
  message_id: string
  from_address: string
  subject: string
  rule_id: string | null
  rule_name: string | null
  action: string
  target: string | null
  status: 'success' | 'error'
  error_msg: string | null
  account_id: string | null
  account_name: string | null
}

export interface LogsResponse {
  total: number
  page: number
  page_size: number
  items: AuditLog[]
}

export const logsApi = {
  list: (params: Record<string, string | number>) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v !== undefined).map(([k, v]) => [k, String(v)])).toString()
    return request<LogsResponse>(`/logs${qs ? '?' + qs : ''}`)
  },
  exportUrl: () => `${BASE}/logs/export`,
  purge: (days: number) => request<void>(`/logs?older_than_days=${days}`, { method: 'DELETE' }),
}

// Settings (ohne IMAP)
export interface Settings {
  paperless_url: string
  paperless_token: string
  ai_enabled: boolean
  ai_api_key: string
  ai_model: string
  ai_system_prompt: string
  ai_provider: string
  ai_base_url: string
  audit_retention_days: number
  api_key: string
}

export const settingsApi = {
  get: () => request<Settings>('/settings'),
  update: (data: Partial<Settings>) => request<Settings>('/settings', { method: 'PUT', body: JSON.stringify(data) }),
  testPaperless: (params: { paperless_url: string; paperless_token: string }) => request<{ ok: boolean; message: string }>('/settings/test-paperless', { method: 'POST', body: JSON.stringify(params) }),
  testAi: (params: { ai_provider: string; ai_api_key: string; ai_model: string; ai_base_url: string }) => request<{ ok: boolean; message: string }>('/settings/test-ai', { method: 'POST', body: JSON.stringify(params) }),
  listAiModels: (params: { provider: string; api_key?: string; base_url?: string }) => {
    const q = new URLSearchParams({ provider: params.provider, api_key: params.api_key ?? '', base_url: params.base_url ?? '' })
    return request<{ models: string[] }>(`/settings/ai-models?${q}`)
  },
}

// Mail Accounts
export interface MailAccount {
  id: string
  name: string
  imap_host: string
  imap_port: number
  imap_user: string
  imap_password: string
  imap_tls: boolean
  imap_folder: string
  trash_folder: string
  poll_interval_seconds: number
  use_idle: boolean
  enabled: boolean
  created_at: string
}

export interface MailAccountCreate {
  name: string
  imap_host: string
  imap_port: number
  imap_user: string
  imap_password: string
  imap_tls: boolean
  imap_folder: string
  trash_folder: string
  poll_interval_seconds: number
  use_idle: boolean
  enabled: boolean
}

export const accountsApi = {
  list: () => request<MailAccount[]>('/accounts'),
  create: (data: MailAccountCreate) => request<MailAccount>('/accounts', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<MailAccountCreate>) => request<MailAccount>(`/accounts/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: string) => request<void>(`/accounts/${id}`, { method: 'DELETE' }),
  testImap: (params: { imap_host: string; imap_port: number; imap_user: string; imap_password: string; imap_tls: boolean }) =>
    request<{ ok: boolean; message: string }>('/accounts/test-imap', { method: 'POST', body: JSON.stringify(params) }),
  testImapById: (id: string) => request<{ ok: boolean; message: string }>(`/accounts/${id}/test-imap`, { method: 'POST' }),
  processNow: (id: string) => request<void>(`/accounts/${id}/process-now`, { method: 'POST' }),
}

// Status
export interface TopRule {
  name: string
  count: number
}

export interface Status {
  worker_running: boolean
  idle_mode: boolean
  imap_configured: boolean
  paperless_configured: boolean
  mails_today: number
  mails_week: number
  ai_count_week: number
  top_rules: TopRule[]
  timestamp: string
}

export const statusApi = {
  get: () => request<Status>('/status'),
  start: () => request<void>('/worker/start', { method: 'POST' }),
  stop: () => request<void>('/worker/stop', { method: 'POST' }),
  processNow: () => request<void>('/worker/process-now', { method: 'POST' }),
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: update API client for multi-account"
```

---

## Task 10: AccountsPage erstellen

**Files:**
- Create: `frontend/src/pages/AccountsPage.tsx`

- [ ] **Step 1: Datei anlegen**

```tsx
import { useEffect, useState } from 'react'
import { accountsApi, type MailAccount, type MailAccountCreate } from '@/api/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Plus, Edit2, Trash2, CheckCircle, AlertCircle, Loader2, RefreshCw } from 'lucide-react'

const BLANK: MailAccountCreate = {
  name: '',
  imap_host: '',
  imap_port: 993,
  imap_user: '',
  imap_password: '',
  imap_tls: true,
  imap_folder: 'INBOX',
  trash_folder: 'Trash',
  poll_interval_seconds: 60,
  use_idle: false,
  enabled: true,
}

type TestState = { loading: boolean; ok?: boolean; message?: string }

function AccountForm({
  initial,
  onSave,
  onCancel,
}: {
  initial: MailAccountCreate
  onSave: (data: MailAccountCreate) => Promise<void>
  onCancel: () => void
}) {
  const [form, setForm] = useState<MailAccountCreate>(initial)
  const [saving, setSaving] = useState(false)
  const [test, setTest] = useState<TestState>({ loading: false })

  const set = <K extends keyof MailAccountCreate>(k: K, v: MailAccountCreate[K]) =>
    setForm(f => ({ ...f, [k]: v }))

  const handleSave = async () => {
    setSaving(true)
    await onSave(form)
    setSaving(false)
  }

  const runTest = async () => {
    setTest({ loading: true })
    try {
      const r = await accountsApi.testImap({
        imap_host: form.imap_host,
        imap_port: form.imap_port,
        imap_user: form.imap_user,
        imap_password: form.imap_password,
        imap_tls: form.imap_tls,
      })
      setTest({ loading: false, ...r })
    } catch (e) {
      setTest({ loading: false, ok: false, message: String(e) })
    }
  }

  return (
    <div className="space-y-4 p-4 border rounded-lg bg-muted/20">
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1 col-span-2">
          <Label>Account-Name</Label>
          <Input value={form.name} onChange={e => set('name', e.target.value)} placeholder="z.B. Privat, Arbeit" />
        </div>
        <div className="space-y-1 col-span-2 md:col-span-1">
          <Label>IMAP-Host</Label>
          <Input value={form.imap_host} onChange={e => set('imap_host', e.target.value)} placeholder="imap.example.com" />
        </div>
        <div className="space-y-1">
          <Label>Port</Label>
          <Input type="number" value={form.imap_port} onChange={e => set('imap_port', Number(e.target.value))} />
        </div>
        <div className="space-y-1 col-span-2">
          <Label>Benutzername</Label>
          <Input value={form.imap_user} onChange={e => set('imap_user', e.target.value)} placeholder="user@example.com" />
        </div>
        <div className="space-y-1 col-span-2">
          <Label>Passwort</Label>
          <Input type="password" value={form.imap_password} onChange={e => set('imap_password', e.target.value)} placeholder="••••••••" />
        </div>
        <div className="space-y-1">
          <Label>Posteingangsordner</Label>
          <Input value={form.imap_folder} onChange={e => set('imap_folder', e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label>Papierkorb-Ordner</Label>
          <Input value={form.trash_folder} onChange={e => set('trash_folder', e.target.value)} />
        </div>
      </div>
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <Switch checked={form.imap_tls} onCheckedChange={v => set('imap_tls', v)} />
          <Label>TLS</Label>
        </div>
        <div className="flex items-center gap-2">
          <Switch checked={form.use_idle} onCheckedChange={v => set('use_idle', v)} />
          <Label>IDLE-Modus</Label>
        </div>
        <div className="flex items-center gap-2">
          <Switch checked={form.enabled} onCheckedChange={v => set('enabled', v)} />
          <Label>Aktiv</Label>
        </div>
      </div>
      {!form.use_idle && (
        <div className="space-y-1">
          <Label>Polling-Intervall (Sekunden)</Label>
          <Input type="number" value={form.poll_interval_seconds} onChange={e => set('poll_interval_seconds', Number(e.target.value))} className="w-32" />
        </div>
      )}
      <div className="flex items-center gap-3 pt-1">
        <Button variant="outline" size="sm" onClick={runTest} disabled={test.loading}>
          {test.loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-1" />}
          Verbindung testen
        </Button>
        {test.ok === true && (
          <span className="flex items-center gap-1 text-sm text-green-600">
            <CheckCircle className="h-4 w-4" /> {test.message}
          </span>
        )}
        {test.ok === false && (
          <span className="flex items-center gap-1 text-sm text-red-600">
            <AlertCircle className="h-4 w-4" /> {test.message}
          </span>
        )}
      </div>
      <div className="flex justify-end gap-2 pt-2 border-t">
        <Button variant="outline" onClick={onCancel}>Abbrechen</Button>
        <Button onClick={handleSave} disabled={saving || !form.name}>
          {saving ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
          Speichern
        </Button>
      </div>
    </div>
  )
}

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<MailAccount[]>([])
  const [editing, setEditing] = useState<{ id?: string; open: boolean }>({ open: false })

  const load = async () => setAccounts(await accountsApi.list())
  useEffect(() => { load() }, [])

  const handleSave = async (data: MailAccountCreate) => {
    if (editing.id) {
      await accountsApi.update(editing.id, data)
    } else {
      await accountsApi.create(data)
    }
    setEditing({ open: false })
    await load()
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Account löschen? Verknüpfte Regeln werden global.')) return
    await accountsApi.delete(id)
    await load()
  }

  const handleToggle = async (account: MailAccount) => {
    await accountsApi.update(account.id, { enabled: !account.enabled })
    await load()
  }

  const editingAccount = accounts.find(a => a.id === editing.id)

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Mail-Accounts</h1>
        <Button onClick={() => setEditing({ open: true })}>
          <Plus className="h-4 w-4 mr-1" /> Account hinzufügen
        </Button>
      </div>

      {editing.open && !editing.id && (
        <AccountForm
          initial={BLANK}
          onSave={handleSave}
          onCancel={() => setEditing({ open: false })}
        />
      )}

      {accounts.length === 0 && !editing.open && (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            Noch kein Account konfiguriert. Klicke auf „Account hinzufügen".
          </CardContent>
        </Card>
      )}

      <div className="space-y-3">
        {accounts.map(account => (
          <Card key={account.id}>
            {editing.open && editing.id === account.id ? (
              <CardContent className="pt-4">
                <AccountForm
                  initial={{
                    name: account.name,
                    imap_host: account.imap_host,
                    imap_port: account.imap_port,
                    imap_user: account.imap_user,
                    imap_password: account.imap_password,
                    imap_tls: account.imap_tls,
                    imap_folder: account.imap_folder,
                    trash_folder: account.trash_folder,
                    poll_interval_seconds: account.poll_interval_seconds,
                    use_idle: account.use_idle,
                    enabled: account.enabled,
                  }}
                  onSave={handleSave}
                  onCancel={() => setEditing({ open: false })}
                />
              </CardContent>
            ) : (
              <>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">{account.name}</CardTitle>
                    <div className="flex items-center gap-2">
                      <Switch checked={account.enabled} onCheckedChange={() => handleToggle(account)} />
                      <Button variant="ghost" size="icon" onClick={() => setEditing({ id: account.id, open: true })}>
                        <Edit2 className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => handleDelete(account.id)}>
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="text-sm text-muted-foreground space-y-0.5">
                    <div>{account.imap_user} @ {account.imap_host}:{account.imap_port}</div>
                    <div>Ordner: {account.imap_folder} · Papierkorb: {account.trash_folder}</div>
                    <div>{account.use_idle ? 'IDLE-Modus' : `Polling alle ${account.poll_interval_seconds}s`} · TLS: {account.imap_tls ? 'ja' : 'nein'}</div>
                  </div>
                </CardContent>
              </>
            )}
          </Card>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/AccountsPage.tsx
git commit -m "feat: add AccountsPage component"
```

---

## Task 11: Navigation und Routing aktualisieren

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/layout/Layout.tsx`

- [ ] **Step 1: `App.tsx` Route hinzufügen**

```tsx
import { Routes, Route } from 'react-router-dom'
import Layout from '@/components/layout/Layout'
import Dashboard from '@/pages/Dashboard'
import AccountsPage from '@/pages/AccountsPage'
import Rules from '@/pages/Rules'
import Logs from '@/pages/Logs'
import SettingsPage from '@/pages/SettingsPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="accounts" element={<AccountsPage />} />
        <Route path="rules" element={<Rules />} />
        <Route path="logs" element={<Logs />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  )
}
```

- [ ] **Step 2: `Layout.tsx` Nav-Eintrag hinzufügen**

In `Layout.tsx` die `nav`-Array und `PAGE_TITLES` aktualisieren. Import `Server` aus lucide-react hinzufügen:

```tsx
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { LayoutDashboard, ListFilter, Settings, ScrollText, Mail, Sun, Moon, Zap, Server } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useTheme } from '@/hooks/useTheme'

const nav = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/accounts', label: 'Accounts', icon: Server, end: false },
  { to: '/rules', label: 'Regeln', icon: ListFilter, end: false },
  { to: '/logs', label: 'Audit-Log', icon: ScrollText, end: false },
  { to: '/settings', label: 'Einstellungen', icon: Settings, end: false },
]

const PAGE_TITLES: Record<string, string> = {
  '/': 'Dashboard',
  '/accounts': 'Mail-Accounts',
  '/rules': 'Regeln',
  '/logs': 'Audit-Log',
  '/settings': 'Einstellungen',
}
```

Der Rest der `Layout.tsx`-Datei bleibt unverändert.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/layout/Layout.tsx
git commit -m "feat: add Accounts route and nav item"
```

---

## Task 12: Regel-Editor um Account-Dropdown erweitern

**Files:**
- Modify: `frontend/src/pages/Rules.tsx`

Die Änderungen betreffen:
1. `BLANK_RULE` um `account_id: null` erweitern
2. `RuleEditor` bekommt `accounts: MailAccount[]` als Prop
3. Account-Dropdown im Formular hinzufügen
4. `Rules`-Komponente lädt Accounts beim Mount

- [ ] **Step 1: Imports und BLANK_RULE anpassen**

Am Anfang von `Rules.tsx` den Import um `accountsApi` und `MailAccount` erweitern:

```tsx
import { rulesApi, accountsApi, settingsApi, type Rule, type RuleCreate, type Condition, type ActionType, type ConditionType, type MailAccount } from '@/api/client'
```

`BLANK_RULE` auf:

```tsx
const BLANK_RULE: RuleCreate = {
  name: '',
  priority: 100,
  enabled: true,
  conditions: [{ type: 'from_domain', value: '' }],
  action: 'move',
  action_params: { folder: '' },
  account_id: null,
}
```

- [ ] **Step 2: `RuleEditor` Prop-Typ und Account-Dropdown erweitern**

Die `RuleEditor`-Funktion bekommt `accounts: MailAccount[]` als neuen Prop:

```tsx
function RuleEditor({ initial, onSave, onClose, paperlessOk, accounts }: {
  initial: RuleCreate
  onSave: (r: RuleCreate) => void
  onClose: () => void
  paperlessOk: boolean
  accounts: MailAccount[]
}) {
```

Direkt nach dem Aktions-Grid (nach dem `mark_as_read`-Switch, vor der Test-Sektion) folgenden Block einfügen:

```tsx
          <div className="space-y-1">
            <Label>Account (optional)</Label>
            <select
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
              value={form.account_id ?? ''}
              onChange={e => setField('account_id', e.target.value || null)}
            >
              <option value="">Alle Accounts (global)</option>
              {accounts.map(a => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </div>
```

- [ ] **Step 3: `Rules`-Komponente lädt Accounts**

In der `Rules`-Komponente State für Accounts hinzufügen und beim Mount laden:

```tsx
export default function Rules() {
  const [rules, setRules] = useState<Rule[]>([])
  const [accounts, setAccounts] = useState<MailAccount[]>([])
  const [editing, setEditing] = useState<{ rule?: Rule; open: boolean }>({ open: false })
  const [paperlessOk, setPaperlessOk] = useState(false)

  useEffect(() => {
    settingsApi.get().then(s => setPaperlessOk(!!(s.paperless_url && s.paperless_token)))
    accountsApi.list().then(setAccounts)
  }, [])
```

- [ ] **Step 4: `RuleEditor` Aufruf um `accounts`-Prop erweitern**

Im JSX der `Rules`-Komponente:

```tsx
      {editing.open && (
        <RuleEditor
          initial={editing.rule ? {
            name: editing.rule.name,
            priority: editing.rule.priority,
            enabled: editing.rule.enabled,
            conditions: editing.rule.conditions,
            action: editing.rule.action,
            action_params: editing.rule.action_params,
            account_id: editing.rule.account_id,
          } : BLANK_RULE}
          onSave={handleSave}
          onClose={() => setEditing({ open: false })}
          paperlessOk={paperlessOk}
          accounts={accounts}
        />
      )}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Rules.tsx
git commit -m "feat: add account filter to rule editor"
```

---

## Task 13: Audit-Log Account-Spalte hinzufügen

**Files:**
- Modify: `frontend/src/pages/Logs.tsx`

- [ ] **Step 1: Account-Daten laden und Spalte anzeigen**

In `Logs.tsx`:

1. Import um `accountsApi` und `MailAccount` erweitern:
```tsx
import { logsApi, accountsApi, type AuditLog, type LogsResponse } from '@/api/client'
```

2. State für Accounts hinzufügen und laden:
```tsx
  const [accounts, setAccounts] = useState<{ id: string; name: string }[]>([])
  useEffect(() => { accountsApi.list().then(setAccounts) }, [])
```

3. In der Tabellen-`<thead>` nach `<th className="px-4 py-2 text-left font-medium">Betreff</th>` (oder an passender Stelle):

Vor der `<table>`-Definition eine Variable definieren:
```tsx
  const multiAccount = accounts.length > 1
```

In `<thead>`, eine neue Spalte nach dem Betreff einfügen (nur wenn multiAccount):
```tsx
                {multiAccount && <th className="px-4 py-2 text-left font-medium">Account</th>}
```

4. In jeder `<tr>` in `<tbody>` analog eine `<td>` einfügen:
```tsx
                {multiAccount && <td className="px-4 py-2 text-sm text-muted-foreground">{item.account_name ?? '—'}</td>}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Logs.tsx
git commit -m "feat: show account column in audit log when multiple accounts exist"
```

---

## Task 14: Settings-Seite IMAP-Sektion entfernen

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`

- [ ] **Step 1: IMAP-Card und veraltete settingsApi-Aufrufe entfernen**

Die gesamte `<Card>` mit `<CardTitle>IMAP-Verbindung</CardTitle>` aus der `SettingsPage.tsx` entfernen. Das Interface `Settings` enthält keine IMAP-Felder mehr (bereits via `client.ts` erledigt).

Außerdem den `testImap`-Aufruf entfernen. Die `ImapTestRequest`-Referenzen entfernen.

Das `fetchModels`-Hook und der `useEffect` für Settings bleibt. Die `settings`-State-Initialisierung funktioniert weiterhin, da `Settings` jetzt nur noch Non-IMAP-Felder enthält.

Resultat: Die Seite zeigt nur noch die Cards „Paperless-NGX", „KI-Klassifizierung" und „Sicherheit & Wartung".

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/SettingsPage.tsx
git commit -m "feat: remove IMAP section from settings page"
```

---

## Task 15: End-to-End Test und Frontend-Build

- [ ] **Step 1: Backend starten**

```bash
cd /Users/andreengele/PycharmProjects/MailSorter
MAILSORT_DATA_DIR=backend/data .venv/bin/uvicorn backend.app.main:app --reload --port 8000
```

- [ ] **Step 2: Frontend-Dev-Server starten**

```bash
cd /Users/andreengele/PycharmProjects/MailSorter/frontend
npm run dev
```

- [ ] **Step 3: Manuell prüfen**

1. Browser auf `http://localhost:5173` öffnen
2. Navigation zeigt: Dashboard | Accounts | Regeln | Audit-Log | Einstellungen
3. Accounts-Seite: Account anlegen, Verbindung testen
4. Regeln-Seite: Neue Regel → Account-Dropdown zeigt alle Accounts + „Alle Accounts (global)"
5. Einstellungen-Seite: keine IMAP-Felder mehr
6. Audit-Log: Account-Spalte erscheint wenn 2+ Accounts vorhanden

- [ ] **Step 4: Frontend-Build**

```bash
cd /Users/andreengele/PycharmProjects/MailSorter/frontend
npm run build
```

Erwartet: Build erfolgreich, keine TypeScript-Fehler.

- [ ] **Step 5: Tests**

```bash
cd /Users/andreengele/PycharmProjects/MailSorter
.venv/bin/pytest backend/tests/ -v
```

Erwartet: alle Tests grün.

- [ ] **Step 6: Abschluss-Commit**

```bash
git add frontend/dist
git commit -m "feat: multi-account support complete"
```
