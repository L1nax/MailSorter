# Backup/Restore Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine Backup/Restore-Funktion die alle Konfigurationsdaten als JSON exportiert/importiert — ansteuerbar per CLI (für Cron) und REST-API (für die UI).

**Architecture:** Die Kernlogik (`backup.py`) ist shared zwischen CLI und API. Das CLI (`python -m app.backup`) greift direkt auf SQLite zu ohne laufenden Server. Die REST-API wickelt Export/Import per HTTP ab. Die SettingsPage bekommt einen neuen Backup-Abschnitt.

**Tech Stack:** Python argparse (CLI), FastAPI (API), SQLModel (DB-Zugriff), React + TypeScript + shadcn/ui (Frontend)

---

## Dateiübersicht

| Datei | Aktion | Zweck |
|-------|--------|-------|
| `backend/app/core/backup.py` | Neu | Export-/Import-Kernlogik (shared) |
| `backend/app/backup.py` | Neu | CLI-Einstiegspunkt (`python -m app.backup`) |
| `backend/app/api/backup.py` | Neu | FastAPI-Router `/api/backup` |
| `backend/app/main.py` | Ändern | Router einbinden |
| `backend/tests/test_backup.py` | Neu | Tests für Kernlogik |
| `frontend/src/api/client.ts` | Ändern | `backupApi` hinzufügen |
| `frontend/src/pages/SettingsPage.tsx` | Ändern | Backup/Restore-Card |

---

### Task 1: Core Backup-Logik mit Tests (TDD)

**Files:**
- Create: `backend/app/core/backup.py`
- Create: `backend/tests/test_backup.py`

- [ ] **Step 1: Tests schreiben**

Datei `backend/tests/test_backup.py`:

