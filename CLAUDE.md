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
