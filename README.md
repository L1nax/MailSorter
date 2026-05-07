# MailSort

**Selbst gehosteter, KI-gestützter E-Mail-Sortierer mit Web-UI**

MailSort verbindet sich per IMAP mit deinem Postfach und sortiert eingehende Mails automatisch — regelbasiert für klare Fälle, KI-gestützt für alles andere. Alles läuft lokal auf deiner Hardware, ohne Cloud-Abhängigkeit.

---

## Features

- **Regelengine** — Absender, Domain, Betreff, Anhang-Typ, Body, Empfänger; AND-Verknüpfung, First-Match, Drag-&-Drop-Sortierung
- **KI-Fallback** — Mails ohne passende Regel werden optional per KI klassifiziert (Anthropic Claude, OpenAI, Google Gemini, Ollama)
- **KI-Regelvorschläge** — Das System erkennt wiederkehrende KI-Entscheidungen und schlägt permanente Regeln vor
- **Mehrere Mail-Accounts** — Beliebig viele IMAP-Accounts, jeder mit eigenem Intervall und IDLE-Support
- **Paperless-NGX Integration** — PDF-Anhänge direkt in Paperless hochladen
- **Webhook-Aktionen** — HTTP POST bei eingehenden Mails (ntfy, Slack, Gotify, …)
- **Audit-Log** — Jede verarbeitete Mail wird vollständig geloggt, durchsuchbar und filterbar
- **Backup & Restore** — Vollständige Konfigurationssicherung als JSON, per UI oder CLI (Cron-tauglich)
- **Web-UI** — Dashboard, Regeleditor, Log-Ansicht, Einstellungen
- **Docker Compose** — Ein Befehl zum Starten

---

## Schnellstart

### Voraussetzungen

- Docker & Docker Compose

### Starten

```bash
# Repository klonen
git clone https://github.com/L1nax/MailSorter.git
cd MailSorter

# Starten
docker compose up -d

# Logs verfolgen
docker compose logs -f
```

Die Web-UI ist danach erreichbar unter: **http://localhost:8080**

### Erste Einrichtung

1. **Web-UI öffnen** — http://localhost:8080
2. **Mail-Account anlegen** — Einstellungen → Accounts → Neuer Account
   - IMAP-Host, Port, Benutzername, Passwort eintragen
   - Verbindung testen
3. **Regeln anlegen** — Regeln → Neue Regel
4. **Optional: KI konfigurieren** — Einstellungen → KI-Klassifizierung
5. **Worker starten** — Dashboard → Worker starten

---

## Konfiguration

### Umgebungsvariablen

Alle Laufzeit-Einstellungen werden über die Web-UI in SQLite gespeichert. Es gibt keine `.env`-Datei für Betriebseinstellungen.

Einzige Ausnahme:

| Variable | Beschreibung | Standard |
|----------|-------------|---------|
| `MAILSORT_DATA_DIR` | Pfad zum Datenverzeichnis (DB, Logs) | `/data` |
| `MAILSORT_SECRET_KEY` | Optionaler Schlüssel für die Session-Verschlüsselung | — |

In der `docker-compose.yml` anpassen:

```yaml
environment:
  - MAILSORT_DATA_DIR=/data
  - MAILSORT_SECRET_KEY=dein-geheimer-schlüssel
```

### Daten-Volume

Die SQLite-Datenbank und Logs liegen im gemounteten Volume `./data`. Sichere dieses Verzeichnis regelmäßig.

```
data/
  mailsort.db   ← Regeln, Einstellungen, Audit-Log
```

---

## Mail-Accounts

Mehrere IMAP-Accounts werden vollständig unterstützt. Jeder Account kann unabhängig konfiguriert werden:

| Einstellung | Beschreibung |
|-------------|-------------|
| IMAP-Host / Port | Verbindungsdaten (Standard: 993 TLS) |
| Posteingang-Ordner | Zu überwachender Ordner (Standard: `INBOX`) |
| Papierkorb-Ordner | Ziel für `trash`-Aktionen (Standard: `Trash`) |
| Poll-Intervall | Abfrageintervall in Sekunden |
| IDLE-Modus | Verbindung offen halten für Sofort-Benachrichtigung |

