# Design: Backup/Restore

**Datum:** 2026-05-07  
**Branch:** main  
**Status:** Genehmigt

---

## Ziel

Eine Backup/Restore-Funktion für MailSort, die sowohl über die UI als auch per CLI (für Cron-Jobs) ansteuerbar ist. Der Nutzer wählt beim Export, welche Datenbereiche gesichert werden sollen, und beim Import, ob bestehende Daten erhalten oder überschrieben werden.

---

## Datenformat

Eine einzige JSON-Datei (`mailsort-backup-YYYYMMDD-HHMMSS.json`) mit folgendem Schema:

```json
{
  "version": 1,
  "exported_at": "2026-05-07T14:30:00",
  "sections": ["rules", "accounts", "settings", "suggestions"],
  "rules": [...],
  "accounts": [...],
  "settings": {...},
  "suggestions": {
    "ai_signals": [...],
    "rule_suggestions": [...]
  }
}
```

- `version` — für zukünftige Formatänderungen
- `sections` — listet welche Sektionen tatsächlich enthalten sind; beim Import wird nur importiert, was in `sections` steht
- IMAP-Passwörter der Accounts werden im Klartext gespeichert — der Nutzer ist für die sichere Aufbewahrung verantwortlich
- Audit-Logs sind nicht im Scope (zu groß, keine sinnvolle Nutzung beim Restore)

### Sektionen

| Sektion | Inhalt |
|---------|--------|
| `rules` | Alle Regeln inkl. Bedingungen, Aktion, Priorität |
| `accounts` | Alle Mail-Accounts inkl. IMAP-Passwörtern |
| `settings` | Alle Settings-Einträge (Key/Value) |
| `suggestions` | `ai_signal`- und `rule_suggestion`-Einträge |

---

## CLI-Interface

Aufruf als Python-Modul direkt gegen die SQLite-DB — der Server muss **nicht** laufen.

```bash
# Export (alle Sektionen)
python -m app.backup export

# Export (bestimmte Sektionen, benutzerdefinierter Pfad)
python -m app.backup export --sections rules,settings --output /backups/rules.json

# Import (merge — bestehende bleiben, neue werden per ID dedupliziert hinzugefügt)
python -m app.backup import backup.json --mode merge

# Import (replace — alle Daten der enthaltenen Sektionen löschen, dann einspielen)
python -m app.backup import backup.json --mode replace
```

- Standard-Ausgabepfad: `./mailsort-backup-YYYYMMDD-HHMMSS.json`
- `--sections` akzeptiert kommaseparierte Liste: `rules`, `accounts`, `settings`, `suggestions`
- Fehlerhafte Dateien (falsches Format, unbekannte Version) führen zu Abbruch mit Fehlermeldung
- Erfolgreiche Operationen geben eine einzeilige Bestätigung aus (z.B. `Export: 12 Regeln, 2 Accounts, ... → mailsort-backup-20260507-143000.json`)

**Cron-Beispiel:**
```bash
0 2 * * * cd /opt/mailsort && python -m app.backup export --output /backups/mailsort-$(date +\%Y\%m\%d).json
```

---

## REST-API

Zwei neue Endpunkte unter `/api/backup`:

| Method | Endpoint | Beschreibung |
|--------|----------|-------------|
| `GET` | `/api/backup/export` | Liefert JSON-Datei als Download (`Content-Disposition: attachment`) |
| `POST` | `/api/backup/import` | Importiert Backup |

### GET `/api/backup/export`

Query-Parameter: `sections=rules,accounts,settings,suggestions` (optional, Standard: alle)

Response: `application/json` mit `Content-Disposition: attachment; filename="mailsort-backup-YYYYMMDD-HHMMSS.json"`

### POST `/api/backup/import`

```json
{
  "mode": "merge" | "replace",
  "data": { ...backup-objekt... }
}
```

Response: `200 OK` mit Zusammenfassung der importierten Einträge:
```json
{
  "rules": 12,
  "accounts": 2,
  "settings": 8,
  "ai_signals": 45,
  "rule_suggestions": 3
}
```

---

## Import-Logik

### Merge-Modus

Pro Sektion: Für jeden Eintrag aus dem Backup wird anhand der `id` geprüft:
- ID existiert bereits → überspringen (bestehender Eintrag bleibt)
- ID existiert nicht → einfügen

### Replace-Modus

Pro Sektion, die in `sections` des Backups enthalten ist:
1. Alle vorhandenen Einträge dieser Sektion löschen
2. Alle Einträge aus dem Backup einfügen

Sektionen, die **nicht** im Backup enthalten sind, werden nicht angefasst.

---

## UI

Neuer Abschnitt **"Backup & Restore"** auf der Einstellungsseite (`/settings`).

### Export-Bereich

- Checkboxen für jede Sektion (alle standardmäßig angehakt):
  - ☑ Regeln
  - ☑ Mail-Accounts
  - ☑ Einstellungen
  - ☑ KI-Regelvorschläge & Signale
- Button **"Backup herunterladen"** → löst `GET /api/backup/export?sections=...` aus

### Import-Bereich

- Datei-Upload (`.json`)
- Radio-Buttons: **Merge** (Standard) / **Überschreiben**
- Button **"Importieren"**
- Nach erfolgreichem Import: Erfolgs-Toast mit Zusammenfassung (z.B. "12 Regeln, 2 Accounts importiert")
- Bei Fehler: Fehlermeldung inline

---

## Neue Dateien

| Datei | Zweck |
|-------|-------|
| `backend/app/core/backup.py` | Export- und Import-Logik (shared zwischen CLI und API) |
| `backend/app/backup.py` | CLI-Einstiegspunkt (`python -m app.backup`) |
| `backend/app/api/backup.py` | FastAPI-Router `/api/backup` |
| `backend/tests/test_backup.py` | Tests für Export/Import-Logik |

---

## Nicht im Scope

- Automatische geplante Backups aus der UI heraus
- Verschlüsselung der Backup-Datei
- Audit-Log im Backup
- Cloud-Upload (S3, etc.)
- Versions-Migration zwischen verschiedenen Backup-Formaten
