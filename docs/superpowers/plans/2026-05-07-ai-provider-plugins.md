# KI-Provider-Adapter & optionales Paperless – Implementierungsplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** KI-Klassifizierung wird provider-agnostisch (Claude, OpenAI, Gemini, Ollama); Paperless-Aktion im Rule-Editor nur sichtbar wenn konfiguriert.

**Architecture:** Abstract Base Class `AIProvider` mit `classify()` und `test_connection()`; je eine Klasse pro Provider; Factory-Funktion liest Provider aus DB-Settings. Ollama teilt sich `OpenAIProvider` via `base_url`.

**Tech Stack:** Python (anthropic, openai, google-generativeai), FastAPI, React/TypeScript, pytest

---

## Dateiübersicht

| Datei | Aktion |
|-------|--------|
| `backend/requirements.txt` | Modify – openai, google-generativeai hinzufügen |
| `backend/app/core/providers/__init__.py` | Create – Factory `get_provider`, `make_provider` |
| `backend/app/core/providers/base.py` | Create – `AIProvider` ABC + `ClassificationResult` |
| `backend/app/core/providers/claude.py` | Create – Anthropic-Implementierung |
| `backend/app/core/providers/openai.py` | Create – OpenAI + Ollama-Implementierung |
| `backend/app/core/providers/gemini.py` | Create – Google Gemini-Implementierung |
| `backend/app/core/ai_classifier.py` | Modify – `AIClassifier` entfernen, Imports anpassen |
| `backend/app/core/imap_worker.py` | Modify – `get_provider` statt `AIClassifier` |
| `backend/app/models/settings.py` | Modify – `ai_provider`, `ai_base_url` Felder |
| `backend/app/config.py` | Modify – Defaults für neue Felder |
| `backend/app/api/settings.py` | Modify – `AiTestRequest` + `test-ai` Endpoint |
| `backend/tests/test_providers.py` | Create – Tests für alle Provider + Factory |
| `frontend/src/api/client.ts` | Modify – neue Settings-Felder |
| `frontend/src/pages/SettingsPage.tsx` | Modify – Provider-Dropdown + dynamische Felder |
| `frontend/src/pages/Rules.tsx` | Modify – Paperless nur sichtbar wenn konfiguriert |

---

## Task 1: Abhängigkeiten

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Zeile einfügen**

```text
# backend/requirements.txt – nach anthropic-Zeile einfügen:
openai>=1.0.0
google-generativeai>=0.8.0
```

- [ ] **Installation prüfen**

```bash
cd backend && pip install openai google-generativeai
```

Erwartete Ausgabe: beide Pakete installiert ohne Fehler.

- [ ] **Commit**

```bash
git add backend/requirements.txt
git commit -m "feat: add openai and google-generativeai dependencies"
```

---

## Task 2: Base-Klasse und ClassificationResult

**Files:**
- Create: `backend/app/core/providers/base.py`
- Create: `backend/app/core/providers/__init__.py` (vorerst leer)

- [ ] **Failing-Test schreiben** (`backend/tests/test_providers.py`)

```python
from __future__ import annotations
import asyncio
from app.core.providers.base import AIProvider, ClassificationResult
from app.models.rule import ActionType


class _DummyProvider(AIProvider):
    async def classify(self, mail, folders, prompt):
        return ClassificationResult(action=ActionType.keep, params={})

    async def test_connection(self):
        return True, "ok"


def test_classification_result_defaults():
    r = ClassificationResult(action=ActionType.move, params={"folder": "INBOX.Work"})
    assert r.action == ActionType.move
    assert r.params == {"folder": "INBOX.Work"}
    assert r.warning == ""


def test_build_prompt_contains_mail_fields():
    from app.core.imap_worker import RawMail
    mail = RawMail(
        uid=1, message_id="<t>", from_address="a@b.com",
        subject="Rechnung", to_address="me@c.com",
        body="Hallo Welt", has_attachment=False, attachment_types=[],
    )
    provider = _DummyProvider()
    prompt = provider._build_prompt(mail, ["INBOX.Rechnungen"])
    assert "a@b.com" in prompt
    assert "Rechnung" in prompt
    assert "INBOX.Rechnungen" in prompt
```

- [ ] **Test ausführen – muss FAIL**

```bash
cd backend && pytest tests/test_providers.py -v
```

Erwarteter Fehler: `ModuleNotFoundError: No module named 'app.core.providers'`

- [ ] **Leere `__init__.py` erstellen**

```python
# backend/app/core/providers/__init__.py
```

- [ ] **`base.py` erstellen**

