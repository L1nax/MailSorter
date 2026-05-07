# Design: KI-Provider-Adapter & optionales Paperless

**Datum:** 2026-05-07  
**Status:** Genehmigt

---

## Ziel

- KI-Klassifizierung wird provider-agnostisch: Claude, OpenAI, Gemini und Ollama sind über ein gemeinsames Interface austauschbar.
- Der aktive Provider wird in der Settings-UI per Dropdown gewählt.
- Paperless bleibt als Action-Typ erhalten, wird aber im Rule-Editor nur angezeigt wenn konfiguriert.

---

## Architektur

### Neue Verzeichnisstruktur

```
backend/app/core/providers/
├── __init__.py       ← Factory: get_provider(session) → AIProvider
├── base.py           ← Abstraktes AIProvider-Interface
├── claude.py         ← Anthropic SDK
├── openai.py         ← OpenAI SDK (auch für Ollama via base_url)
└── gemini.py         ← Google Generative AI SDK
```

`ai_classifier.py` wird zur dünnen Wrapper-Schicht: Sie holt den Provider via Factory und ruft `classify()` auf. Die gesamte provider-spezifische Logik lebt in den Provider-Klassen.

### Provider-Interface (`base.py`)

```python
class AIProvider(ABC):
    @abstractmethod
    async def classify(self, mail: MailData, folders: list[str], prompt: str) -> ClassificationResult: ...

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]: ...
```

### Factory (`__init__.py`)

```python
def get_provider(session: Session) -> AIProvider:
    provider = get_setting(session, "ai_provider")
    api_key  = get_setting(session, "ai_api_key")
    model    = get_setting(session, "ai_model")
    base_url = get_setting(session, "ai_base_url")

    match provider:
        case "claude":  return ClaudeProvider(api_key, model)
        case "openai":  return OpenAIProvider(api_key, model, base_url or "https://api.openai.com/v1")
        case "ollama":  return OpenAIProvider("ollama", model, base_url or "http://localhost:11434/v1")
        case "gemini":  return GeminiProvider(api_key, model)
        case _:         return ClaudeProvider(api_key, model)  # Fallback
```

Ollama und OpenAI teilen sich `OpenAIProvider` – der Unterschied ist nur `base_url` und ob ein echter API-Key gesetzt wird.

---

## Settings-Datenmodell

### Neue Felder

| Feld | Typ | Default | Beschreibung |
|------|-----|---------|-------------|
| `ai_provider` | str | `"claude"` | Gewählter Provider: `claude`, `openai`, `gemini`, `ollama` |
| `ai_base_url` | str | `""` | Custom-Endpoint für Ollama oder OpenAI-kompatible APIs |

### Bestehende Felder (unverändert, providerübergreifend)

| Feld | Verwendung |
|------|-----------|
| `ai_api_key` | API-Key (leer bei Ollama) |
| `ai_model` | Modellname |
| `ai_system_prompt` | System-Prompt |
| `ai_enabled` | KI-Fallback aktiviert |

### Default-Modelle (wenn `ai_model` leer)

| Provider | Default-Modell |
|----------|---------------|
| Claude | `claude-sonnet-4-6` |
| OpenAI | `gpt-4o-mini` |
| Gemini | `gemini-2.0-flash` |
| Ollama | `llama3.2` |

`ai_base_url` ist kein Secret und kommt nicht in `MASKED_KEYS`.

Keine DB-Migration nötig – Settings werden als Key-Value in SQLite gespeichert, neue Keys erscheinen automatisch mit Default.

---

## Frontend Settings-UI

### KI-Sektion

```
┌─ KI-Klassifizierung ──────────────────────────┐
│ [x] KI-Fallback aktivieren                     │
│                                                 │
│ Provider: [Claude ▼]                            │
│                                                 │
│ API-Key:  [••••••••]      ← ausgeblendet bei Ollama
│ Modell:   [claude-sonnet-4-6]                   │
│ Base URL: [http://localhost:11434/v1]  ← nur bei Ollama/OpenAI
│                                                 │
│ System-Prompt: [________________________]       │
│                                                 │
│ [Verbindung testen]                             │
└─────────────────────────────────────────────────┘
```

### Sichtbarkeitsregeln

| Feld | Sichtbar bei |
|------|-------------|
| API-Key | Claude, OpenAI, Gemini |
| Base URL | OpenAI, Ollama |
| Modell, System-Prompt | immer (wenn KI aktiviert) |

### Paperless im Rule-Editor

Das Aktions-Dropdown zeigt die Option "Paperless" nur wenn `paperless_url` und `paperless_token` in den geladenen Settings nicht leer sind. Nur Frontend-Bedingung, kein Backend-Umbau.

---

## Backend-Änderungen

### `test-ai` Endpoint

Ruft `get_provider(session).test_connection()` auf – kein weiterer Umbau nötig.

### `SettingsRead` / `SettingsUpdate`

Bekommen je zwei neue Felder: `ai_provider: str` und `ai_base_url: str`.

### Neue Abhängigkeiten (`requirements.txt`)

```
openai>=1.0.0
google-generativeai>=0.8.0
```

---

## Was sich NICHT ändert

- Paperless als Action-Typ bleibt vollständig erhalten
- `ClassificationResult` Datenstruktur bleibt gleich
- Audit-Log, Rule-Engine, IMAP-Worker – keine Änderungen
- Bestehende Claude-Konfigurationen funktionieren weiterhin (Fallback auf Claude wenn `ai_provider` nicht gesetzt)
