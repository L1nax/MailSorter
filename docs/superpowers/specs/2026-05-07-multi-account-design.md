# Multi-Account-Feature – Design-Dokument
**Datum:** 2026-05-07  
**Status:** Genehmigt

---

## Überblick

MailSort soll mehrere IMAP-Accounts gleichzeitig verarbeiten können. Jeder Account läuft in einem eigenen asynchronen Worker-Task. Regeln können global (alle Accounts) oder account-spezifisch sein. Das Audit-Log zeigt, von welchem Account eine Mail stammt.

---

## Datenmodell

### Neue Tabelle `mailaccount`

| Feld | Typ | Default |
|------|-----|---------|
| `id` | UUID, Primary Key | auto |
| `name` | str | – |
| `imap_host` | str | `""` |
| `imap_port` | int | `993` |
| `imap_user` | str | `""` |
| `imap_password` | str | `""` |
| `imap_tls` | bool | `True` |
| `imap_folder` | str | `"INBOX"` |
| `trash_folder` | str | `"Trash"` |
| `poll_interval_seconds` | int | `60` |
| `use_idle` | bool | `False` |
| `enabled` | bool | `True` |
| `created_at` | datetime | auto |

### Änderung `Rule`

- Neues Feld: `account_id: str | None` (FK → `mailaccount.id`, nullable)  
- `NULL` bedeutet: Regel gilt für alle Accounts (global)

### Änderung `AuditLog`

- Neues Feld: `account_id: str | None` (FK → `mailaccount.id`, nullable)  
- Neues Feld: `account_name: str | None` (denormalisiert für Anzeige nach Account-Löschung)

### Migration beim App-Start

Beim ersten Start nach dem Update:
1. Prüfen ob `mailaccount`-Tabelle leer ist
2. Falls `imap_host` in den alten `settings`-Keys gesetzt ist → Account mit Name `"Standard"` anlegen
3. Die alten IMAP-Keys (`imap_host`, `imap_port`, `imap_user`, `imap_password`, `imap_tls`, `imap_folder`, `trash_folder`, `poll_interval_seconds`, `use_idle`) aus `settings` löschen

---

## Backend-Architektur

### `AccountManager` (neu, in `backend/app/core/account_manager.py`)

Ersetzt den globalen `worker = IMAPWorker()` in `main.py`.

```
AccountManager
├── _tasks: dict[str, asyncio.Task]   # account_id → Task
├── start()                            # alle enabled Accounts starten
├── stop()                             # alle Tasks beenden
└── sync_accounts()                    # DB neu lesen, Tasks starten/stoppen/neustarten
```

- Beim Lifespan-Start: `account_manager.start()`
- Nach jeder Account-Änderung (PUT/POST/DELETE): `account_manager.sync_accounts()` aufrufen
- `IMAPWorker.__init__` bekommt `account: MailAccount` statt aus Settings zu lesen

### Neue API-Endpoints `/api/accounts`

| Method | Path | Beschreibung |
|--------|------|-------------|
| `GET` | `/api/accounts` | Liste aller Accounts (Passwort maskiert) |
| `POST` | `/api/accounts` | Account anlegen, Worker starten |
| `PUT` | `/api/accounts/{id}` | Account aktualisieren, Worker neu starten |
| `DELETE` | `/api/accounts/{id}` | Account löschen, Worker stoppen |
| `POST` | `/api/accounts/{id}/test-imap` | Verbindungstest |
| `POST` | `/api/accounts/{id}/process-now` | Sofortige Verarbeitung dieses Accounts |

### Änderungen bestehender Endpoints

- `GET/PUT /api/settings` – IMAP-Felder werden entfernt
- `GET/POST/PUT /api/rules` – `account_id`-Feld wird akzeptiert/zurückgegeben
- `GET /api/logs` – `account_id`-Filter, `account_name` in der Antwort
- `POST /api/status/process-now` – triggert alle Account-Worker

### Passwort-Maskierung

Accounts-API maskiert `imap_password` analog zur bestehenden Settings-API (`***`). Beim Update: Sentinel `***` → gespeichertes Passwort nicht überschreiben.

---

## Frontend

### Navigation

```
Dashboard | Accounts | Regeln | Logs | Einstellungen
```

### Neue Seite „Accounts" (`src/pages/AccountsPage.tsx`)

- Liste aller Accounts als Cards
- Jede Card zeigt: Name, Host, Benutzer, Status (aktiv/inaktiv), Verbindungsstatus
- Aktionen pro Card: Bearbeiten, Verbindung testen, Aktivieren/Deaktivieren, Löschen
- „+ Account hinzufügen"-Button → Formular mit allen IMAP-Feldern (analog zur bisherigen IMAP-Sektion in Einstellungen)
- Speichern triggert sofortigen Worker-Neustart im Backend

### Änderung Regel-Editor (`src/pages/Rules.tsx`)

- Neues optionales Dropdown „Account" in der Regelkonfiguration
- Optionen: alle vorhandenen Accounts + „Alle Accounts (global)"
- Standard bei neuen Regeln: global (kein Account)

### Änderung Audit-Log (`src/pages/Logs.tsx`)

- Neue Spalte „Account" (zeigt `account_name`)
- Spalte nur einblenden wenn mehr als ein Account existiert

### Änderung Einstellungen (`src/pages/SettingsPage.tsx`)

- IMAP-Sektion entfernen (durch Accounts-Seite ersetzt)

---

## Fehlerbehandlung

- Account-Worker schlägt fehl → Fehler wird geloggt, Worker macht Pause (30s) und versucht Reconnect – identisch zur bisherigen Logik
- Account wird gelöscht während Worker läuft → Task wird sauber beendet
- Regel mit `account_id` auf gelöschten Account → Regel wird bei der Verarbeitung übersprungen (kein Match)

---

## Nicht im Scope

- Getrennte Paperless-/KI-Konfiguration pro Account (bleibt global)
- OAuth/XOAUTH2 für IMAP
- Account-spezifische API-Keys für die Web-UI