```python
# backend/app/core/providers/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from ...models.rule import ActionType

if TYPE_CHECKING:
    from ..imap_worker import RawMail


class ClassificationResult:
    __slots__ = ("action", "params", "warning")

    def __init__(self, action: ActionType, params: dict, warning: str = "") -> None:
        self.action = action
        self.params = params
        self.warning = warning


class AIProvider(ABC):
    @abstractmethod
    async def classify(
        self, mail: "RawMail", folders: list[str], prompt: str
    ) -> ClassificationResult: ...

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]: ...

    def _build_prompt(self, mail: "RawMail", folders: list[str]) -> str:
        folders_str = "\n".join(f"- {f}" for f in folders)
        return (
            f"Available folders:\n{folders_str}\n\n"
            f"From: {mail.from_address}\n"
            f"Subject: {mail.subject}\n\n"
            f"{mail.body[:4000]}"
        )
```

- [ ] **Test ausführen – muss PASS**

```bash
cd backend && pytest tests/test_providers.py -v
```

- [ ] **Commit**

```bash
git add backend/app/core/providers/ backend/tests/test_providers.py
git commit -m "feat: add AIProvider base class and ClassificationResult"
```

---

## Task 3: ClaudeProvider

**Files:**
- Create: `backend/app/core/providers/claude.py`
- Modify: `backend/tests/test_providers.py`

- [ ] **Failing-Test hinzufügen** (an `test_providers.py` anhängen)

```python
import anthropic
from unittest.mock import MagicMock, patch
from app.core.providers.claude import ClaudeProvider
from app.core.imap_worker import RawMail


def _mail(subject="Test", body="Hello"):
    return RawMail(uid=1, message_id="<t>", from_address="a@b.com",
                   subject=subject, to_address="me@c.com", body=body,
                   has_attachment=False, attachment_types=[])


class TestClaudeProvider:
    def test_known_folder(self):
        provider = ClaudeProvider(api_key="key", model="claude-sonnet-4-6")
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="INBOX.Work")]

        with patch.object(provider.client.messages, "create", return_value=mock_resp):
            result = asyncio.run(provider.classify(_mail(), ["INBOX.Work"], "Classify."))

        assert result.action == ActionType.move
        assert result.params["folder"] == "INBOX.Work"
        assert result.warning == ""

    def test_unknown_folder_keeps(self):
        provider = ClaudeProvider(api_key="key", model="claude-sonnet-4-6")
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="INBOX.Unknown")]

        with patch.object(provider.client.messages, "create", return_value=mock_resp):
            result = asyncio.run(provider.classify(_mail(), ["INBOX.Work"], "Classify."))

        assert result.action == ActionType.keep
        assert "INBOX.Unknown" in result.warning

    def test_no_api_key_returns_keep(self):
        provider = ClaudeProvider(api_key="", model="claude-sonnet-4-6")
        result = asyncio.run(provider.classify(_mail(), ["INBOX.Work"], "Classify."))
        assert result.action == ActionType.keep
        assert "not configured" in result.warning

    def test_rate_limit_retries(self):
        provider = ClaudeProvider(api_key="key", model="claude-sonnet-4-6")
        from unittest.mock import AsyncMock
        with patch.object(
            provider.client.messages, "create",
            side_effect=anthropic.RateLimitError.__new__(anthropic.RateLimitError),
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = asyncio.run(provider.classify(_mail(), ["INBOX.Work"], "Classify."))
        assert result.action == ActionType.keep
        assert result.warning != ""
```

- [ ] **Test ausführen – muss FAIL**

```bash
cd backend && pytest tests/test_providers.py::TestClaudeProvider -v
```

Erwarteter Fehler: `ImportError: cannot import name 'ClaudeProvider'`

- [ ] **`claude.py` erstellen**