```python
from __future__ import annotations
import pytest
from sqlmodel import Session, create_engine, SQLModel, select
from app.models.rule import Rule, ActionType
from app.models.account import MailAccount
from app.models.settings import Settings
from app.models.suggestion import AISignal, RuleSuggestion, SuggestionStatus
from app.core.backup import export_data, import_data


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    from app import models  # noqa
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def populated(session):
    session.add(Rule(
        name="Test-Regel", priority=1, enabled=True,
        conditions=[{"type": "from_domain", "value": "test.de"}],
        action=ActionType.move, action_params={"folder": "Test"},
    ))
    session.add(MailAccount(
        name="Test-Account", imap_host="imap.test.com",
        imap_user="user@test.com", imap_password="secret",
    ))
    session.add(Settings(key="paperless_url", value="http://paperless"))
    session.add(AISignal(
        signal_type="from_domain", signal_value="test.de",
        action="move", target="Test",
    ))
    session.commit()
    return session


class TestExportData:
    def test_exports_all_sections(self, populated):
        data = export_data(populated, ["rules", "accounts", "settings", "suggestions"])
        assert data["version"] == 1
        assert set(data["sections"]) == {"rules", "accounts", "settings", "suggestions"}
        assert len(data["rules"]) == 1
        assert len(data["accounts"]) == 1
        assert "paperless_url" in data["settings"]
        assert len(data["suggestions"]["ai_signals"]) == 1
        assert "exported_at" in data

    def test_exports_only_requested_sections(self, populated):
        data = export_data(populated, ["rules"])
        assert "rules" in data
        assert "accounts" not in data
        assert "settings" not in data
        assert "suggestions" not in data
        assert data["sections"] == ["rules"]

    def test_rule_fields_present(self, populated):
        data = export_data(populated, ["rules"])
        rule = data["rules"][0]
        assert rule["name"] == "Test-Regel"
        assert rule["action"] == "move"
        assert rule["action_params"] == {"folder": "Test"}
        assert "id" in rule
        assert "created_at" in rule

    def test_account_password_in_plaintext(self, populated):
        data = export_data(populated, ["accounts"])
        assert data["accounts"][0]["imap_password"] == "secret"

    def test_empty_db_exports_empty_lists(self, session):
        data = export_data(session, ["rules", "accounts"])
        assert data["rules"] == []
        assert data["accounts"] == []


class TestImportMerge:
    def test_merge_adds_new_rule(self, session):
        data = {
            "version": 1,
            "sections": ["rules"],
            "rules": [{
                "id": "rule-1", "name": "Neue Regel", "priority": 1,
                "enabled": True, "conditions": [], "action": "move",
                "action_params": {"folder": "X"}, "account_id": None,
                "created_at": "2026-01-01T00:00:00",
            }],
        }
        counts = import_data(session, data, "merge")
        assert counts["rules"] == 1
        assert session.get(Rule, "rule-1") is not None

    def test_merge_skips_existing_rule(self, populated):
        existing = populated.exec(select(Rule)).first()
        data = {
            "version": 1,
            "sections": ["rules"],
            "rules": [{
                "id": existing.id, "name": "Geändert", "priority": 99,
                "enabled": False, "conditions": [], "action": "trash",
                "action_params": {}, "account_id": None,
                "created_at": existing.created_at.isoformat(),
            }],
        }
        counts = import_data(populated, data, "merge")
        assert counts["rules"] == 0
        assert populated.get(Rule, existing.id).name == "Test-Regel"

    def test_merge_settings_skips_existing_key(self, populated):
        data = {
            "version": 1,
            "sections": ["settings"],
            "settings": {"paperless_url": "http://other", "new_key": "new_val"},
        }
        counts = import_data(populated, data, "merge")
        assert counts["settings"] == 1
        assert populated.get(Settings, "paperless_url").value == "http://paperless"
        assert populated.get(Settings, "new_key").value == "new_val"


class TestImportReplace:
    def test_replace_deletes_existing_rules(self, populated):
        data = {
            "version": 1,
            "sections": ["rules"],
            "rules": [{
                "id": "new-id", "name": "Ersatz", "priority": 1,
                "enabled": True, "conditions": [], "action": "keep",
                "action_params": {}, "account_id": None,
                "created_at": "2026-01-01T00:00:00",
            }],
        }
        import_data(populated, data, "replace")
        all_rules = populated.exec(select(Rule)).all()
        assert len(all_rules) == 1
        assert all_rules[0].name == "Ersatz"

    def test_replace_does_not_touch_other_sections(self, populated):
        data = {
            "version": 1,
            "sections": ["rules"],
            "rules": [],
        }
        import_data(populated, data, "replace")
        accounts = populated.exec(select(MailAccount)).all()
        assert len(accounts) == 1

    def test_only_imports_declared_sections(self, session):
        data = {
            "version": 1,
            "sections": ["rules"],
            "rules": [],
            "accounts": [{"id": "acc-1", "name": "Phantom"}],
        }
        counts = import_data(session, data, "replace")
        assert "accounts" not in counts
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

```bash
cd backend && python -m pytest tests/test_backup.py -v 2>&1 | head -30
```

Erwartet: `ImportError` oder `ModuleNotFoundError` (Modul existiert noch nicht)

- [ ] **Step 3: Kernlogik implementieren**

Datei `backend/app/core/backup.py`:

```python
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from sqlmodel import Session, select
from ..models.rule import Rule
from ..models.account import MailAccount
from ..models.settings import Settings
from ..models.suggestion import AISignal, RuleSuggestion

ALL_SECTIONS = ("rules", "accounts", "settings", "suggestions")


def export_data(session: Session, sections: list[str]) -> dict[str, Any]:
    data: dict[str, Any] = {
        "version": 1,
        "exported_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "sections": sections,
    }
    if "rules" in sections:
        data["rules"] = [_rule_to_dict(r) for r in session.exec(select(Rule).order_by(Rule.priority)).all()]
    if "accounts" in sections:
        data["accounts"] = [_account_to_dict(a) for a in session.exec(select(MailAccount).order_by(MailAccount.created_at)).all()]
    if "settings" in sections:
        data["settings"] = {s.key: s.value for s in session.exec(select(Settings)).all()}
    if "suggestions" in sections:
        data["suggestions"] = {
            "ai_signals": [_signal_to_dict(s) for s in session.exec(select(AISignal)).all()],
            "rule_suggestions": [_suggestion_to_dict(s) for s in session.exec(select(RuleSuggestion)).all()],
        }
    return data


