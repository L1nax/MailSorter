# KI-Regelvorschläge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** KI-Entscheidungen werden gezählt; bei N gleichen Mustern schlägt das System dem Nutzer automatisch eine permanente Regel vor, die dann ohne KI-Aufruf greift.

**Architecture:** KI-Provider liefern neben der Aktion strukturierte Signals (Signal-Typ + Wert). Eine `SuggestionService`-Klasse zählt Signals in der `ai_signal`-Tabelle und erstellt bei Erreichen des Schwellwerts einen Eintrag in `rule_suggestion`. Der Nutzer genehmigt Vorschläge in einer neuen `/suggestions`-UI-Seite.

**Tech Stack:** Python 3.12, FastAPI, SQLModel/SQLite, React 18, TypeScript, Tailwind CSS, shadcn/ui

---

## Dateiübersicht

| Datei | Aktion |
|-------|--------|
| `backend/app/models/suggestion.py` | Neu: `AISignal`, `RuleSuggestion`, `SuggestionStatus` |
| `backend/app/models/__init__.py` | Modify: neue Exports |
| `backend/app/db.py` | Modify: Migration für `suggestion_threshold`/`snooze_days` in `_migrate()` |
| `backend/app/models/settings.py` | Modify: `SettingsRead` + `SettingsUpdate` um 2 Felder |
| `backend/app/config.py` | Modify: `DEFAULTS` + `get_all_settings()` |
| `backend/app/core/providers/base.py` | Modify: `ClassificationResult.signals`, `_parse_signals()`, `_parse_response()` |
| `backend/app/core/providers/claude.py` | Modify: `max_tokens` 64 → 128 |
| `backend/app/core/providers/openai.py` | Modify: `max_tokens` 64 → 128 |
| `backend/app/core/suggestion_service.py` | Neu: `process_signals()` |
| `backend/app/core/imap_worker.py` | Modify: Signal-Prompt + Signal-Tracking nach KI-Klassifizierung |
| `backend/app/api/suggestions.py` | Neu: REST-Router `/api/suggestions` |
| `backend/app/main.py` | Modify: Router registrieren |
| `backend/tests/test_signals.py` | Neu: Tests für `_parse_response` mit Signals |
| `backend/tests/test_suggestion_service.py` | Neu: Tests für `SuggestionService` |
| `frontend/src/api/client.ts` | Modify: `suggestionsApi` Types + Functions |
| `frontend/src/pages/SuggestionsPage.tsx` | Neu: Vorschläge-Seite |
| `frontend/src/App.tsx` | Modify: `/suggestions` Route |
| `frontend/src/components/layout/Layout.tsx` | Modify: Nav-Eintrag + Badge |
| `frontend/src/pages/Dashboard.tsx` | Modify: Suggestion-Badge |
| `frontend/src/pages/SettingsPage.tsx` | Modify: KI-Vorschläge-Abschnitt |

---

## Task 1: DB-Modelle — AISignal + RuleSuggestion

**Files:**
- Create: `backend/app/models/suggestion.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Datei erstellen**

```python
# backend/app/models/suggestion.py
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
```

- [ ] **Step 2: `__init__.py` erweitern**

In `backend/app/models/__init__.py` die Import-Zeile und `__all__` ergänzen:

```python
from .rule import Rule, RuleCreate, RuleUpdate, RuleRead, RuleReorder, RuleTestRequest, ActionType, ConditionType
from .audit import AuditLog, AuditLogRead, AuditLogFilter, AuditStatus
from .settings import Settings, SettingsRead, SettingsUpdate
from .account import MailAccount, MailAccountCreate, MailAccountUpdate, MailAccountRead
from .suggestion import AISignal, RuleSuggestion, RuleSuggestionRead, SuggestionStatus