```python
# backend/app/core/providers/claude.py
from __future__ import annotations
import asyncio
import logging
from typing import TYPE_CHECKING
import anthropic
from .base import AIProvider, ClassificationResult
from ...models.rule import ActionType

if TYPE_CHECKING:
    from ..imap_worker import RawMail

log = logging.getLogger(__name__)
BACKOFF_DELAYS = [1, 2, 4]


class ClaudeProvider(AIProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model or "claude-sonnet-4-6"
        self.client = anthropic.Anthropic(api_key=api_key)

    async def classify(
        self, mail: "RawMail", folders: list[str], prompt: str
    ) -> ClassificationResult:
        if not self.api_key:
            return ClassificationResult(ActionType.keep, {}, "AI not configured: API key missing")

        user_msg = self._build_prompt(mail, folders)
        last_error: Exception | None = None

        for attempt, delay in enumerate([0] + BACKOFF_DELAYS):
            if delay:
                await asyncio.sleep(delay)
            try:
                response = await asyncio.to_thread(
                    self.client.messages.create,
                    model=self.model,
                    max_tokens=64,
                    system=prompt,
                    messages=[{"role": "user", "content": user_msg}],
                )
                folder = response.content[0].text.strip()
                if folder in folders:
                    return ClassificationResult(ActionType.move, {"folder": folder})
                log.warning("Claude returned unknown folder %r", folder)
                return ClassificationResult(ActionType.keep, {}, f"AI returned unknown folder: {folder}")
            except anthropic.RateLimitError as exc:
                last_error = exc
                log.warning("Claude rate limit (attempt %d/%d)", attempt + 1, len(BACKOFF_DELAYS) + 1)
            except Exception as exc:
                last_error = exc
                log.exception("Claude classifier error (attempt %d)", attempt + 1)
                break

        log.error("Claude classifier failed after retries: %s", last_error)
        return ClassificationResult(ActionType.keep, {}, f"AI failed: {last_error}")

    async def test_connection(self) -> tuple[bool, str]:
        if not self.api_key:
            return False, "No API key configured"
        try:
            await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True, "Connection successful"
        except Exception as exc:
            return False, str(exc)
```

- [ ] **Test ausführen – muss PASS**

```bash
cd backend && pytest tests/test_providers.py::TestClaudeProvider -v
```

- [ ] **Commit**

```bash
git add backend/app/core/providers/claude.py backend/tests/test_providers.py
git commit -m "feat: add ClaudeProvider"
```

---

## Task 4: OpenAIProvider (OpenAI + Ollama)

**Files:**
- Create: `backend/app/core/providers/openai.py`
- Modify: `backend/tests/test_providers.py`

- [ ] **Failing-Test hinzufügen**

```python
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.providers.openai import OpenAIProvider


class TestOpenAIProvider:
    def test_known_folder(self):
        provider = OpenAIProvider(
            api_key="key", model="gpt-4o-mini",
            base_url="https://api.openai.com/v1"
        )
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "INBOX.Work"

        with patch.object(
            provider.client.chat.completions, "create",
            new_callable=AsyncMock, return_value=mock_resp
        ):
            result = asyncio.run(provider.classify(_mail(), ["INBOX.Work"], "Classify."))

        assert result.action == ActionType.move
        assert result.params["folder"] == "INBOX.Work"

    def test_unknown_folder_keeps(self):
        provider = OpenAIProvider(api_key="key", model="gpt-4o-mini",
                                   base_url="https://api.openai.com/v1")
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "INBOX.Unknown"

        with patch.object(
            provider.client.chat.completions, "create",
            new_callable=AsyncMock, return_value=mock_resp
        ):
            result = asyncio.run(provider.classify(_mail(), ["INBOX.Work"], "Classify."))

        assert result.action == ActionType.keep
        assert "INBOX.Unknown" in result.warning

    def test_no_api_key_returns_keep(self):
        provider = OpenAIProvider(api_key="", model="gpt-4o-mini",
                                   base_url="https://api.openai.com/v1")
        result = asyncio.run(provider.classify(_mail(), ["INBOX.Work"], "Classify."))
        assert result.action == ActionType.keep
        assert "not configured" in result.warning
```

- [ ] **Test ausführen – muss FAIL**

```bash
cd backend && pytest tests/test_providers.py::TestOpenAIProvider -v
```

- [ ] **`openai.py` erstellen**

```python
# backend/app/core/providers/openai.py
from __future__ import annotations
import logging
from typing import TYPE_CHECKING
from openai import AsyncOpenAI
from .base import AIProvider, ClassificationResult
from ...models.rule import ActionType

if TYPE_CHECKING:
    from ..imap_worker import RawMail

log = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        self.api_key = api_key
        self.model = model or "gpt-4o-mini"
        self.client = AsyncOpenAI(api_key=api_key or "ollama", base_url=base_url)

    async def classify(
        self, mail: "RawMail", folders: list[str], prompt: str
    ) -> ClassificationResult:
        if not self.api_key:
            return ClassificationResult(ActionType.keep, {}, "AI not configured: API key missing")

        user_msg = self._build_prompt(mail, folders)
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                max_tokens=64,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_msg},
                ],
            )
            folder = response.choices[0].message.content.strip()
            if folder in folders:
                return ClassificationResult(ActionType.move, {"folder": folder})
            log.warning("OpenAI returned unknown folder %r", folder)
            return ClassificationResult(ActionType.keep, {}, f"AI returned unknown folder: {folder}")
        except Exception as exc:
            log.exception("OpenAI classifier error")
            return ClassificationResult(ActionType.keep, {}, f"AI failed: {exc}")

    async def test_connection(self) -> tuple[bool, str]:
        try:
            await self.client.chat.completions.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True, "Connection successful"
        except Exception as exc:
            return False, str(exc)
```