---

## Regelengine

Regeln werden in der UI angelegt und in Prioritätsreihenfolge ausgewertet (First-Match). Jede Regel besteht aus einer oder mehreren AND-verknüpften Bedingungen und einer Aktion.

### Bedingungstypen

| Typ | Beschreibung | Beispiel |
|-----|-------------|---------|
| `from_domain` | Absender-Domain | `amazon.de` |
| `from_address` | Exakte Absender-Adresse | `no-reply@github.com` |
| `subject_contains` | Betreff enthält Text (case-insensitiv) | `Rechnung` |
| `subject_regex` | Betreff matcht Regex | `^(Auftrag|Bestellung)` |
| `has_attachment` | Hat Anhang | — |
| `attachment_type` | Anhang-MIME-Typ | `application/pdf` |
| `body_contains` | Mail-Body enthält Text | `IBAN` |
| `to_address` | Empfänger-Adresse | `info@meinefirma.de` |

### Aktionen

| Aktion | Beschreibung |
|--------|-------------|
| `move` | In IMAP-Ordner verschieben (wird automatisch erstellt) |
| `label` | IMAP-Flag setzen |
| `paperless` | PDF-Anhang an Paperless-NGX hochladen, dann verschieben |
| `webhook` | HTTP POST mit Mail-Metadaten |
| `keep` | Unverändert im Posteingang lassen |
| `trash` | In Papierkorb verschieben |

### Test-Modus

Im Regeleditor gibt es einen eingebauten Test-Modus: Absender, Betreff und Body eingeben und prüfen, welche Regel greifen würde.

---

## KI-Klassifizierung

Wenn keine Regel passt, kann MailSort optional eine KI zur Klassifizierung befragen.

### Unterstützte Provider

| Provider | Modell-Beispiele |
|----------|----------------|
| **Anthropic Claude** | `claude-sonnet-4-6` (Standard) |
| **OpenAI** | `gpt-4o`, `gpt-4o-mini` |
| **Google Gemini** | `gemini-2.0-flash` |
| **Ollama** (lokal) | `llama3.2`, `mistral`, … |

Konfigurieren unter **Einstellungen → KI-Klassifizierung**.

### KI-Regelvorschläge

MailSort beobachtet wiederkehrende KI-Entscheidungen. Sobald dasselbe Signal (z.B. `from_domain: amazon.de → Rechnungen`) N-mal aufgetreten ist (Standard: 3), wird ein Regelvorschlag erstellt.

- **Annehmen** → permanente Regel wird erstellt, kein KI-Aufruf mehr für diesen Fall
- **Snooze** → Vorschlag wird für X Tage ausgeblendet
- **Ablehnen** → Vorschlag wird dauerhaft verworfen

Vorschläge erscheinen als Badge in der Navigation und auf dem Dashboard.

---

## Paperless-NGX Integration

PDF-Anhänge können direkt an Paperless-NGX hochgeladen werden.

1. Paperless-URL und API-Token unter **Einstellungen → Paperless** eintragen
2. Verbindung testen
3. Regel mit Aktion `paperless` anlegen

---

## Backup & Restore

### Über die Web-UI

Unter **Einstellungen → Backup & Restore**:

- **Export:** Sektionen auswählen (Regeln, Accounts, Einstellungen, KI-Daten) und JSON-Datei herunterladen
- **Import:** JSON-Datei hochladen, Modus wählen:
  - **Merge** — Bestehende Einträge bleiben erhalten, nur neue werden hinzugefügt
  - **Überschreiben** — Sektionen werden vollständig ersetzt

### Über die CLI (für Cron-Jobs)

Der Server muss **nicht** laufen. Die CLI greift direkt auf die SQLite-Datenbank zu.

