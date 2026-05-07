# CLAUDE.md – Hinweise für Claude Code

## Sprache

Antworte **immer auf Deutsch**, unabhängig von der Sprache der Nutzereingabe.

## Projektkonzept

Das vollständige Projektkonzept (Spezifikation v1.0) befindet sich in:

```
SPEC.md
```

Es beschreibt Architektur, Features, Datenmodell, REST-API, Deployment und kritische Implementierungsdetails für MailSort.

## Wichtige Hinweise

- Empfohlene Implementierungsreihenfolge und kritische Details stehen in `SPEC.md` Abschnitt 7.
- IMAP UIDs verwenden (keine Sequenznummern).
- Transaktionsreihenfolge: Audit-Log schreiben → Aktion ausführen → Log-Status updaten.
- Alle Laufzeit-Einstellungen liegen in SQLite, keine `.env` für Runtime-Config.
- Einzige Umgebungsvariable: `MAILSORT_SECRET_KEY`.
- Python 3.14: `datetime.utcnow()` ist deprecated → stattdessen `datetime.now(timezone.utc).replace(tzinfo=None)` (`.replace(tzinfo=None)` für SQLite-Kompatibilität mit naiven Datetimes).

---

## Umgesetzte Features (über SPEC.md hinaus)

### Mehrere Mail-Accounts (Branch: `multiple-mail-accounts`, gemergt)

- `MailAccount`-Tabelle ersetzt die einzelne IMAP-Konfiguration in Settings
- Jeder Account hat eigene IMAP-Einstellungen, Poll-Intervall, IDLE-Modus
- `IMAPWorker` iteriert über alle aktiven Accounts
- REST-API: `/api/accounts` (CRUD + test-imap, process-now, reset-flags)
- Frontend: `/accounts` Seite zur Verwaltung

### KI-Regelvorschläge (Branch: `KI-Rules`, PR offen)

**Ziel:** KI-Klassifizierungen führen nach N Wiederholungen zu automatischen Regelvorschlägen, die der Nutzer annehmen kann → danach kein KI-Aufruf mehr für diesen Fall.

**Neue DB-Tabellen:**
- `ai_signal` — zählt beobachtete Signale pro `(signal_type, signal_value, action, target, account_id)`. UniqueConstraint auf dieser Kombination.
- `rule_suggestion` — Vorschläge mit Status `pending | accepted | snoozed | dismissed`. UniqueConstraint auf `(signal_type, signal_value, action, target, account_id)`.

**Neue Settings-Felder:** `suggestion_threshold` (Standard: 3), `suggestion_snooze_days` (Standard: 30)

**Backend-Dateien:**
- `backend/app/models/suggestion.py` — `AISignal`, `RuleSuggestion`, `SuggestionStatus`, `RuleSuggestionRead`
- `backend/app/core/suggestion_service.py` — `process_signals()`, Upsert-Logik, Schwellwert-Prüfung, Doppelprüfung gegen vorhandene Regeln und Snooze-Zustände
- `backend/app/api/suggestions.py` — REST-Router `/api/suggestions` (list, count, accept, snooze, dismiss)
- `backend/app/core/providers/base.py` — `ClassificationResult` um `signals`-Feld erweitert; `_parse_response()` parst optionale `signals:`-Zeile; `ALLOWED_SIGNAL_TYPES` frozenset; `_parse_signals()` Hilfsfunktion
- `backend/app/core/imap_worker.py` — ergänzt KI-Prompt um Signal-Anweisung; ruft nach KI-Klassifizierung `process_signals()` auf

**Signal-Format in KI-Antwort:**
```
move:Rechnungen
signals: from_domain:amazon.de, subject_contains:Rechnung
```
Erlaubte Signal-Typen: `from_domain`, `from_address`, `subject_contains`, `has_attachment`, `attachment_type`, `to_address`

**Accept-Logik:** Erstellt eine vollständige `Rule` mit `priority = max_existing + 1`, setzt `rule_suggestion.status = accepted`. `action_params["folder"]` wird nur bei `move` und `paperless` gesetzt.

**Frontend-Dateien:**
- `frontend/src/pages/SuggestionsPage.tsx` — Tabs "Offen" / "Verlauf", Accept-Modal, Snooze-Dropdown, Einstellungen für Schwellwert und Snooze-Tage
- `frontend/src/components/layout/Layout.tsx` — Nav-Badge mit Anzahl offener Vorschläge (polling alle 60s)
- `frontend/src/pages/Dashboard.tsx` — Banner-Button wenn offene Vorschläge vorhanden
- `frontend/src/pages/SettingsPage.tsx` — Abschnitt "KI-Regelvorschläge" mit den zwei neuen Feldern
- `frontend/src/api/client.ts` — `suggestionsApi`, `RuleSuggestion`, `SuggestionStatus`, Settings-Felder ergänzt

**Tests:** `backend/tests/test_signals.py` (6 Tests), `backend/tests/test_suggestion_service.py` (8 Tests)