**Hinweis Ollama:** Ollama hat keine API-Key-Pflicht. Die Factory übergibt `api_key="ollama"` (Dummy) und `base_url="http://localhost:11434/v1"`. Der `test_no_api_key_returns_keep`-Test gilt daher nur für echte OpenAI-Aufrufe; für Ollama setzt die Factory immer `api_key="ollama"`.

- [ ] **Test ausführen – muss PASS**

```bash
cd backend && pytest tests/test_providers.py::TestOpenAIProvider -v
```

- [ ] **Commit**

```bash
git add backend/app/core/providers/openai.py backend/tests/test_providers.py
git commit -m "feat: add OpenAIProvider (OpenAI + Ollama)"
```

---

## Task 5: GeminiProvider

**Files:**
- Create: `backend/app/core/providers/gemini.py`
- Modify: `backend/tests/test_providers.py`

- [ ] **Failing-Test hinzufügen**

```python
from unittest.mock import MagicMock, patch
from app.core.providers.gemini import GeminiProvider


class TestGeminiProvider:
    def test_known_folder(self):
        provider = GeminiProvider(api_key="key", model="gemini-2.0-flash")
        mock_resp = MagicMock()
        mock_resp.text = "INBOX.Work"

        with patch("google.generativeai.GenerativeModel") as MockModel:
            MockModel.return_value.generate_content.return_value = mock_resp
            with patch("google.generativeai.configure"):
                provider._model = MockModel.return_value
                result = asyncio.run(provider.classify(_mail(), ["INBOX.Work"], "Classify."))

        assert result.action == ActionType.move
        assert result.params["folder"] == "INBOX.Work"

    def test_no_api_key_returns_keep(self):
        provider = GeminiProvider(api_key="", model="gemini-2.0-flash")
        result = asyncio.run(provider.classify(_mail(), ["INBOX.Work"], "Classify."))
        assert result.action == ActionType.keep
        assert "not configured" in result.warning
```

- [ ] **Test ausführen – muss FAIL**

```bash
cd backend && pytest tests/test_providers.py::TestGeminiProvider -v
```

- [ ] **`gemini.py` erstellen**

```python
# backend/app/core/providers/gemini.py
from __future__ import annotations
import asyncio
import logging
from typing import TYPE_CHECKING
import google.generativeai as genai
from .base import AIProvider, ClassificationResult
from ...models.rule import ActionType

if TYPE_CHECKING:
    from ..imap_worker import RawMail

log = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model or "gemini-2.0-flash"
        if api_key:
            genai.configure(api_key=api_key)
        self._model: genai.GenerativeModel | None = None

    def _get_model(self, system_prompt: str) -> genai.GenerativeModel:
        return genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt,
        )

    async def classify(
        self, mail: "RawMail", folders: list[str], prompt: str
    ) -> ClassificationResult:
        if not self.api_key:
            return ClassificationResult(ActionType.keep, {}, "AI not configured: API key missing")

        user_msg = self._build_prompt(mail, folders)
        try:
            model = self._model or self._get_model(prompt)
            response = await asyncio.to_thread(model.generate_content, user_msg)
            folder = response.text.strip()
            if folder in folders:
                return ClassificationResult(ActionType.move, {"folder": folder})
            log.warning("Gemini returned unknown folder %r", folder)
            return ClassificationResult(ActionType.keep, {}, f"AI returned unknown folder: {folder}")
        except Exception as exc:
            log.exception("Gemini classifier error")
            return ClassificationResult(ActionType.keep, {}, f"AI failed: {exc}")

    async def test_connection(self) -> tuple[bool, str]:
        if not self.api_key:
            return False, "No API key configured"
        try:
            model = genai.GenerativeModel(model_name=self.model)
            await asyncio.to_thread(model.generate_content, "ping")
            return True, "Connection successful"
        except Exception as exc:
            return False, str(exc)
```

- [ ] **Test ausführen – muss PASS**

```bash
cd backend && pytest tests/test_providers.py::TestGeminiProvider -v
```

- [ ] **Commit**