__all__ = [
    "Rule", "RuleCreate", "RuleUpdate", "RuleRead", "RuleReorder", "RuleTestRequest",
    "ActionType", "ConditionType",
    "AuditLog", "AuditLogRead", "AuditLogFilter", "AuditStatus",
    "Settings", "SettingsRead", "SettingsUpdate",
    "MailAccount", "MailAccountCreate", "MailAccountUpdate", "MailAccountRead",
    "AISignal", "RuleSuggestion", "RuleSuggestionRead", "SuggestionStatus",
]
```

- [ ] **Step 3: Verify — Tabellen werden angelegt**

```bash
cd /Users/andreengele/PycharmProjects/MailSorter/backend
MAILSORT_DATA_DIR=/tmp/mailsort_test python -c "
from app.db import init_db, engine
init_db()
from sqlalchemy import text
with engine.connect() as c:
    tables = [r[0] for r in c.execute(text(\"SELECT name FROM sqlite_master WHERE type='table'\")).fetchall()]
    print(tables)
    assert 'aisignal' in tables, 'aisignal fehlt'
    assert 'rulesuggestion' in tables, 'rulesuggestion fehlt'
    print('OK')
"
```

Erwartete Ausgabe enthält `aisignal` und `rulesuggestion`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/suggestion.py backend/app/models/__init__.py
git commit -m "feat: add AISignal and RuleSuggestion DB models"
```

---

## Task 2: Settings — suggestion_threshold + snooze_days

**Files:**
- Modify: `backend/app/models/settings.py`
- Modify: `backend/app/config.py`

- [ ] **Step 1: `SettingsRead` und `SettingsUpdate` erweitern**

In `backend/app/models/settings.py` die beiden Klassen um je zwei Felder ergänzen:

```python
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
    suggestion_threshold: int = 3
    suggestion_snooze_days: int = 30


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
    suggestion_threshold: int | None = None
    suggestion_snooze_days: int | None = None
```

- [ ] **Step 2: `config.py` — DEFAULTS + get_all_settings ergänzen**

In `backend/app/config.py` in `DEFAULTS` zwei Einträge hinzufügen:

```python
DEFAULTS: dict[str, str] = {
    # ... bestehende Einträge ...
    "suggestion_threshold": "3",
    "suggestion_snooze_days": "30",
}
```

Und in `get_all_settings` die Return-Anweisung ergänzen:

```python
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
```

- [ ] **Step 3: Verify**

```bash
cd /Users/andreengele/PycharmProjects/MailSorter/backend
MAILSORT_DATA_DIR=/tmp/mailsort_test python -c "
from app.db import init_db, engine
init_db()
from sqlmodel import Session
from app.config import get_all_settings
with Session(engine) as s:
    cfg = get_all_settings(s)
    assert cfg.suggestion_threshold == 3
    assert cfg.suggestion_snooze_days == 30
    print('OK:', cfg.suggestion_threshold, cfg.suggestion_snooze_days)
"
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/models/settings.py backend/app/config.py
git commit -m "feat: add suggestion_threshold and snooze_days settings"
```

---

## Task 3: ClassificationResult signals + _parse_response refactor

**Files:**
- Modify: `backend/app/core/providers/base.py`
- Modify: `backend/app/core/providers/claude.py`
- Modify: `backend/app/core/providers/openai.py`
- Test: `backend/tests/test_signals.py`

- [ ] **Step 1: Failing tests schreiben**

```python
# backend/tests/test_signals.py
from __future__ import annotations
import pytest
from app.core.providers.claude import ClaudeProvider
from app.core.providers.base import ClassificationResult
from app.models.rule import ActionType


def _provider() -> ClaudeProvider:
    return ClaudeProvider(api_key="test", model="claude-sonnet-4-6")


class TestSignalsParsing:
    def test_no_signals_line_returns_empty(self):
        p = _provider()
        result = p._parse_response("move:Rechnungen", ["Rechnungen"])
        assert result.action == ActionType.move
        assert result.signals == []

    def test_signals_line_parsed(self):
        p = _provider()
        result = p._parse_response(
            "move:Rechnungen\nsignals: from_domain:amazon.de, subject_contains:Rechnung",
            ["Rechnungen"],
        )
        assert result.action == ActionType.move
        assert result.params == {"folder": "Rechnungen"}
        assert {"type": "from_domain", "value": "amazon.de"} in result.signals
        assert {"type": "subject_contains", "value": "Rechnung"} in result.signals

    def test_unknown_signal_type_ignored(self):
        p = _provider()
        result = p._parse_response(
            "move:Spam\nsignals: unknown_type:foo, from_address:test@example.com",
            ["Spam"],
        )
        assert len(result.signals) == 1
        assert result.signals[0] == {"type": "from_address", "value": "test@example.com"}

    def test_signals_with_keep_action(self):
        p = _provider()
        result = p._parse_response(
            "keep\nsignals: from_domain:newsletter.com",
            [],
        )
        assert result.action == ActionType.keep
        assert result.signals == [{"type": "from_domain", "value": "newsletter.com"}]

    def test_signals_field_on_classification_result(self):
        r = ClassificationResult(ActionType.keep, {}, signals=[{"type": "from_domain", "value": "test.de"}])
        assert r.signals == [{"type": "from_domain", "value": "test.de"}]

    def test_classification_result_default_signals_empty(self):
        r = ClassificationResult(ActionType.keep, {})
        assert r.signals == []
```

- [ ] **Step 2: Tests ausführen (erwarte FAIL)**

```bash
cd /Users/andreengele/PycharmProjects/MailSorter/backend
.venv/bin/pytest tests/test_signals.py -v 2>&1 | tail -20
```

Erwartete Ausgabe: Mehrere `FAILED` oder `AttributeError` für `signals`.

- [ ] **Step 3: `base.py` implementieren**

```python
# backend/app/core/providers/base.py
from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from ...models.rule import ActionType

if TYPE_CHECKING:
    from ..imap_worker import RawMail

log = logging.getLogger(__name__)

ALLOWED_SIGNAL_TYPES = frozenset({
    "from_domain", "from_address", "subject_contains",
    "has_attachment", "attachment_type", "to_address",
})


def _parse_signals(signals_str: str) -> list[dict]:
    signals = []
    for part in signals_str.split(","):
        part = part.strip()
        if ":" not in part:
            continue
        typ, _, val = part.partition(":")
        typ = typ.strip()
        val = val.strip()
        if typ in ALLOWED_SIGNAL_TYPES and val:
            signals.append({"type": typ, "value": val})
    return signals


class ClassificationResult:
    __slots__ = ("action", "params", "warning", "signals")

    def __init__(
        self,
        action: ActionType,
        params: dict,
        warning: str = "",
        signals: list[dict] | None = None,
    ) -> None:
        self.action = action
        self.params = params
        self.warning = warning
        self.signals: list[dict] = signals if signals is not None else []


class AIProvider(ABC):
    @abstractmethod
    async def classify(
        self, mail: "RawMail", folders: list[str], prompt: str
    ) -> ClassificationResult: ...

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]: ...

    async def list_models(self) -> list[str]:
        return []

    def _build_prompt(self, mail: "RawMail", folders: list[str]) -> str:
        folders_str = "\n".join(f"- {f}" for f in folders) if folders else "(keine vorhanden)"
        has_pdf = any("pdf" in t.lower() for t in mail.attachment_types)
        if mail.attachment_types:
            attachment_info = f"Anhänge: {', '.join(mail.attachment_types)}"
        else:
            attachment_info = "Anhänge: keine"

        actions = "move:<Ordner> | keep | trash"
        if has_pdf:
            actions = "move:<Ordner> | paperless:<Ordner> | paperless | keep | trash"

        return (
            f"Aktion (genau eine): {actions}\n\n"
            f"Vorhandene Ordner:\n{folders_str}\n\n"
            f"From: {mail.from_address}\n"
            f"Subject: {mail.subject}\n"
            f"{attachment_info}\n\n"
            f"{mail.body[:4000]}"
        )

    def _parse_response(self, text: str, folders: list[str]) -> ClassificationResult:
        text = text.strip()
        lines = text.split("\n", 1)
        action_line = lines[0].strip()
        signals_line = lines[1].strip() if len(lines) > 1 else ""

        signals: list[dict] = []
        if signals_line.lower().startswith("signals:"):
            signals = _parse_signals(signals_line[len("signals:"):].strip())

        if not action_line or len(action_line) > 200:
            return ClassificationResult(
                ActionType.keep, {}, f"AI: ungültige Antwort: {action_line!r}", signals=signals
            )

        if action_line == "keep":
            return ClassificationResult(ActionType.keep, {}, signals=signals)

        if action_line == "trash":
            return ClassificationResult(ActionType.trash, {}, signals=signals)

        if action_line == "paperless":
            return ClassificationResult(ActionType.paperless, {}, signals=signals)

        if action_line.startswith("paperless:"):
            folder = action_line[len("paperless:"):].strip()
            params = {"folder": folder} if folder else {}
            return ClassificationResult(ActionType.paperless, params, signals=signals)

        if action_line.startswith("move:"):
            folder = action_line[len("move:"):].strip()
            if not folder:
                return ClassificationResult(
                    ActionType.keep, {}, "AI: move ohne Ordner", signals=signals
                )
            if folder not in folders:
                log.info("AI schlug neuen Ordner vor: %r", folder)
            return ClassificationResult(ActionType.move, {"folder": folder}, signals=signals)

        if action_line not in folders:
            log.info("AI schlug neuen Ordner vor (plain): %r", action_line)
        return ClassificationResult(ActionType.move, {"folder": action_line}, signals=signals)
```

- [ ] **Step 4: `claude.py` — max_tokens erhöhen**

In `backend/app/core/providers/claude.py` Zeile `max_tokens=64` auf `max_tokens=128` ändern.

- [ ] **Step 5: `openai.py` — max_tokens erhöhen**

In `backend/app/core/providers/openai.py` Zeile `max_tokens=64` auf `max_tokens=128` ändern.

- [ ] **Step 6: Tests ausführen (erwarte PASS)**

```bash
cd /Users/andreengele/PycharmProjects/MailSorter/backend
.venv/bin/pytest tests/test_signals.py -v 2>&1 | tail -15
```

Erwartete Ausgabe: Alle 6 Tests `PASSED`.

- [ ] **Step 7: Bestehende Tests noch grün**

```bash
cd /Users/andreengele/PycharmProjects/MailSorter/backend
.venv/bin/pytest tests/ -v 2>&1 | tail -20
```

Alle bisherigen Tests müssen weiterhin `PASSED` sein.

- [ ] **Step 8: Commit**

```bash
git add backend/app/core/providers/base.py backend/app/core/providers/claude.py backend/app/core/providers/openai.py backend/tests/test_signals.py
git commit -m "feat: add signals to ClassificationResult, refactor _parse_response"
```

---

## Task 4: SuggestionService

**Files:**
- Create: `backend/app/core/suggestion_service.py`
- Test: `backend/tests/test_suggestion_service.py`

- [ ] **Step 1: Failing tests schreiben**

```python
# backend/tests/test_suggestion_service.py
from __future__ import annotations
import pytest
from datetime import datetime, timedelta
from sqlmodel import Session, create_engine, SQLModel, select
from app.models.suggestion import AISignal, RuleSuggestion, SuggestionStatus
from app.models.settings import Settings
from app.core.suggestion_service import process_signals


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    # Import all models so metadata knows about them
    from app import models  # noqa
    SQLModel.metadata.create_all(engine)
    # Set threshold = 3
    with Session(engine) as s:
        s.add(Settings(key="suggestion_threshold", value="3"))
        s.add(Settings(key="suggestion_snooze_days", value="30"))
        s.commit()
    with Session(engine) as s:
        yield s


def _signals(typ: str = "from_domain", val: str = "amazon.de") -> list[dict]:
    return [{"type": typ, "value": val}]


class TestProcessSignals:
    def test_upserts_signal_count(self, session):
        process_signals(_signals(), "move", "Rechnungen", None, session)
        sig = session.exec(select(AISignal)).first()
        assert sig is not None
        assert sig.count == 1
        assert sig.signal_type == "from_domain"
        assert sig.signal_value == "amazon.de"

    def test_increments_on_second_call(self, session):
        process_signals(_signals(), "move", "Rechnungen", None, session)
        process_signals(_signals(), "move", "Rechnungen", None, session)
        sig = session.exec(select(AISignal)).first()
        assert sig.count == 2

    def test_no_suggestion_below_threshold(self, session):
        process_signals(_signals(), "move", "Rechnungen", None, session)
        process_signals(_signals(), "move", "Rechnungen", None, session)
        suggestions = session.exec(select(RuleSuggestion)).all()
        assert len(suggestions) == 0

    def test_creates_suggestion_at_threshold(self, session):
        for _ in range(3):
            process_signals(_signals(), "move", "Rechnungen", None, session)
        suggestions = session.exec(select(RuleSuggestion)).all()
        assert len(suggestions) == 1
        s = suggestions[0]
        assert s.status == SuggestionStatus.pending
        assert s.signal_type == "from_domain"
        assert s.signal_value == "amazon.de"
        assert s.suggested_rule_name == "[KI] amazon.de → Rechnungen"
        assert s.suggested_conditions == [
            {"type": "from_domain", "value": "amazon.de", "operator": "contains"}
        ]

    def test_no_duplicate_suggestion_when_pending(self, session):
        for _ in range(6):
            process_signals(_signals(), "move", "Rechnungen", None, session)
        suggestions = session.exec(select(RuleSuggestion)).all()
        assert len(suggestions) == 1

    def test_dismissed_blocks_new_suggestion(self, session):
        for _ in range(3):
            process_signals(_signals(), "move", "Rechnungen", None, session)
        suggestion = session.exec(select(RuleSuggestion)).first()
        suggestion.status = SuggestionStatus.dismissed
        session.add(suggestion)
        session.commit()
        # 3 more signals
        for _ in range(3):
            process_signals(_signals(), "move", "Rechnungen", None, session)
        suggestions = session.exec(select(RuleSuggestion)).all()
        assert len(suggestions) == 1
        assert suggestions[0].status == SuggestionStatus.dismissed

    def test_expired_snooze_reactivates(self, session):
        for _ in range(3):
            process_signals(_signals(), "move", "Rechnungen", None, session)
        suggestion = session.exec(select(RuleSuggestion)).first()
        suggestion.status = SuggestionStatus.snoozed
        suggestion.snooze_until = datetime.utcnow() - timedelta(days=1)
        session.add(suggestion)
        session.commit()
        # One more signal triggers reactivation
        process_signals(_signals(), "move", "Rechnungen", None, session)
        refreshed = session.exec(select(RuleSuggestion)).first()
        assert refreshed.status == SuggestionStatus.pending
        assert refreshed.snooze_until is None

    def test_active_snooze_blocks(self, session):
        for _ in range(3):
            process_signals(_signals(), "move", "Rechnungen", None, session)
        suggestion = session.exec(select(RuleSuggestion)).first()
        suggestion.status = SuggestionStatus.snoozed
        suggestion.snooze_until = datetime.utcnow() + timedelta(days=10)
        session.add(suggestion)
        session.commit()
        process_signals(_signals(), "move", "Rechnungen", None, session)
        refreshed = session.exec(select(RuleSuggestion)).first()
        assert refreshed.status == SuggestionStatus.snoozed
```

- [ ] **Step 2: Tests ausführen (erwarte FAIL)**

```bash
cd /Users/andreengele/PycharmProjects/MailSorter/backend
.venv/bin/pytest tests/test_suggestion_service.py -v 2>&1 | tail -15
```

Erwartete Ausgabe: `ImportError` oder `ModuleNotFoundError` für `suggestion_service`.

- [ ] **Step 3: `suggestion_service.py` implementieren**

```python
# backend/app/core/suggestion_service.py
from __future__ import annotations
import logging
from datetime import datetime
from sqlmodel import Session, select
from ..models.suggestion import AISignal, RuleSuggestion, SuggestionStatus
from ..config import get_setting

log = logging.getLogger(__name__)


def process_signals(
    signals: list[dict],
    action: str,
    target: str,
    account_id: str | None,
    session: Session,
) -> None:
    if not signals:
        return
    threshold = int(get_setting(session, "suggestion_threshold") or "3")

    for signal in signals:
        sig_type = signal.get("type", "")
        sig_value = signal.get("value", "")
        if not sig_type or not sig_value:
            continue
        _upsert_and_check(sig_type, sig_value, action, target, account_id, threshold, session)


def _upsert_and_check(
    sig_type: str,
    sig_value: str,
    action: str,
    target: str,
    account_id: str | None,
    threshold: int,
    session: Session,
) -> None:
    existing = session.exec(
        select(AISignal).where(
            AISignal.signal_type == sig_type,
            AISignal.signal_value == sig_value,
            AISignal.action == action,
            AISignal.target == target,
            AISignal.account_id == account_id,
        )
    ).first()

    if existing:
        existing.count += 1
        existing.last_seen = datetime.utcnow()
        session.add(existing)
    else:
        existing = AISignal(
            signal_type=sig_type,
            signal_value=sig_value,
            action=action,
            target=target,
            account_id=account_id,
        )
        session.add(existing)
    session.commit()
    session.refresh(existing)

    if existing.count < threshold:
        return

    _maybe_create_suggestion(sig_type, sig_value, action, target, account_id, session)


def _maybe_create_suggestion(
    sig_type: str,
    sig_value: str,
    action: str,
    target: str,
    account_id: str | None,
    session: Session,
) -> None:
    from ..models.rule import Rule
    now = datetime.utcnow()

    # Check if a rule already covers this signal
    rules = session.exec(select(Rule).where(Rule.enabled == True)).all()
    for rule in rules:
        for cond in (rule.conditions or []):
            if cond.get("type") == sig_type and cond.get("value") == sig_value:
                return

    # Check for existing suggestion
    existing = session.exec(
        select(RuleSuggestion).where(
            RuleSuggestion.signal_type == sig_type,
            RuleSuggestion.signal_value == sig_value,
            RuleSuggestion.action == action,
            RuleSuggestion.target == target,
            RuleSuggestion.account_id == account_id,
        )
    ).first()

    if existing:
        if existing.status == SuggestionStatus.dismissed:
            return
        if existing.status == SuggestionStatus.pending:
            return
        if existing.status == SuggestionStatus.accepted:
            return
        if existing.status == SuggestionStatus.snoozed:
            if existing.snooze_until and existing.snooze_until > now:
                return
            # Expired snooze — reactivate
            existing.status = SuggestionStatus.pending
            existing.snooze_until = None
            session.add(existing)
            session.commit()
            log.info("Regelvorschlag reaktiviert: %s → %s", sig_value, target)
        return

    conditions = [{"type": sig_type, "value": sig_value, "operator": "contains"}]
    suggestion = RuleSuggestion(
        signal_type=sig_type,
        signal_value=sig_value,
        action=action,
        target=target,
        suggested_conditions=conditions,
        suggested_rule_name=f"[KI] {sig_value} → {target}",
        account_id=account_id,
    )
    session.add(suggestion)
    session.commit()
    log.info("Regelvorschlag erstellt: %s → %s", sig_value, target)
```

- [ ] **Step 4: Tests ausführen (erwarte PASS)**

```bash
cd /Users/andreengele/PycharmProjects/MailSorter/backend
.venv/bin/pytest tests/test_suggestion_service.py -v 2>&1 | tail -20
```

Erwartete Ausgabe: Alle 8 Tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/suggestion_service.py backend/tests/test_suggestion_service.py
git commit -m "feat: implement SuggestionService for AI signal tracking"
```

---

## Task 5: IMAPWorker — Signal-Prompt + Signal-Tracking

**Files:**
- Modify: `backend/app/core/imap_worker.py`

Die Änderungen betreffen `_process_single` (ca. Zeile 303–413).

- [ ] **Step 1: Signal-Prompt-Anweisung hinzufügen**

Direkt nach dem Block der `format_lines` / `effective_prompt` (ca. Zeile 365–369 in `_process_single`), BEVOR `_provider.classify()` aufgerufen wird, folgende Zeilen einfügen:

Aktueller Code:
```python
effective_prompt += (
    "\n\nAntworte ausschließlich mit einer der folgenden Aktionen – "
    "kein weiterer Text, keine Erklärung:\n"
    + "\n".join(f"  {a}" for a in format_lines)
)
ai_result = _asyncio.run(_provider.classify(mail, target_folders, effective_prompt))
```

Ersetzen durch:
```python
effective_prompt += (
    "\n\nAntworte ausschließlich mit einer der folgenden Aktionen – "
    "kein weiterer Text, keine Erklärung:\n"
    + "\n".join(f"  {a}" for a in format_lines)
)
effective_prompt += (
    "\n\nOptional: Füge nach der Aktionszeile eine zweite Zeile mit dem "
    "ausschlaggebenden Signal hinzu:\n"
    "signals: <typ>:<wert>\n"
    "Erlaubte Typen: from_domain, from_address, subject_contains, "
    "has_attachment, attachment_type, to_address"
)
ai_result = _asyncio.run(_provider.classify(mail, target_folders, effective_prompt))
```

- [ ] **Step 2: Signal-Tracking nach KI-Klassifizierung hinzufügen**

Direkt nach den Zeilen (ca. Zeile 370–374):
```python
rule_name = "AI"
action_type = ai_result.action
action_params = ai_result.params
ai_warning = ai_result.warning
```

Folgendes einfügen:
```python
if ai_result.signals:
    from .suggestion_service import process_signals as _track_signals
    with Session(engine) as _s:
        _track_signals(
            ai_result.signals,
            str(action_type),
            action_params.get("folder", ""),
            self.account.id,
            _s,
        )
```

- [ ] **Step 3: Verify — keine Import-Fehler**

```bash
cd /Users/andreengele/PycharmProjects/MailSorter/backend
MAILSORT_DATA_DIR=/tmp/mailsort_test python -c "from app.core.imap_worker import IMAPWorker; print('OK')"
```

Erwartete Ausgabe: `OK`

- [ ] **Step 4: Alle Tests noch grün**

```bash
cd /Users/andreengele/PycharmProjects/MailSorter/backend
.venv/bin/pytest tests/ -v 2>&1 | tail -20
```

Alle Tests `PASSED`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/imap_worker.py
git commit -m "feat: extend AI prompt for signals, track signals after classification"
```

---

## Task 6: REST API — /api/suggestions Router

**Files:**
- Create: `backend/app/api/suggestions.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Router erstellen**

```python
# backend/app/api/suggestions.py
from __future__ import annotations
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, func, or_
from ..db import get_session
from ..models.suggestion import RuleSuggestion, RuleSuggestionRead, SuggestionStatus
from ..models.rule import Rule, ActionType

router = APIRouter(prefix="/api/suggestions", tags=["suggestions"])


def _get_or_404(suggestion_id: str, session: Session) -> RuleSuggestion:
    obj = session.get(RuleSuggestion, suggestion_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return obj


@router.get("", response_model=list[RuleSuggestionRead])
def list_suggestions(
    status: str | None = None,
    session: Session = Depends(get_session),
):
    now = datetime.utcnow()
    if status:
        query = select(RuleSuggestion).where(RuleSuggestion.status == status)
    else:
        query = select(RuleSuggestion).where(
            RuleSuggestion.status == SuggestionStatus.pending
        )
    return session.exec(query.order_by(RuleSuggestion.created_at.desc())).all()


@router.get("/count")
def count_suggestions(session: Session = Depends(get_session)):
    n = session.exec(
        select(func.count(RuleSuggestion.id)).where(
            RuleSuggestion.status == SuggestionStatus.pending
        )
    ).one()
    return {"count": n}


@router.post("/{suggestion_id}/accept", response_model=RuleSuggestionRead)
def accept_suggestion(suggestion_id: str, session: Session = Depends(get_session)):
    obj = _get_or_404(suggestion_id, session)
    if obj.status != SuggestionStatus.pending:
        raise HTTPException(status_code=400, detail="Suggestion is not pending")

    # Compute next priority
    max_priority = session.exec(select(func.max(Rule.priority))).one() or 0
    new_priority = (max_priority or 0) + 1

    action_type = ActionType(obj.action)
    action_params: dict = {}
    if obj.target:
        action_params["folder"] = obj.target

    rule = Rule(
        name=obj.suggested_rule_name,
        priority=new_priority,
        enabled=True,
        conditions=obj.suggested_conditions,
        action=action_type,
        action_params=action_params,
        account_id=obj.account_id,
    )
    session.add(rule)
    obj.status = SuggestionStatus.accepted
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


@router.post("/{suggestion_id}/snooze", response_model=RuleSuggestionRead)
def snooze_suggestion(
    suggestion_id: str,
    body: dict,
    session: Session = Depends(get_session),
):
    obj = _get_or_404(suggestion_id, session)
    days = int(body.get("days", 30))
    obj.status = SuggestionStatus.snoozed
    obj.snooze_until = datetime.utcnow() + timedelta(days=days)
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


@router.post("/{suggestion_id}/dismiss", response_model=RuleSuggestionRead)
def dismiss_suggestion(suggestion_id: str, session: Session = Depends(get_session)):
    obj = _get_or_404(suggestion_id, session)
    obj.status = SuggestionStatus.dismissed
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj
```

- [ ] **Step 2: Router in `main.py` registrieren**

In `backend/app/main.py` den Import und `include_router` hinzufügen:

```python
from .api import rules, logs, settings
from .api.accounts import router as accounts_router, set_account_manager
from .api.status import router as status_router, set_account_manager as set_status_manager
from .api.suggestions import router as suggestions_router  # neu
```

Und im App-Setup:
```python
app.include_router(rules.router)
app.include_router(logs.router)
app.include_router(settings.router)
app.include_router(accounts_router)
app.include_router(status_router)
app.include_router(suggestions_router)  # neu
```

- [ ] **Step 3: Verify — Server startet**

```bash
cd /Users/andreengele/PycharmProjects/MailSorter/backend
MAILSORT_DATA_DIR=/tmp/mailsort_test MAILSORT_SECRET_KEY=test .venv/bin/python -c "
from app.main import app
routes = [r.path for r in app.routes]
assert any('/api/suggestions' in r for r in routes), 'Router nicht registriert'
print('Routes OK:', [r for r in routes if 'suggestion' in r])
"
```

Erwartete Ausgabe: Liste mit `/api/suggestions`, `/api/suggestions/count`, etc.

- [ ] **Step 4: Alle Tests noch grün**

```bash
cd /Users/andreengele/PycharmProjects/MailSorter/backend
.venv/bin/pytest tests/ -v 2>&1 | tail -10
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/suggestions.py backend/app/main.py
git commit -m "feat: add /api/suggestions REST router"
```

---

## Task 7: Frontend API Client — suggestionsApi

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Types und API-Funktionen ans Ende von `client.ts` anhängen**

```typescript
// Suggestions
export type SuggestionStatus = 'pending' | 'accepted' | 'snoozed' | 'dismissed'

export interface RuleSuggestion {
  id: string
  signal_type: string
  signal_value: string
  action: string
  target: string
  suggested_conditions: Condition[]
  suggested_rule_name: string
  status: SuggestionStatus
  snooze_until: string | null
  created_at: string
  account_id: string | null
}

export const suggestionsApi = {
  list: (status?: string) => {
    const qs = status ? `?status=${status}` : ''
    return request<RuleSuggestion[]>(`/suggestions${qs}`)
  },
  count: () => request<{ count: number }>('/suggestions/count'),
  accept: (id: string) =>
    request<RuleSuggestion>(`/suggestions/${id}/accept`, { method: 'POST' }),
  snooze: (id: string, days: number) =>
    request<RuleSuggestion>(`/suggestions/${id}/snooze`, {
      method: 'POST',
      body: JSON.stringify({ days }),
    }),
  dismiss: (id: string) =>
    request<RuleSuggestion>(`/suggestions/${id}/dismiss`, { method: 'POST' }),
}
```

- [ ] **Step 2: Verify — TypeScript kompiliert**

```bash
cd /Users/andreengele/PycharmProjects/MailSorter/frontend
npm run build 2>&1 | tail -10
```

Erwartete Ausgabe: Build erfolgreich, keine TypeScript-Fehler.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add suggestionsApi types and client functions"
```

---

## Task 8: Frontend — SuggestionsPage

**Files:**
- Create: `frontend/src/pages/SuggestionsPage.tsx`

- [ ] **Step 1: Seite erstellen**

```tsx
// frontend/src/pages/SuggestionsPage.tsx
import { useEffect, useState } from 'react'
import { suggestionsApi, settingsApi, type RuleSuggestion } from '@/api/client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { CheckCircle, Clock, XCircle, Sparkles } from 'lucide-react'

const SIGNAL_TYPE_LABELS: Record<string, string> = {
  from_domain: 'Domain',
  from_address: 'Absender',
  subject_contains: 'Betreff enthält',
  has_attachment: 'Hat Anhang',
  attachment_type: 'Anhang-Typ',
  to_address: 'Empfänger',
}

const STATUS_LABELS: Record<string, string> = {
  pending: 'Offen',
  accepted: 'Angenommen',
  snoozed: 'Zurückgestellt',
  dismissed: 'Abgelehnt',
}

function AcceptModal({ suggestion, onConfirm, onCancel }: {
  suggestion: RuleSuggestion
  onConfirm: () => void
  onCancel: () => void
}) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-background border rounded-xl p-6 max-w-md w-full mx-4 space-y-4">
        <h2 className="text-lg font-semibold">Regel erstellen</h2>
        <p className="text-sm text-muted-foreground">Folgende Regel wird angelegt:</p>
        <div className="bg-secondary rounded-lg p-3 space-y-1 text-sm">
          <div><span className="font-medium">Name:</span> {suggestion.suggested_rule_name}</div>
          <div><span className="font-medium">Bedingung:</span> {SIGNAL_TYPE_LABELS[suggestion.signal_type] ?? suggestion.signal_type} = {suggestion.signal_value}</div>
          <div><span className="font-medium">Aktion:</span> {suggestion.action}:{suggestion.target}</div>
        </div>
        <div className="flex gap-2 justify-end">
          <Button variant="outline" onClick={onCancel}>Abbrechen</Button>
          <Button onClick={onConfirm}>Regel erstellen</Button>
        </div>
      </div>
    </div>
  )
}

export default function SuggestionsPage() {
  const [tab, setTab] = useState<'open' | 'history'>('open')
  const [suggestions, setSuggestions] = useState<RuleSuggestion[]>([])
  const [history, setHistory] = useState<RuleSuggestion[]>([])
  const [confirmSuggestion, setConfirmSuggestion] = useState<RuleSuggestion | null>(null)
  const [threshold, setThreshold] = useState('3')
  const [snoozeDays, setSnoozeDays] = useState('30')
  const [saving, setSaving] = useState(false)

  const loadData = async () => {
    const [open, hist, cfg] = await Promise.all([
      suggestionsApi.list(),
      suggestionsApi.list('accepted,snoozed,dismissed').catch(() => [] as RuleSuggestion[]),
      settingsApi.get(),
    ])
    setSuggestions(open)
    setThreshold(String(cfg.suggestion_threshold))
    setSnoozeDays(String(cfg.suggestion_snooze_days))
    // Load history: all non-pending
    const [acc, snz, dis] = await Promise.all([
      suggestionsApi.list('accepted'),
      suggestionsApi.list('snoozed'),
      suggestionsApi.list('dismissed'),
    ])
    setHistory([...acc, ...snz, ...dis].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    ))
  }

  useEffect(() => { loadData() }, [])

  const handleAccept = async (s: RuleSuggestion) => {
    setConfirmSuggestion(s)
  }

  const handleConfirmAccept = async () => {
    if (!confirmSuggestion) return
    await suggestionsApi.accept(confirmSuggestion.id)
    setConfirmSuggestion(null)
    loadData()
  }

  const handleSnooze = async (s: RuleSuggestion, days: number) => {
    await suggestionsApi.snooze(s.id, days)
    loadData()
  }

  const handleDismiss = async (s: RuleSuggestion) => {
    await suggestionsApi.dismiss(s.id)
    loadData()
  }

  const handleSaveSettings = async () => {
    setSaving(true)
    await settingsApi.update({
      suggestion_threshold: parseInt(threshold),
      suggestion_snooze_days: parseInt(snoozeDays),
    })
    setSaving(false)
  }

  return (
    <div className="space-y-6">
      {confirmSuggestion && (
        <AcceptModal
          suggestion={confirmSuggestion}
          onConfirm={handleConfirmAccept}
          onCancel={() => setConfirmSuggestion(null)}
        />
      )}

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold flex items-center gap-2">
          <Sparkles className="h-6 w-6 text-primary" />
          Regelvorschläge
        </h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b">
        {(['open', 'history'] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              tab === t
                ? 'border-primary text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            {t === 'open' ? `Offen (${suggestions.length})` : 'Verlauf'}
          </button>
        ))}
      </div>

      {tab === 'open' && (
        <Card>
          <CardContent className="p-0">
            {suggestions.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground text-sm">
                Keine offenen Regelvorschläge
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground text-xs uppercase tracking-wide">
                    <th className="text-left px-4 py-3">Signal</th>
                    <th className="text-left px-4 py-3">Wert</th>
                    <th className="text-left px-4 py-3">Aktion</th>
                    <th className="text-left px-4 py-3">Ziel</th>
                    <th className="text-right px-4 py-3">Aktionen</th>
                  </tr>
                </thead>
                <tbody>
                  {suggestions.map(s => (
                    <tr key={s.id} className="border-b last:border-0 hover:bg-secondary/30 transition-colors">
                      <td className="px-4 py-3 font-medium">
                        {SIGNAL_TYPE_LABELS[s.signal_type] ?? s.signal_type}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">{s.signal_value}</td>
                      <td className="px-4 py-3">{s.action}</td>
                      <td className="px-4 py-3">{s.target}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-2">
                          <Button size="sm" onClick={() => handleAccept(s)}>
                            <CheckCircle className="h-3.5 w-3.5 mr-1" /> Annehmen
                          </Button>
                          <Select onValueChange={v => handleSnooze(s, parseInt(v))}>
                            <SelectTrigger className="h-8 w-32 text-xs">
                              <Clock className="h-3.5 w-3.5 mr-1" />
                              <SelectValue placeholder="Snooze" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="7">7 Tage</SelectItem>
                              <SelectItem value="30">30 Tage</SelectItem>
                              <SelectItem value="90">90 Tage</SelectItem>
                            </SelectContent>
                          </Select>
                          <Button variant="outline" size="sm" onClick={() => handleDismiss(s)}>
                            <XCircle className="h-3.5 w-3.5 mr-1" /> Ablehnen
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      )}

      {tab === 'history' && (
        <Card>
          <CardContent className="p-0">
            {history.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground text-sm">Kein Verlauf</div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground text-xs uppercase tracking-wide">
                    <th className="text-left px-4 py-3">Signal</th>
                    <th className="text-left px-4 py-3">Wert</th>
                    <th className="text-left px-4 py-3">Ziel</th>
                    <th className="text-left px-4 py-3">Status</th>
                    <th className="text-left px-4 py-3">Datum</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map(s => (
                    <tr key={s.id} className="border-b last:border-0">
                      <td className="px-4 py-3">{SIGNAL_TYPE_LABELS[s.signal_type] ?? s.signal_type}</td>
                      <td className="px-4 py-3 font-mono text-xs">{s.signal_value}</td>
                      <td className="px-4 py-3">{s.target}</td>
                      <td className="px-4 py-3">
                        <Badge variant={s.status === 'accepted' ? 'default' : 'secondary'}>
                          {STATUS_LABELS[s.status] ?? s.status}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground text-xs">
                        {new Date(s.created_at).toLocaleDateString('de-DE')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      )}

      {/* Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Einstellungen</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4 max-w-sm">
            <div className="space-y-1">
              <Label htmlFor="threshold">Schwellwert (N)</Label>
              <Input
                id="threshold"
                type="number"
                min={1}
                max={20}
                value={threshold}
                onChange={e => setThreshold(e.target.value)}
                className="h-8 w-24"
              />
              <p className="text-xs text-muted-foreground">Anzahl gleicher KI-Entscheidungen</p>
            </div>
            <div className="space-y-1">
              <Label htmlFor="snooze">Snooze-Standard (Tage)</Label>
              <Input
                id="snooze"
                type="number"
                min={1}
                value={snoozeDays}
                onChange={e => setSnoozeDays(e.target.value)}
                className="h-8 w-24"
              />
              <p className="text-xs text-muted-foreground">Standard-Snooze-Dauer</p>
            </div>
          </div>
          <Button size="sm" onClick={handleSaveSettings} disabled={saving}>
            {saving ? 'Speichern...' : 'Einstellungen speichern'}
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
```

- [ ] **Step 2: Verify — TypeScript kompiliert**

```bash
cd /Users/andreengele/PycharmProjects/MailSorter/frontend
npm run build 2>&1 | tail -10
```

Keine Fehler.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/SuggestionsPage.tsx
git commit -m "feat: add SuggestionsPage with open/history tabs and settings"
```

---

## Task 9: Frontend — Routing + Navigation + Dashboard-Badge + Settings

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/layout/Layout.tsx`
- Modify: `frontend/src/pages/Dashboard.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx`

- [ ] **Step 1: Route in `App.tsx` registrieren**

```tsx
// frontend/src/App.tsx
import { Routes, Route } from 'react-router-dom'
import Layout from '@/components/layout/Layout'
import Dashboard from '@/pages/Dashboard'
import AccountsPage from '@/pages/AccountsPage'
import Rules from '@/pages/Rules'
import Logs from '@/pages/Logs'
import SettingsPage from '@/pages/SettingsPage'
import SuggestionsPage from '@/pages/SuggestionsPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="accounts" element={<AccountsPage />} />
        <Route path="rules" element={<Rules />} />
        <Route path="logs" element={<Logs />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="suggestions" element={<SuggestionsPage />} />
      </Route>
    </Routes>
  )
}
```

- [ ] **Step 2: Nav-Eintrag + Badge in `Layout.tsx` hinzufügen**

In `Layout.tsx` den Import und den `nav`-Array anpassen. Direkt nach `import { useTheme }` einfügen:

```tsx
import { useEffect, useState } from 'react'
import { suggestionsApi } from '@/api/client'
```

Den `nav`-Array anpassen (nach dem `rules`-Eintrag):

```tsx
const nav = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/accounts', label: 'Accounts', icon: Server, end: false },
  { to: '/rules', label: 'Regeln', icon: ListFilter, end: false },
  { to: '/suggestions', label: 'Vorschläge', icon: Sparkles, end: false },
  { to: '/logs', label: 'Audit-Log', icon: ScrollText, end: false },
  { to: '/settings', label: 'Einstellungen', icon: Settings, end: false },
]
```

Import `Sparkles` zu den lucide-react-Imports hinzufügen.

`PAGE_TITLES` ergänzen:

```tsx
const PAGE_TITLES: Record<string, string> = {
  '/': 'Dashboard',
  '/accounts': 'Mail-Accounts',
  '/rules': 'Regeln',
  '/suggestions': 'Regelvorschläge',
  '/logs': 'Audit-Log',
  '/settings': 'Einstellungen',
}
```

In der `Layout`-Komponente einen State für den Badge-Count hinzufügen:

```tsx
export default function Layout() {
  const { theme, toggle } = useTheme()
  const location = useLocation()
  const pageTitle = PAGE_TITLES[location.pathname] ?? 'MailSort'
  const [suggestionCount, setSuggestionCount] = useState(0)

  useEffect(() => {
    suggestionsApi.count().then(r => setSuggestionCount(r.count)).catch(() => {})
    const interval = setInterval(() => {
      suggestionsApi.count().then(r => setSuggestionCount(r.count)).catch(() => {})
    }, 60_000)
    return () => clearInterval(interval)
  }, [])
```

Im NavLink-Render-Teil den Badge für `Vorschläge` hinzufügen. Den NavLink-Inhalt für `/suggestions` erweitern:

```tsx
{({ isActive }) => (
  <>
    <Icon ... />
    <span className="truncate">{label}</span>
    {to === '/suggestions' && suggestionCount > 0 && !isActive && (
      <span className="ml-auto bg-primary text-primary-foreground text-[10px] font-bold rounded-full w-4 h-4 flex items-center justify-center shrink-0">
        {suggestionCount > 9 ? '9+' : suggestionCount}
      </span>
    )}
    {isActive && (
      <span className="ml-auto w-1.5 h-1.5 rounded-full bg-primary-foreground opacity-60 shrink-0" />
    )}
  </>
)}
```

Da das bestehende NavLink-Render-Pattern `isActive` verwendet, muss der Badge-Code so eingebaut werden, dass er nur erscheint wenn der Eintrag nicht aktiv ist. Der vollständige NavLink-Inhalt für alle Einträge bleibt gleich; nur für `/suggestions` kommt der Badge-Span hinzu.

- [ ] **Step 3: Dashboard-Badge in `Dashboard.tsx` hinzufügen**

Am Anfang der Dashboard-Komponente einen `suggestionCount`-State hinzufügen:

```tsx
import { useNavigate } from 'react-router-dom'
import { suggestionsApi } from '@/api/client'

export default function Dashboard() {
  // ... bestehende States ...
  const [suggestionCount, setSuggestionCount] = useState(0)
  const navigate = useNavigate()

  const refresh = async () => {
    const [s, l, sc] = await Promise.all([
      statusApi.get(),
      logsApi.list({ page: 1, page_size: 10 }),
      suggestionsApi.count(),
    ])
    setStatus(s)
    setLogs(l.items)
    setSuggestionCount(sc.count)
  }
```

Direkt unter der `<h1>Dashboard</h1>`-Überschrift (vor den Worker-Buttons) einen klickbaren Banner einfügen:

```tsx
{suggestionCount > 0 && (
  <button
    onClick={() => navigate('/suggestions')}
    className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary/10 border border-primary/20 text-sm text-primary hover:bg-primary/20 transition-colors"
  >
    <Sparkles className="h-4 w-4" />
    {suggestionCount} {suggestionCount === 1 ? 'Regelvorschlag' : 'Regelvorschläge'} verfügbar
  </button>
)}
```

`Sparkles` zu den lucide-react-Imports in `Dashboard.tsx` hinzufügen.

- [ ] **Step 4: Settings-Seite — KI-Vorschläge-Abschnitt**

In `frontend/src/pages/SettingsPage.tsx` den KI-Vorschläge-Abschnitt hinzufügen. Am Ende des bestehenden Formulars (vor dem Speichern-Button) einen neuen Card-Abschnitt einfügen:

```tsx
<Card>
  <CardHeader>
    <CardTitle>KI-Regelvorschläge</CardTitle>
  </CardHeader>
  <CardContent className="space-y-4">
    <div className="grid grid-cols-2 gap-4 max-w-sm">
      <div className="space-y-1">
        <Label htmlFor="suggestion_threshold">Schwellwert (N)</Label>
        <Input
          id="suggestion_threshold"
          type="number"
          min={1}
          max={20}
          value={form.suggestion_threshold ?? 3}
          onChange={e => setForm(f => ({ ...f, suggestion_threshold: parseInt(e.target.value) }))}
          className="h-8 w-24"
        />
        <p className="text-xs text-muted-foreground">
          Anzahl gleicher KI-Entscheidungen bis ein Vorschlag erscheint
        </p>
      </div>
      <div className="space-y-1">
        <Label htmlFor="suggestion_snooze_days">Snooze-Dauer (Tage)</Label>
        <Input
          id="suggestion_snooze_days"
          type="number"
          min={1}
          value={form.suggestion_snooze_days ?? 30}
          onChange={e => setForm(f => ({ ...f, suggestion_snooze_days: parseInt(e.target.value) }))}
          className="h-8 w-24"
        />
        <p className="text-xs text-muted-foreground">Standard-Snooze-Dauer für Vorschläge</p>
      </div>
    </div>
  </CardContent>
</Card>
```

Dazu `suggestion_threshold` und `suggestion_snooze_days` in den `form`-State aufnehmen (der State wird aus `settingsApi.get()` befüllt; da `Settings`-Interface jetzt die neuen Felder hat, wird das automatisch übernommen).

- [ ] **Step 5: Build prüfen**

```bash
cd /Users/andreengele/PycharmProjects/MailSorter/frontend
npm run build 2>&1 | tail -15
```

Keine Fehler.

- [ ] **Step 6: Alle Backend-Tests noch grün**

```bash
cd /Users/andreengele/PycharmProjects/MailSorter/backend
.venv/bin/pytest tests/ -v 2>&1 | tail -15
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/layout/Layout.tsx frontend/src/pages/Dashboard.tsx frontend/src/pages/SettingsPage.tsx
git commit -m "feat: add suggestions nav, dashboard badge, and settings section"
```

---

## Self-Review

**Spec-Abdeckung:**

| Spec-Anforderung | Task |
|-----------------|------|
| `ai_signal`-Tabelle | Task 1 |
| `rule_suggestion`-Tabelle | Task 1 |
| `suggestion_threshold` + `snooze_days` Settings | Task 2 |
| `ClassificationResult.signals` | Task 3 |
| `_parse_response` mit Signals-Zeile | Task 3 |
| Signal-Zählung + Vorschlag-Logik | Task 4 |
| Dismissed blockiert dauerhaft | Task 4 |
| Snooze-Ablauf reaktiviert | Task 4 |
| Aktiver Snooze blockiert | Task 4 |
| IMAPWorker Signal-Tracking | Task 5 |
| Signal-Prompt-Erweiterung | Task 5 |
| GET /api/suggestions | Task 6 |
| GET /api/suggestions/count | Task 6 |
| POST accept → Regel erstellen | Task 6 |
| POST snooze | Task 6 |
| POST dismiss | Task 6 |
| Accept: niedrigste Priorität + 1 | Task 6 |
| Frontend suggestionsApi | Task 7 |
| SuggestionsPage (Offen + Verlauf) | Task 8 |
| Bestätigungs-Modal bei Annehmen | Task 8 |
| Einstellungen auf der Seite | Task 8 |
| Route /suggestions | Task 9 |
| Nav-Eintrag + Badge | Task 9 |
| Dashboard-Badge | Task 9 |
| Settings-Abschnitt | Task 9 |

**Keine Platzhalter gefunden.**

**Typ-Konsistenz:** `RuleSuggestion` in Task 1 definiert, `RuleSuggestionRead` wird in Task 6 (API) und Task 7 (TS-Interface) verwendet. `SuggestionStatus`-Enum in Task 1 definiert, in Task 4 + 6 konsistent verwendet.