def import_data(session: Session, data: dict[str, Any], mode: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    sections = data.get("sections", [])
    if "rules" in sections:
        counts["rules"] = _import_rules(session, data.get("rules", []), mode)
    if "accounts" in sections:
        counts["accounts"] = _import_accounts(session, data.get("accounts", []), mode)
    if "settings" in sections:
        counts["settings"] = _import_settings(session, data.get("settings", {}), mode)
    if "suggestions" in sections:
        sug = data.get("suggestions", {})
        counts["ai_signals"] = _import_ai_signals(session, sug.get("ai_signals", []), mode)
        counts["rule_suggestions"] = _import_rule_suggestions(session, sug.get("rule_suggestions", []), mode)
    session.commit()
    return counts


def _import_rules(session: Session, items: list[dict], mode: str) -> int:
    if mode == "replace":
        for r in session.exec(select(Rule)).all():
            session.delete(r)
        session.flush()
    count = 0
    for d in items:
        if mode == "merge" and session.get(Rule, d["id"]):
            continue
        session.add(Rule(**d))
        count += 1
    return count


def _import_accounts(session: Session, items: list[dict], mode: str) -> int:
    if mode == "replace":
        for a in session.exec(select(MailAccount)).all():
            session.delete(a)
        session.flush()
    count = 0
    for d in items:
        if mode == "merge" and session.get(MailAccount, d["id"]):
            continue
        session.add(MailAccount(**d))
        count += 1
    return count


def _import_settings(session: Session, items: dict[str, str], mode: str) -> int:
    if mode == "replace":
        for s in session.exec(select(Settings)).all():
            session.delete(s)
        session.flush()
    count = 0
    for key, value in items.items():
        if mode == "merge" and session.get(Settings, key):
            continue
        session.add(Settings(key=key, value=str(value)))
        count += 1
    return count


def _import_ai_signals(session: Session, items: list[dict], mode: str) -> int:
    if mode == "replace":
        for s in session.exec(select(AISignal)).all():
            session.delete(s)
        session.flush()
    count = 0
    for d in items:
        if mode == "merge" and session.get(AISignal, d["id"]):
            continue
        session.add(AISignal(**d))
        count += 1
    return count


def _import_rule_suggestions(session: Session, items: list[dict], mode: str) -> int:
    if mode == "replace":
        for s in session.exec(select(RuleSuggestion)).all():
            session.delete(s)
        session.flush()
    count = 0
    for d in items:
        if mode == "merge" and session.get(RuleSuggestion, d["id"]):
            continue
        session.add(RuleSuggestion(**d))
        count += 1
    return count


def _rule_to_dict(r: Rule) -> dict:
    return {
        "id": r.id, "name": r.name, "priority": r.priority,
        "enabled": r.enabled, "conditions": r.conditions,
        "action": r.action, "action_params": r.action_params,
        "account_id": r.account_id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _account_to_dict(a: MailAccount) -> dict:
    return {
        "id": a.id, "name": a.name, "imap_host": a.imap_host,
        "imap_port": a.imap_port, "imap_user": a.imap_user,
        "imap_password": a.imap_password, "imap_tls": a.imap_tls,
        "imap_folder": a.imap_folder, "trash_folder": a.trash_folder,
        "poll_interval_seconds": a.poll_interval_seconds,
        "use_idle": a.use_idle, "enabled": a.enabled,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _signal_to_dict(s: AISignal) -> dict:
    return {
        "id": s.id, "signal_type": s.signal_type, "signal_value": s.signal_value,
        "action": s.action, "target": s.target, "count": s.count,
        "last_seen": s.last_seen.isoformat() if s.last_seen else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "account_id": s.account_id,
    }


def _suggestion_to_dict(s: RuleSuggestion) -> dict:
    return {
        "id": s.id, "signal_type": s.signal_type, "signal_value": s.signal_value,
        "action": s.action, "target": s.target,
        "suggested_conditions": s.suggested_conditions,
        "suggested_rule_name": s.suggested_rule_name,
        "status": s.status,
        "snooze_until": s.snooze_until.isoformat() if s.snooze_until else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "account_id": s.account_id,
    }
```

- [ ] **Step 4: Tests laufen lassen — müssen bestehen**

```bash
cd backend && python -m pytest tests/test_backup.py -v
```

Erwartet: alle Tests grün, kein Fehler

- [ ] **Step 5: Alle Tests laufen lassen**

```bash
cd backend && python -m pytest tests/ -q
```

Erwartet: alle vorhandenen Tests weiterhin bestanden

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/backup.py backend/tests/test_backup.py
git commit -m "feat: add backup/restore core logic with tests"
```

---

### Task 2: CLI-Einstiegspunkt

**Files:**
- Create: `backend/app/backup.py`

- [ ] **Step 1: CLI-Modul erstellen**

Datei `backend/app/backup.py`:

```python
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime
from sqlmodel import Session
from .db import engine, init_db
from .core.backup import export_data, import_data, ALL_SECTIONS


def cmd_export(args: argparse.Namespace) -> None:
    sections = [s.strip() for s in args.sections.split(",")] if args.sections else list(ALL_SECTIONS)
    unknown = set(sections) - set(ALL_SECTIONS)
    if unknown:
        print(f"Fehler: Unbekannte Sektionen: {', '.join(unknown)}", file=sys.stderr)
        sys.exit(1)
    init_db()
    with Session(engine) as session:
        data = export_data(session, sections)
    output = args.output or f"mailsort-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    parts: list[str] = []
    for s in sections:
        if s == "suggestions":
            sug = data.get("suggestions", {})
            parts.append(f"Signale: {len(sug.get('ai_signals', []))}, Vorschläge: {len(sug.get('rule_suggestions', []))}")
        elif s == "settings":
            parts.append(f"Einstellungen: {len(data.get('settings', {}))}")
        else:
            parts.append(f"{s.capitalize()}: {len(data.get(s, []))}")
    print(f"Export: {', '.join(parts)} → {output}")


def cmd_import(args: argparse.Namespace) -> None:
    try:
        with open(args.file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Fehler beim Lesen der Datei: {e}", file=sys.stderr)
        sys.exit(1)
    if data.get("version") != 1:
        print(f"Fehler: Unbekannte Backup-Version {data.get('version')!r}", file=sys.stderr)
        sys.exit(1)
    init_db()
    with Session(engine) as session:
        counts = import_data(session, data, args.mode)
    parts = [f"{k}: {v}" for k, v in counts.items() if v > 0]
    print(f"Import ({args.mode}): {', '.join(parts) or 'Keine neuen Einträge'}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m app.backup",
        description="MailSort Backup/Restore",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    exp = sub.add_parser("export", help="Backup exportieren")
    exp.add_argument(
        "--sections", "-s",
        help="Kommasepariert: rules,accounts,settings,suggestions (Standard: alle)",
    )
    exp.add_argument(
        "--output", "-o",
        help="Ausgabedatei (Standard: mailsort-backup-YYYYMMDD-HHMMSS.json)",
    )

    imp = sub.add_parser("import", help="Backup importieren")
    imp.add_argument("file", help="Pfad zur Backup-JSON-Datei")
    imp.add_argument(
        "--mode", "-m",
        choices=["merge", "replace"],
        default="merge",
        help="merge: bestehende Einträge behalten | replace: Sektionen überschreiben (Standard: merge)",
    )

    args = parser.parse_args()
    if args.command == "export":
        cmd_export(args)
    else:
        cmd_import(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Manuell testen**

```bash
cd backend
# Export
MAILSORT_DATA_DIR=/tmp/mailsort-test python -m app.backup export --output /tmp/test-backup.json
# Erwartet: "Export: Rules: 0, Accounts: 0, Einstellungen: 0, Signale: 0, Vorschläge: 0 → /tmp/test-backup.json"

# Backup-Datei prüfen
python -c "import json; d=json.load(open('/tmp/test-backup.json')); print(list(d.keys()))"
# Erwartet: ['version', 'exported_at', 'sections', 'rules', 'accounts', 'settings', 'suggestions']

# Hilfe prüfen
python -m app.backup --help
python -m app.backup export --help
python -m app.backup import --help
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/backup.py
git commit -m "feat: add CLI entry point for backup/restore"
```

---

### Task 3: REST-API

**Files:**
- Create: `backend/app/api/backup.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: API-Router erstellen**

Datei `backend/app/api/backup.py`:

```python
from __future__ import annotations
import json
from datetime import datetime
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlmodel import Session
from ..db import get_session
from ..core.backup import export_data, import_data, ALL_SECTIONS

router = APIRouter(prefix="/api/backup", tags=["backup"])


class ImportRequest(BaseModel):
    mode: str = "merge"
    data: dict[str, Any]


@router.get("/export")
def backup_export(
    sections: str | None = Query(None, description="Kommasepariert: rules,accounts,settings,suggestions"),
    session: Session = Depends(get_session),
) -> Response:
    secs = [s.strip() for s in sections.split(",")] if sections else list(ALL_SECTIONS)
    unknown = set(secs) - set(ALL_SECTIONS)
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unbekannte Sektionen: {', '.join(unknown)}")
    data = export_data(session, secs)
    filename = f"mailsort-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    content = json.dumps(data, indent=2, default=str)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import")
def backup_import(
    body: ImportRequest,
    session: Session = Depends(get_session),
) -> dict[str, int]:
    if body.data.get("version") != 1:
        raise HTTPException(
            status_code=400,
            detail=f"Unbekannte Backup-Version: {body.data.get('version')!r}",
        )
    if body.mode not in ("merge", "replace"):
        raise HTTPException(status_code=400, detail="mode muss 'merge' oder 'replace' sein")
    return import_data(session, body.data, body.mode)
```

- [ ] **Step 2: Router in main.py einbinden**

Datei `backend/app/main.py` — die Import-Zeile und `include_router`-Zeile ergänzen:

```python
# Bestehende Imports (Zeile 11-14):
from .api import rules, logs, settings
from .api.accounts import router as accounts_router, set_account_manager
from .api.status import router as status_router, set_account_manager as set_status_manager
from .api.suggestions import router as suggestions_router
from .api.backup import router as backup_router  # NEU
```

Und im Block nach `app.include_router(suggestions_router)`:

```python
app.include_router(backup_router)  # NEU
```

- [ ] **Step 3: API manuell testen**

```bash
cd backend && uvicorn app.main:app --reload &
sleep 2

# Export testen
curl -s "http://localhost:8000/api/backup/export?sections=rules" | python -m json.tool | head -10

# Nur Regeln exportieren
curl -s "http://localhost:8000/api/backup/export?sections=rules,settings" -o /tmp/api-backup.json
python -c "import json; d=json.load(open('/tmp/api-backup.json')); print(d['sections'])"
# Erwartet: ['rules', 'settings']

# Import testen (merge)
curl -s -X POST "http://localhost:8000/api/backup/import" \
  -H "Content-Type: application/json" \
  -d '{"mode": "merge", "data": {"version": 1, "sections": ["rules"], "rules": []}}'
# Erwartet: {"rules": 0}

# Ungültige Version testen
curl -s -X POST "http://localhost:8000/api/backup/import" \
  -H "Content-Type: application/json" \
  -d '{"mode": "merge", "data": {"version": 99, "sections": []}}' | python -m json.tool
# Erwartet: 400 mit detail über unbekannte Version

kill %1
```

- [ ] **Step 4: Alle Tests laufen lassen**

```bash
cd backend && python -m pytest tests/ -q
```

Erwartet: alle Tests grün

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/backup.py backend/app/main.py
git commit -m "feat: add /api/backup REST router"
```

---

### Task 4: Frontend — API-Client und SettingsPage

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/SettingsPage.tsx`

- [ ] **Step 1: `backupApi` in client.ts ergänzen**

In `frontend/src/api/client.ts` am Ende der Datei (nach `suggestionsApi`) anfügen:

```typescript
// Backup
export const backupApi = {
  export: async (sections?: string[]): Promise<void> => {
    const qs = sections && sections.length > 0 ? `?sections=${sections.join(',')}` : ''
    const apiKey = localStorage.getItem('mailsort_api_key') ?? ''
    const res = await fetch(`/api/backup/export${qs}`, {
      headers: apiKey ? { 'X-API-Key': apiKey } : {},
    })
    if (!res.ok) {
      const text = await res.text()
      throw new Error(`${res.status}: ${text}`)
    }
    const blob = await res.blob()
    const disposition = res.headers.get('Content-Disposition') ?? ''
    const match = disposition.match(/filename="([^"]+)"/)
    const filename = match?.[1] ?? `mailsort-backup-${new Date().toISOString().slice(0, 10)}.json`
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  },
  import: (data: object, mode: 'merge' | 'replace') =>
    request<Record<string, number>>('/backup/import', {
      method: 'POST',
      body: JSON.stringify({ mode, data }),
    }),
}
```

- [ ] **Step 2: Backup/Restore-Card in SettingsPage.tsx**

In `frontend/src/pages/SettingsPage.tsx`:

**Imports ergänzen** — `backupApi` zum bestehenden Import hinzufügen:

```typescript
import { settingsApi, backupApi, type Settings } from '@/api/client'
```

Außerdem `useRef` zum bestehenden React-Import ergänzen (falls nicht vorhanden — es ist bereits vorhanden).

**State-Variablen** am Anfang von `SettingsPage()` nach den bestehenden States einfügen:

```typescript
const [backupSections, setBackupSections] = useState<string[]>(['rules', 'accounts', 'settings', 'suggestions'])
const [exporting, setExporting] = useState(false)
const [importing, setImporting] = useState(false)
const [importResult, setImportResult] = useState<Record<string, number> | null>(null)
const [importError, setImportError] = useState<string | null>(null)
const [importMode, setImportMode] = useState<'merge' | 'replace'>('merge')
const fileInputRef = useRef<HTMLInputElement>(null)
```

**Handler-Funktionen** vor dem `return`-Statement einfügen:

```typescript
const handleExport = async () => {
  setExporting(true)
  try {
    await backupApi.export(backupSections)
  } catch (e) {
    console.error('Export fehlgeschlagen:', e)
  } finally {
    setExporting(false)
  }
}

const handleImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
  const file = e.target.files?.[0]
  if (!file) return
  setImporting(true)
  setImportResult(null)
  setImportError(null)
  try {
    const text = await file.text()
    const data = JSON.parse(text)
    const counts = await backupApi.import(data, importMode)
    setImportResult(counts)
  } catch (err) {
    setImportError(String(err))
  } finally {
    setImporting(false)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }
}

const toggleSection = (s: string) =>
  setBackupSections(prev =>
    prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]
  )
```

**Neue Card** am Ende des `<div className="space-y-6">` in SettingsPage, direkt vor dem letzten schließenden `</div>`, nach der KI-Regelvorschläge-Card einfügen:

```tsx
<Card>
  <CardHeader><CardTitle>Backup & Restore</CardTitle></CardHeader>
  <CardContent className="space-y-5">
    {/* Export */}
    <div className="space-y-2">
      <p className="text-sm font-medium">Export</p>
      <div className="flex flex-wrap gap-3">
        {[
          { key: 'rules', label: 'Regeln' },
          { key: 'accounts', label: 'Mail-Accounts' },
          { key: 'settings', label: 'Einstellungen' },
          { key: 'suggestions', label: 'KI-Vorschläge & Signale' },
        ].map(({ key, label }) => (
          <label key={key} className="flex items-center gap-1.5 text-sm cursor-pointer select-none">
            <input
              type="checkbox"
              checked={backupSections.includes(key)}
              onChange={() => toggleSection(key)}
              className="rounded"
            />
            {label}
          </label>
        ))}
      </div>
      <Button
        variant="outline"
        size="sm"
        onClick={handleExport}
        disabled={exporting || backupSections.length === 0}
      >
        {exporting ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : null}
        Backup herunterladen
      </Button>
    </div>

    <div className="h-px bg-border" />

    {/* Import */}
    <div className="space-y-2">
      <p className="text-sm font-medium">Import</p>
      <div className="flex gap-4">
        {(['merge', 'replace'] as const).map(m => (
          <label key={m} className="flex items-center gap-1.5 text-sm cursor-pointer select-none">
            <input
              type="radio"
              name="importMode"
              value={m}
              checked={importMode === m}
              onChange={() => setImportMode(m)}
            />
            {m === 'merge' ? 'Merge (bestehende behalten)' : 'Überschreiben'}
          </label>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => fileInputRef.current?.click()}
          disabled={importing}
        >
          {importing ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : null}
          Backup-Datei auswählen…
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".json"
          className="hidden"
          onChange={handleImportFile}
        />
      </div>
      {importResult && (
        <p className="text-sm text-green-600 flex items-center gap-1">
          <CheckCircle className="h-4 w-4" />
          Importiert: {Object.entries(importResult).filter(([, v]) => v > 0).map(([k, v]) => `${k}: ${v}`).join(', ') || 'Keine neuen Einträge'}
        </p>
      )}
      {importError && (
        <p className="text-sm text-red-600 flex items-center gap-1">
          <AlertCircle className="h-4 w-4" />
          {importError}
        </p>
      )}
    </div>
  </CardContent>
</Card>
```

- [ ] **Step 3: TypeScript-Build prüfen**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Erwartet: `✓ built in` ohne Fehler

- [ ] **Step 4: Alle Backend-Tests laufen lassen**

```bash
cd backend && python -m pytest tests/ -q
```

Erwartet: alle Tests grün

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/pages/SettingsPage.tsx
git commit -m "feat: add backup/restore UI and API client"
```