```bash
git add backend/app/core/providers/gemini.py backend/tests/test_providers.py
git commit -m "feat: add GeminiProvider"
```

---

## Task 6: Factory

**Files:**
- Modify: `backend/app/core/providers/__init__.py`
- Modify: `backend/tests/test_providers.py`

- [ ] **Failing-Test hinzufügen**

```python
from unittest.mock import MagicMock
from app.core.providers import get_provider, make_provider
from app.core.providers.claude import ClaudeProvider
from app.core.providers.openai import OpenAIProvider
from app.core.providers.gemini import GeminiProvider


def _mock_session(settings: dict):
    """Returns a mock session where get_setting(s, key) returns settings[key] or ''."""
    from app.config import DEFAULTS
    session = MagicMock()
    session.get.side_effect = lambda model, key: (
        MagicMock(value=settings.get(key, DEFAULTS.get(key, "")))
        if key in settings or key in DEFAULTS else None
    )
    return session


class TestFactory:
    def test_make_provider_claude(self):
        p = make_provider("claude", "key", "claude-sonnet-4-6", "")
        assert isinstance(p, ClaudeProvider)

    def test_make_provider_openai(self):
        p = make_provider("openai", "key", "gpt-4o-mini", "https://api.openai.com/v1")
        assert isinstance(p, OpenAIProvider)

    def test_make_provider_ollama(self):
        p = make_provider("ollama", "", "llama3.2", "http://localhost:11434/v1")
        assert isinstance(p, OpenAIProvider)

    def test_make_provider_gemini(self):
        p = make_provider("gemini", "key", "gemini-2.0-flash", "")
        assert isinstance(p, GeminiProvider)

    def test_make_provider_unknown_falls_back_to_claude(self):
        p = make_provider("unknown", "key", "", "")
        assert isinstance(p, ClaudeProvider)

    def test_get_provider_reads_from_session(self):
        session = _mock_session({"ai_provider": "openai", "ai_api_key": "k", "ai_model": "gpt-4o-mini", "ai_base_url": "https://api.openai.com/v1"})
        p = get_provider(session)
        assert isinstance(p, OpenAIProvider)
```

- [ ] **Test ausführen – muss FAIL**

```bash
cd backend && pytest tests/test_providers.py::TestFactory -v
```

- [ ] **`__init__.py` befüllen**

```python
# backend/app/core/providers/__init__.py
from __future__ import annotations
from typing import TYPE_CHECKING
from .base import AIProvider
from .claude import ClaudeProvider
from .openai import OpenAIProvider
from .gemini import GeminiProvider

if TYPE_CHECKING:
    from sqlmodel import Session

DEFAULT_MODELS: dict[str, str] = {
    "claude": "claude-sonnet-4-6",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.0-flash",
    "ollama": "llama3.2",
}


def make_provider(provider: str, api_key: str, model: str, base_url: str) -> AIProvider:
    model = model or DEFAULT_MODELS.get(provider, "")
    match provider:
        case "openai":
            return OpenAIProvider(api_key, model, base_url or "https://api.openai.com/v1")
        case "ollama":
            return OpenAIProvider("ollama", model, base_url or "http://localhost:11434/v1")
        case "gemini":
            return GeminiProvider(api_key, model)
        case _:  # "claude" und unbekannte Provider
            return ClaudeProvider(api_key, model or DEFAULT_MODELS["claude"])


def get_provider(session: "Session") -> AIProvider:
    from ...config import get_setting
    provider = get_setting(session, "ai_provider") or "claude"
    api_key = get_setting(session, "ai_api_key")
    model = get_setting(session, "ai_model")
    base_url = get_setting(session, "ai_base_url")
    return make_provider(provider, api_key, model, base_url)
```

- [ ] **Test ausführen – muss PASS**

```bash
cd backend && pytest tests/test_providers.py::TestFactory -v
```

- [ ] **Alle Provider-Tests laufen lassen**

```bash
cd backend && pytest tests/test_providers.py -v
```

Alle Tests grün.

- [ ] **Commit**

```bash
git add backend/app/core/providers/__init__.py backend/tests/test_providers.py
git commit -m "feat: add provider factory (get_provider, make_provider)"
```

---

## Task 7: ai_classifier.py refaktorieren

**Files:**
- Modify: `backend/app/core/ai_classifier.py`
- Modify: `backend/tests/test_ai_classifier.py`

- [ ] **Bestehende Tests anpassen** – `test_ai_classifier.py` komplett ersetzen

