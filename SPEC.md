# MailSort – Project Specification v1.0
> Self-hosted AI Mail Sorter | Open Source | Mai 2026
---
## 1. Projektübersicht
MailSort ist ein selbst gehosteter E-Mail-Sortierer mit Web-UI. Er verbindet sich per IMAP mit einem beliebigen Postfach und sortiert eingehende Mails automatisch in Ordner.
Die Sortierung erfolgt zweistufig: zuerst greifen konfigurierbare Regelsets (Absender, Domain, Betreff, Anhangtyp). Nur was keine Regel trifft, wird optional per KI (Anthropic Claude) klassifiziert. Zusätzlich kann MailSort PDF-Anhänge direkt an Paperless-NGX weiterleiten.
### Problemstellung
Bestehende Lösungen haben kritische Schwächen:
- n8n IMAP-Node markiert Mails als gelesen trotz gegenteiliger Einstellung
- n8n hat keine Transaktionssicherheit: Workflow-Abbruch nach Verschieben führt zu Datenverlust
- Anthropic Rate Limiting (429) bricht Bulk-Verarbeitung ab
- IMAP Get Many lädt keine Anhänge als Binary – Paperless-Upload im Bulk nicht möglich
- Kein Audit-Log: unklar wo eine Mail gelandet ist
- Sieve-Filter sind rein regelbasiert und benötigen Serversupport
### Ziele
- Zuverlässige, verlustfreie Mailsortierung mit vollständigem Audit-Trail
- Regelbasiert für klare Fälle, KI-Fallback für unklare Fälle
- Web-UI für Konfiguration, Monitoring und Debugging
- Einfaches Self-Hosting via Docker Compose
- Open Source (GitHub), community-freundliche Architektur
---
## 2. Feature-Übersicht
### 2.1 Regelengine
Regeln werden in der UI konfiguriert und in SQLite gespeichert. Jede Regel besteht aus Bedingungen und einer Aktion.
#### Bedingungstypen
| Typ | Beschreibung |
|-----|-------------|
| `from_domain` | Absender-Domain (z.B. `amazon.de`, `ntfy.sh`) |
| `from_address` | Exakte E-Mail-Adresse |
| `subject_contains` | Betreff enthält Zeichenkette (case-insensitive) |
| `subject_regex` | Betreff matcht regulären Ausdruck |
| `has_attachment` | Hat Anhang (beliebig) |
| `attachment_type` | Anhang hat bestimmten MIME-Typ (z.B. `application/pdf`) |
| `body_contains` | Mail-Body enthält Zeichenkette |
| `to_address` | Empfänger-Adresse |
#### Logik
- Mehrere Bedingungen in einer Regel sind AND-verknüpft
- Regelreihenfolge ist konfigurierbar (drag & drop in UI)
- Erste passende Regel gewinnt (First-Match)
- Regeln können aktiviert/deaktiviert werden
#### Aktionstypen
| Aktion | Beschreibung |
|--------|-------------|
| `move` | In IMAP-Ordner verschieben (wird erstellt falls nicht vorhanden) |
| `label` | IMAP-Flag/Label setzen (GMail-kompatibel) |
| `paperless` | PDF-Anhang an Paperless-NGX API hochladen, dann move |
| `webhook` | HTTP POST an beliebige URL mit Mail-Metadaten |
| `keep` | Mail unverändert im Posteingang lassen |
| `trash` | In Papierkorb verschieben (konfigurierbarer Ordnername) |
---
### 2.2 KI-Klassifizierung (optionaler Fallback)
Wenn keine Regel greift, kann MailSort die Mail optional an Claude (Anthropic API) zur Klassifizierung schicken.
- Konfigurierbar: an/aus, API-Key, Modell (Standard: `claude-sonnet-4-20250514`)
- Vollständiger Mail-Body wird übertragen (kein bodyPreview-Limit)
- System-Prompt frei konfigurierbar in der UI
- Exponential Backoff bei Rate Limiting (429) – kein Abbruch
- KI-Aktion wird wie eine Regelaktion behandelt und geloggt
- KI-Klassifizierung kann deaktiviert werden (Mail bleibt dann im Posteingang)
---
### 2.3 Paperless-NGX Integration
- Verbindung per API-Token konfigurierbar
- PDF-Anhänge werden direkt per `multipart/form-data` hochgeladen
- Optional: Titel, Tags, Korrespondent aus Mail-Metadaten vorbelegen
- Nach erfolgreichem Upload: Mail in konfigurierten Ordner verschieben
- Fehler beim Upload: Mail bleibt im Posteingang, Eintrag im Audit-Log
---
### 2.4 Audit-Log
Jede verarbeitete Mail erzeugt einen unveränderlichen Log-Eintrag:
- Zeitstempel, Message-ID, Absender, Betreff
- Angewendete Regel (oder `KI` oder `kein Match`)
- Ausgeführte Aktion und Zielordner
- Status: `success` / `error` + Fehlermeldung
- Durchsuchbar und filterbar in der UI
- Aufbewahrung konfigurierbar (Standard: 90 Tage)
---
### 2.5 Web-UI
#### Dashboard
- Statistiken: verarbeitete Mails heute/Woche, Regelverteilung, KI-Anteil
- Letzten N Audit-Log-Einträge
- Verbindungsstatus IMAP + Paperless
#### Regeleditor
- Regeln anlegen, bearbeiten, löschen
- Drag & drop Sortierung (Priorität)
- Aktivieren/Deaktivieren per Toggle
- Test-Modus: Mail-Header eingeben und prüfen welche Regel greift
#### Einstellungen
- IMAP-Verbindung: Host, Port, User, Passwort, TLS
- Polling-Intervall oder IMAP IDLE
- Paperless-NGX: URL + API-Token
- Anthropic: API-Key, Modell, System-Prompt
- Trash-Ordner-Name (Standard: `Trash`)
- Audit-Log-Aufbewahrung
#### Audit-Log Ansicht
- Tabellarische Ansicht mit Suche und Filter
- Filter nach Datum, Aktion, Regel, Status
- Export als CSV
---
## 3. Architektur
### 3.1 Tech-Stack
| Komponente | Technologie |
|------------|------------|
| Backend | Python 3.12, FastAPI |
| IMAP | `imaplib` (stdlib) + `imapclient` für IDLE-Support |
| Datenbank | SQLite via SQLModel (Rules, Audit-Log, Settings) |
| Frontend | React 18, TypeScript, Tailwind CSS, shadcn/ui |
| KI | Anthropic Python SDK (`anthropic>=0.25`) |
| Deployment | Docker Compose |
| Config | Alle Einstellungen in SQLite (kein `.env` für Laufzeit-Config) |
---
### 3.2 Komponenten
#### IMAPWorker
Läuft als Background-Task. Zwei Modi:
- **Polling:** prüft alle N Sekunden auf neue Mails im Posteingang
- **IDLE:** hält IMAP-Verbindung offen, reagiert sofort auf neue Mails
- Liest kompletten Mail-Body + Anhänge (kein Preview-Limit)
- Transaktionssicherheit: Aktion erst nach erfolgreichem Log-Eintrag
#### RuleEngine
Synchrone Verarbeitung pro Mail:
- Lädt aktive Regeln in Prioritätsreihenfolge
- Prüft Bedingungen (First-Match)
- Gibt Aktion zurück oder `None` (→ KI-Fallback)
#### AIClassifier
- Wird nur aufgerufen wenn RuleEngine kein Match liefert und KI aktiviert ist
- Exponential Backoff: 1s, 2s, 4s bei 429
- Max 3 Retries, dann `keep` (Mail bleibt im Posteingang, Log-Eintrag mit Warnung)
- Antwort wird auf bekannte Aktionen validiert
#### ActionExecutor
- Führt Aktion aus (IMAP-Befehle, Paperless-Upload, Webhook)
- Bei Fehler: rollback soweit möglich, Fehlereintrag im Audit-Log
- Erstellt IMAP-Ordner automatisch wenn nicht vorhanden
---
### 3.3 Datenmodell
#### Rule
| Feld | Beschreibung |
|------|-------------|
| `id` | UUID, primärer Schlüssel |
| `name` | Anzeigename in der UI |
| `priority` | Integer, aufsteigend (niedrig = höhere Priorität) |
| `enabled` | Boolean |
| `conditions` | JSON-Array von Bedingungsobjekten |
| `action` | Enum: `move` \| `label` \| `paperless` \| `webhook` \| `keep` \| `trash` |
| `action_params` | JSON: Zielordner, URL, etc. |
| `created_at` | Timestamp |
#### AuditLog
| Feld | Beschreibung |
|------|-------------|
| `id` | UUID |
| `timestamp` | Timestamp (UTC) |
| `message_id` | IMAP Message-ID Header |
| `from_address` | Absender |
| `subject` | Betreff |
| `rule_id` | FK zu Rule oder NULL (KI oder kein Match) |
| `rule_name` | Denormalisiert für historische Korrektheit |
| `action` | Ausgeführte Aktion |
| `target` | Zielordner / URL |
| `status` | `success` \| `error` |
| `error_msg` | Fehlermeldung bei `error` |
---
## 4. REST API
Alle Endpunkte liefern JSON. Authentifizierung: optionaler API-Key (Header `X-API-Key`).
### 4.1 Regeln
| Method | Endpoint | Beschreibung |
|--------|----------|-------------|
| `GET` | `/api/rules` | Alle Regeln in Prioritätsreihenfolge |
| `POST` | `/api/rules` | Neue Regel erstellen |
| `PUT` | `/api/rules/{id}` | Regel aktualisieren |
| `DELETE` | `/api/rules/{id}` | Regel löschen |
| `POST` | `/api/rules/reorder` | Prioritäten neu setzen (Array von IDs) |
| `POST` | `/api/rules/test` | Regel gegen Mail-Header testen |
### 4.2 Audit-Log
| Method | Endpoint | Beschreibung |
|--------|----------|-------------|
| `GET` | `/api/logs` | Log-Einträge (paginiert, filterbar) |
| `GET` | `/api/logs/export` | CSV-Export |
| `DELETE` | `/api/logs` | Logs älter als N Tage löschen |
### 4.3 Einstellungen
| Method | Endpoint | Beschreibung |
|--------|----------|-------------|
| `GET` | `/api/settings` | Aktuelle Einstellungen (Passwort/Key maskiert) |
| `PUT` | `/api/settings` | Einstellungen aktualisieren |
| `POST` | `/api/settings/test-imap` | IMAP-Verbindung testen |
| `POST` | `/api/settings/test-paperless` | Paperless-Verbindung testen |
| `POST` | `/api/settings/test-ai` | Anthropic API-Key validieren |
### 4.4 Status & Worker
| Method | Endpoint | Beschreibung |
|--------|----------|-------------|
| `GET` | `/api/status` | IMAP-Status, Worker-Status, Statistiken |
| `POST` | `/api/worker/start` | Worker starten |
| `POST` | `/api/worker/stop` | Worker stoppen |
| `POST` | `/api/worker/process-now` | Sofortige Verarbeitung auslösen |
---
## 5. Deployment
### 5.1 Docker Compose
MailSort wird als einzelner Docker-Container deployed. Das Frontend wird als statische Files vom Backend ausgeliefert (kein separater nginx nötig).
```yaml
version: '3.8'
services:
  mailsort:
    image: ghcr.io/[username]/mailsort:latest
    container_name: mailsort
    restart: unless-stopped
    ports:
      - '8080:8080'
    volumes:
      - ./data:/data
```
`/data` enthält:
- `/data/mailsort.db` – SQLite Datenbank (Rules, Settings, Audit-Log)
- `/data/logs/` – optionale Log-Files
### 5.2 Erste Einrichtung
1. Container starten
2. Web-UI aufrufen (Port 8080)
3. IMAP-Verbindung konfigurieren und testen
4. Optional: Paperless-NGX + Anthropic API konfigurieren
5. Erste Regeln anlegen
6. Worker starten
### 5.3 Konfiguration
Alle Laufzeit-Einstellungen werden in der Web-UI konfiguriert und in SQLite gespeichert. Es gibt keine `.env`-Datei für Laufzeit-Config.
Einzige Ausnahme: `MAILSORT_SECRET_KEY` als Umgebungsvariable für die Session-Verschlüsselung.
---
## 6. Open Source Strategie
### 6.1 Lizenz
MIT License – maximale Freiheit für Community und kommerzielle Nutzung.
### 6.2 Repository-Struktur
```
mailsort/
  backend/
    app/
      api/           # Route-Handler
      core/          # IMAPWorker, RuleEngine, AIClassifier, ActionExecutor
      models/        # SQLModel Datenmodelle
      services/      # Paperless, Webhook
    tests/
    Dockerfile
  frontend/
    src/
      components/
      pages/
      api/           # API-Client
    Dockerfile
  docker-compose.yml
  README.md
  CONTRIBUTING.md
```
### 6.3 Roadmap
#### v1.0 – MVP
- IMAP Polling + IDLE
- Regelengine (alle Bedingungstypen)
- KI-Fallback (Anthropic)
- Paperless-NGX Integration
- Audit-Log
- Web-UI (Dashboard, Regeleditor, Einstellungen, Log-Ansicht)
- Docker Compose Deployment
#### v1.1
- GMail OAuth2 Support
- Mehrere Postfächer
- Regel-Export/Import als JSON
- Webhook-Aktionen + Templates (ntfy, Slack, Gotify)
#### v1.2
- Weitere KI-Provider (OpenAI, Ollama)
- Statistik-Charts im Dashboard
- E-Mail-Preview im Audit-Log
- Community Regelsets
---
## 7. Hinweise für Claude Code
### 7.1 Empfohlener Startpunkt
1. Backend-Skeleton: FastAPI App, SQLModel-Modelle, leere Router
2. IMAPWorker mit Polling (IDLE später)
3. RuleEngine (unit-testbar ohne IMAP)
4. ActionExecutor
5. AIClassifier
6. Frontend (parallel oder danach)
### 7.2 Kritische Implementierungsdetails
- **IMAP UID verwenden** (nicht Sequenznummer) – Sequenznummern ändern sich nach EXPUNGE
- **Mail-Lesestatus explizit steuern:** nach Verarbeitung SEEN setzen, vorher UNSEEN lassen
- **Transaktionsreihenfolge:** 1. Audit-Log schreiben → 2. Aktion ausführen → 3. Log-Status updaten
- **IMAP MOVE** (RFC 6851) verwenden falls Server unterstützt, sonst COPY + DELETE
- **Ordner mit Punkt-Notation erstellen:** `INBOX.Homelab` (Manitu-kompatibel)
- **Anthropic Exponential Backoff:** `max_retries=3`, delays `[1, 2, 4]` Sekunden
- **Mail-Body:** zuerst `text/plain` versuchen, dann `text/html` (BeautifulSoup Strip-Tags)
### 7.3 Testing
- **RuleEngine:** Unit-Tests mit Mock-Mail-Objekten
- **IMAPWorker:** Integration-Test gegen lokalen Dovecot oder greenmail
- **AIClassifier:** Mock des Anthropic-Clients
- **ActionExecutor:** Mock-IMAP-Server
### 7.4 Konfigurationspriorität
Einstellungen werden in dieser Reihenfolge geladen (höhere Priorität überschreibt niedrigere):
1. Umgebungsvariablen (nur `MAILSORT_SECRET_KEY`)
2. SQLite-Datenbank (alle anderen Settings)
3. Default-Werte im Code