```bash
# Alle Daten exportieren
python -m app.backup export --output /backups/mailsort.json

# Nur Regeln und Einstellungen exportieren
python -m app.backup export --sections rules,settings --output /backups/rules.json

# Backup importieren (merge)
python -m app.backup import /backups/mailsort.json --mode merge

# Backup importieren (alles überschreiben)
python -m app.backup import /backups/mailsort.json --mode replace
```

**Cron-Beispiel** (täglich um 02:00 Uhr):

```bash
0 2 * * * cd /opt/mailsort && python -m app.backup export --output /backups/mailsort-$(date +\%Y\%m\%d).json
```

**Verfügbare Sektionen:** `rules`, `accounts`, `settings`, `suggestions`

> **Hinweis:** Das Backup enthält IMAP-Passwörter im Klartext. Die Backup-Datei sicher aufbewahren.

---

## Audit-Log

Jede verarbeitete Mail erzeugt einen unveränderlichen Log-Eintrag mit:

- Zeitstempel, Absender, Betreff
- Angewendete Regel oder KI-Kennzeichnung
- Ausgeführte Aktion und Zielordner
- Status (`success` / `error`) + Fehlermeldung

Die Log-Ansicht ist filterbar nach Datum, Aktion, Regel und Status. Export als CSV möglich.

Aufbewahrungsdauer: konfigurierbar in den Einstellungen (Standard: 90 Tage).

---

## Lokale Entwicklung

### Voraussetzungen

- Python 3.12+
- Node.js 20+

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Datenbank initialisieren und Server starten
MAILSORT_DATA_DIR=./data uvicorn app.main:app --reload --port 8080
```

### Frontend

```bash
cd frontend
npm install
npm run dev    # Entwicklungsserver auf http://localhost:5173
```

Der Dev-Server leitet API-Anfragen automatisch an `http://localhost:8080` weiter.

### Tests

```bash
cd backend
python -m pytest tests/ -v
```

### Docker-Image lokal bauen

```bash
docker compose build
docker compose up
```

---

## REST API

Alle Endpunkte unter `/api/`. Optionale Authentifizierung per `X-API-Key`-Header (einstellbar unter Einstellungen → Sicherheit).

| Gruppe | Endpunkte |
|--------|----------|
| Regeln | `GET/POST /api/rules`, `PUT/DELETE /api/rules/{id}`, `POST /api/rules/reorder`, `POST /api/rules/test` |
| Accounts | `GET/POST /api/accounts`, `PUT/DELETE /api/accounts/{id}`, `POST /api/accounts/{id}/test-imap` |
| Audit-Log | `GET /api/logs`, `GET /api/logs/export`, `DELETE /api/logs` |
| Einstellungen | `GET/PUT /api/settings`, Test-Endpunkte für IMAP/Paperless/KI |
| Status | `GET /api/status`, `POST /api/worker/start|stop|process-now` |
| Vorschläge | `GET /api/suggestions`, `POST /api/suggestions/{id}/accept|snooze|dismiss` |
| Backup | `GET /api/backup/export`, `POST /api/backup/import` |

---

## Projektstruktur

```
mailsort/
  backend/
    app/
      api/          # FastAPI-Router
      core/         # IMAPWorker, RuleEngine, AIClassifier, ActionExecutor, SuggestionService
      models/       # SQLModel-Datenmodelle
      services/     # Paperless, Webhook
    tests/
  frontend/
    src/
      api/          # TypeScript API-Client
      components/   # UI-Komponenten (shadcn/ui)
      pages/        # Seiten: Dashboard, Regeln, Vorschläge, Log, Einstellungen
  docker-compose.yml
  Dockerfile
  data/             # SQLite-Datenbank (nach erstem Start)
```

---

## Tech-Stack

| Komponente | Technologie |
|------------|------------|
| Backend | Python 3.12, FastAPI, SQLModel |
| IMAP | `imapclient` (mit IDLE-Support) |
| Datenbank | SQLite |
| Frontend | React 18, TypeScript, Tailwind CSS, shadcn/ui |
| KI | Anthropic, OpenAI, Google Gemini, Ollama |
| Deployment | Docker Compose |

---

## Lizenz

MIT License — freie Nutzung, auch kommerziell.