```python
# backend/tests/test_ai_classifier.py
from __future__ import annotations
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.core.providers.claude import ClaudeProvider
from app.core.providers.base import ClassificationResult
from app.core.imap_worker import RawMail
from app.models.rule import ActionType


def _make_mail(subject: str = "Test", body: str = "Hello") -> RawMail:
    return RawMail(
        uid=1, message_id="<test@test>", from_address="test@example.com",
        subject=subject, to_address="me@example.com", body=body,
        has_attachment=False, attachment_types=[],
    )


class TestClaudeProviderLegacy:
    """Smoke-Tests, die vorher in test_ai_classifier.py lagen."""

    def test_known_folder_returned(self):
        provider = ClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="INBOX.Work")]

        with patch.object(provider.client.messages, "create", return_value=mock_response):
            result = asyncio.run(
                provider.classify(_make_mail(), ["INBOX.Work", "INBOX.Shopping"], "Classify.")
            )

        assert result.action == ActionType.move
        assert result.params == {"folder": "INBOX.Work"}
        assert result.warning == ""

    def test_unknown_folder_keeps_mail(self):
        provider = ClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="INBOX.Unknown")]

        with patch.object(provider.client.messages, "create", return_value=mock_response):
            result = asyncio.run(
                provider.classify(_make_mail(), ["INBOX.Work"], "Classify.")
            )

        assert result.action == ActionType.keep
        assert "INBOX.Unknown" in result.warning
```

- [ ] **`ai_classifier.py` ersetzen**

```python
# backend/app/core/ai_classifier.py
"""Thin compatibility shim – provider logic lebt in app.core.providers.*"""
from __future__ import annotations
from .providers.base import ClassificationResult  # noqa: F401 – re-export für alte Imports
from .providers import get_provider, make_provider


async def test_ai_connection(api_key: str, model: str) -> tuple[bool, str]:
    """Für Rückwärtskompatibilität; neuer Code nutzt provider.test_connection()."""
    provider = make_provider("claude", api_key, model, "")
    return await provider.test_connection()
```

- [ ] **Alle Tests laufen lassen**

```bash
cd backend && pytest tests/ -v
```

Alle Tests grün.

- [ ] **Commit**

```bash
git add backend/app/core/ai_classifier.py backend/tests/test_ai_classifier.py
git commit -m "refactor: replace AIClassifier with provider delegation in ai_classifier.py"
```

---

## Task 8: imap_worker.py aktualisieren

**Files:**
- Modify: `backend/app/core/imap_worker.py` (Zeilen 297–308)

- [ ] **Änderung vornehmen** – den AI-Block in `_process_single` ersetzen

Suche diesen Block (ca. Zeile 297):
```python
elif ai_enabled and ai_key:
    import asyncio as _asyncio
    with Session(engine) as s:
        from sqlmodel import select as _select
        target_folders = [r.action_params.get("folder", "") for r in s.exec(_select(Rule)).all() if r.action_params.get("folder")]
    classifier = AIClassifier(ai_key, ai_model, ai_prompt, target_folders)
    ai_result = _asyncio.run(classifier.classify(mail))
```

Ersetzen durch:
```python
elif ai_enabled:
    import asyncio as _asyncio
    with Session(engine) as s:
        from .providers import get_provider as _get_provider
        from sqlmodel import select as _select
        _provider = _get_provider(s)
        target_folders = [r.action_params.get("folder", "") for r in s.exec(_select(Rule)).all() if r.action_params.get("folder")]
    ai_result = _asyncio.run(_provider.classify(mail, target_folders, ai_prompt))
```

- [ ] **Import `AIClassifier` am Dateianfang entfernen**

Suche und entferne:
```python
from .ai_classifier import AIClassifier
```

- [ ] **Tests laufen lassen**

```bash
cd backend && pytest tests/ -v
```

- [ ] **Commit**

```bash
git add backend/app/core/imap_worker.py
git commit -m "refactor: use get_provider in imap_worker instead of AIClassifier"
```

---

## Task 9: Settings-Modell und Config aktualisieren

**Files:**
- Modify: `backend/app/models/settings.py`
- Modify: `backend/app/config.py`

- [ ] **`settings.py` – neue Felder in SettingsRead und SettingsUpdate**

```python
# In SettingsRead – nach ai_system_prompt einfügen:
ai_provider: str = "claude"
ai_base_url: str = ""

# In SettingsUpdate – nach ai_system_prompt einfügen:
ai_provider: str | None = None
ai_base_url: str | None = None
```

- [ ] **`config.py` – neue Defaults in DEFAULTS**

```python
# In DEFAULTS dict einfügen (nach "ai_model"):
"ai_provider": "claude",
"ai_base_url": "",
```

- [ ] **`get_all_settings` in `config.py` aktualisieren** – neue Felder hinzufügen

```python
# In get_all_settings, nach ai_system_prompt:
ai_provider=g("ai_provider"),
ai_base_url=g("ai_base_url"),
```

- [ ] **Backend starten und prüfen**

```bash
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8080 &
curl -s http://localhost:8080/api/settings | python3 -m json.tool | grep ai_provider
```

Erwartete Ausgabe: `"ai_provider": "claude"`

```bash
kill %1
```

- [ ] **Commit**

```bash
git add backend/app/models/settings.py backend/app/config.py
git commit -m "feat: add ai_provider and ai_base_url settings fields"
```

---

## Task 10: test-ai Endpoint aktualisieren

**Files:**
- Modify: `backend/app/api/settings.py`

- [ ] **`AiTestRequest` erweitern**

```python
# Altes AiTestRequest ersetzen:
class AiTestRequest(BaseModel):
    ai_provider: str = "claude"
    ai_api_key: str = ""
    ai_model: str = ""
    ai_base_url: str = ""
```

- [ ] **`test_ai` Endpoint ersetzen**

```python
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

- [ ] **Manuell testen**

```bash
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8080 &
curl -s -X POST http://localhost:8080/api/settings/test-ai \
  -H "Content-Type: application/json" \
  -d '{"ai_provider":"claude","ai_api_key":"","ai_model":"","ai_base_url":""}'
kill %1
```

Erwartete Ausgabe: `{"ok":false,"message":"No API key configured"}`

- [ ] **Commit**

```bash
git add backend/app/api/settings.py
git commit -m "feat: update test-ai endpoint to support all AI providers"
```

---

## Task 11: Frontend – client.ts

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **`Settings` Interface erweitern**

```typescript
// In der Settings-Interface nach ai_system_prompt einfügen:
ai_provider: string
ai_base_url: string
```

- [ ] **`testAi` Params erweitern**

```typescript
// testAi Signatur in settingsApi:
testAi: (params: { ai_provider: string; ai_api_key: string; ai_model: string; ai_base_url: string }) =>
  request<{ ok: boolean; message: string }>('/settings/test-ai', { method: 'POST', body: JSON.stringify(params) }),
```

- [ ] **Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add ai_provider and ai_base_url to Settings type"
```

---

## Task 12: Frontend – SettingsPage.tsx

**Files:**
- Modify: `frontend/src/pages/SettingsPage.tsx`

- [ ] **KI-Sektion komplett ersetzen** – den Block innerhalb `<Card>` für KI-Klassifizierung

```tsx
<Card>
  <CardHeader><CardTitle>KI-Klassifizierung</CardTitle></CardHeader>
  <CardContent className="space-y-3">
    <div className="flex items-center gap-2">
      <Switch checked={settings.ai_enabled} onCheckedChange={v => update('ai_enabled', v)} />
      <Label>KI-Fallback aktivieren</Label>
    </div>
    {settings.ai_enabled && (
      <>
        <div className="space-y-1">
          <Label>Provider</Label>
          <select
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
            value={settings.ai_provider}
            onChange={e => update('ai_provider', e.target.value)}
          >
            <option value="claude">Claude (Anthropic)</option>
            <option value="openai">OpenAI</option>
            <option value="gemini">Gemini (Google)</option>
            <option value="ollama">Ollama (lokal)</option>
          </select>
        </div>
        {settings.ai_provider !== 'ollama' && (
          <div className="space-y-1">
            <Label>API-Key</Label>
            <Input type="password" value={settings.ai_api_key}
              onChange={e => update('ai_api_key', e.target.value)} placeholder="••••••••" />
          </div>
        )}
        {(settings.ai_provider === 'openai' || settings.ai_provider === 'ollama') && (
          <div className="space-y-1">
            <Label>Base URL</Label>
            <Input value={settings.ai_base_url}
              onChange={e => update('ai_base_url', e.target.value)}
              placeholder={settings.ai_provider === 'ollama' ? 'http://localhost:11434/v1' : 'https://api.openai.com/v1'} />
          </div>
        )}
        <div className="space-y-1">
          <Label>Modell</Label>
          <Input value={settings.ai_model} onChange={e => update('ai_model', e.target.value)}
            placeholder={{ claude: 'claude-sonnet-4-6', openai: 'gpt-4o-mini', gemini: 'gemini-2.0-flash', ollama: 'llama3.2' }[settings.ai_provider] ?? ''} />
        </div>
        <div className="space-y-1">
          <Label>System-Prompt</Label>
          <textarea
            className="flex min-h-[80px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            value={settings.ai_system_prompt}
            onChange={e => update('ai_system_prompt', e.target.value)}
          />
        </div>
        <TestButton onTest={() => {
          const missing: string[] = []
          if (settings.ai_provider !== 'ollama' && !settings.ai_api_key) missing.push('API-Key')
          if (missing.length > 0)
            return Promise.resolve({ ok: false, message: `Fehlende Felder: ${missing.join(', ')}` })
          return settingsApi.testAi({
            ai_provider: settings.ai_provider,
            ai_api_key: settings.ai_api_key,
            ai_model: settings.ai_model,
            ai_base_url: settings.ai_base_url,
          })
        }} />
      </>
    )}
  </CardContent>
</Card>
```

- [ ] **Frontend starten und manuell testen**

```bash
cd frontend && npm run dev
```

Browser öffnen → Einstellungen → KI-Sektion:
- Provider-Dropdown zeigt alle 4 Optionen
- Bei "Ollama": API-Key-Feld verschwindet, Base-URL erscheint
- Bei "OpenAI": API-Key + Base-URL beide sichtbar
- Bei "Claude" / "Gemini": nur API-Key, keine Base-URL

- [ ] **Commit**

```bash
git add frontend/src/pages/SettingsPage.tsx
git commit -m "feat: add provider dropdown and dynamic fields to AI settings"
```

---

## Task 13: Frontend – Paperless im Rule-Editor optional

**Files:**
- Modify: `frontend/src/pages/Rules.tsx`

- [ ] **Import ergänzen** (am Dateianfang)

```tsx
import { settingsApi } from '@/api/client'
```

- [ ] **State + Effect in `Rules`-Komponente** (direkt nach `const [rules, setRules] ...`)

```tsx
const [paperlessOk, setPaperlessOk] = useState(false)
useEffect(() => {
  settingsApi.get().then(s => setPaperlessOk(!!(s.paperless_url && s.paperless_token)))
}, [])
```

- [ ] **`ACTION_TYPES`-Konstante dynamisch filtern** – `RuleEditor` bekommt ein neues Prop

```tsx
// RuleEditor Signatur ändern:
function RuleEditor({
  initial, onSave, onClose, paperlessOk
}: {
  initial: RuleCreate; onSave: (r: RuleCreate) => void; onClose: () => void; paperlessOk: boolean
}) {
  // Zeile mit ACTION_TYPES.map ersetzen:
  const availableActions = ACTION_TYPES.filter(a => a.value !== 'paperless' || paperlessOk)
  // ...im JSX:
  // {ACTION_TYPES.map(...)}  →  {availableActions.map(...)}
```

- [ ] **`RuleEditor` Aufruf in `Rules` aktualisieren**

```tsx
<RuleEditor
  initial={...}
  onSave={handleSave}
  onClose={() => setEditing({ open: false })}
  paperlessOk={paperlessOk}
/>
```

- [ ] **Manuell prüfen**

Browser → Regeln → Neue Regel: "Paperless + Verschieben" erscheint nur wenn Paperless in Settings konfiguriert ist.

- [ ] **Commit**

```bash
git add frontend/src/pages/Rules.tsx
git commit -m "feat: hide Paperless action in rule editor when not configured"
```

---

## Task 14: Docker neu bauen und Gesamttest

**Files:** keine

- [ ] **Docker neu bauen**

```bash
docker compose down && docker compose up -d --build
```

Erwartete Ausgabe: `Container mailsort Started`

- [ ] **Smoke-Test Backend**

```bash
curl -s http://localhost:8080/api/settings | python3 -m json.tool | grep -E '"ai_provider"|"ai_base_url"'
```

Erwartete Ausgabe:
```
"ai_provider": "claude",
"ai_base_url": "",
```

- [ ] **Smoke-Test Provider-Test**

```bash
curl -s -X POST http://localhost:8080/api/settings/test-ai \
  -H "Content-Type: application/json" \
  -d '{"ai_provider":"ollama","ai_api_key":"","ai_model":"llama3.2","ai_base_url":"http://localhost:11434/v1"}'
```

Erwartete Ausgabe: `{"ok":false,"message":"..."}` (Verbindungsfehler, kein "not configured")

- [ ] **Abschließender Test-Run**

```bash
docker exec mailsort python -m pytest tests/ -v 2>/dev/null || cd backend && pytest tests/ -v
```

Alle Tests grün.
