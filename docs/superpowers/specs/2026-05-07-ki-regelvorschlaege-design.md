# Design: KI-Regelvorschläge

**Datum:** 2026-05-07  
**Branch:** KI-Rules  
**Status:** Genehmigt

---

## Ziel

Die KI-Klassifizierung soll nicht dauerhaft für jede Mail aufgerufen werden müssen. Stattdessen lernt das System aus KI-Entscheidungen: Erkennt es ein wiederkehrendes Muster, schlägt es dem Nutzer eine permanente Regel vor. Nach Genehmigung greift die RuleEngine lokal — kein KI-Aufruf mehr für diesen Fall.

---

## Überblick

1. KI-Provider liefern neben der Aktion strukturierte **Signals** (welches Merkmal war ausschlaggebend)
2. Signals werden pro Signal+Ziel-Kombination **gezählt** (`ai_signal`-Tabelle)
3. Ab Schwellwert N wird ein **Regelvorschlag** erstellt (`rule_suggestion`-Tabelle)
4. Nutzer genehmigt, snoozt oder lehnt dauerhaft ab
5. Bei Genehmigung wird eine vollständige Regel in die RuleEngine geschrieben

---

## 1. Datenmodell

### Neue Tabelle: `ai_signal`

Zählt beobachtete KI-Signale pro Signal+Ziel-Kombination.

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| `id` | UUID PK | |
| `signal_type` | str | z.B. `from_domain`, `from_address`, `subject_contains` |
| `signal_value` | str | z.B. `amazon.de` |
| `action` | str | z.B. `move` |
| `target` | str | z.B. `Rechnungen` |
| `count` | int | Wie oft dieses Signal+Ziel beobachtet wurde |
| `last_seen` | datetime | Timestamp der letzten Beobachtung |
| `account_id` | str FK | FK zu `mailaccount` |

Unique-Constraint auf `(signal_type, signal_value, action, target, account_id)`.

### Neue Tabelle: `rule_suggestion`

Ein vom System generierter Regelvorschlag, der auf Nutzer-Genehmigung wartet.

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| `id` | UUID PK | |
| `signal_type` | str | Das auslösende Signal |
| `signal_value` | str | Der Wert des auslösenden Signals |
| `action` | str | Vorgeschlagene Aktion |
| `target` | str | Vorgeschlagenes Ziel (Ordner, URL, etc.) |
| `suggested_conditions` | JSON | Fertige Bedingungsliste für die Regel |
| `suggested_rule_name` | str | z.B. `"[KI] amazon.de → Rechnungen"` |
| `status` | enum | `pending` \| `accepted` \| `snoozed` \| `dismissed` |
| `snooze_until` | datetime? | Gesetzt wenn `status = snoozed` |
| `created_at` | datetime | |
| `account_id` | str FK | FK zu `mailaccount` |

Unique-Constraint auf `(signal_type, signal_value, action, target, account_id)` — pro Kombination nur ein aktiver Vorschlag.

### Änderung: `settings`

Zwei neue Felder:
- `suggestion_threshold: int` — Standard: `3`
- `suggestion_snooze_days: int` — Standard: `30`

---

## 2. KI-Provider: Signals

### `ClassificationResult` (erweitert)

```python
class ClassificationResult:
    __slots__ = ("action", "params", "warning", "signals")

    def __init__(self, action, params, warning="", signals=None):
        self.action = action
        self.params = params
        self.warning = warning
        self.signals = signals or []  # list[dict[str, str]]
```

Signal-Format: `{"type": "<ConditionType>", "value": "<wert>"}`

Erlaubte `type`-Werte (identisch mit vorhandenen `ConditionType`-Werten):
`from_domain`, `from_address`, `subject_contains`, `has_attachment`, `attachment_type`, `to_address`

### Prompt-Erweiterung

Der KI-Prompt (in `_build_prompt`) wird um eine Anweisung ergänzt: Nach der Aktionszeile soll die KI eine zweite Zeile mit den ausschlaggebenden Signalen liefern.

Erwartetes Antwortformat:
```
move:Rechnungen
signals: from_domain:amazon.de, subject_contains:Rechnung
```

### Response-Parser (`_parse_response`)

Die zweite Zeile wird optional geparst:
- Beginnt mit `signals:` → Signale extrahieren und validieren
- Fehlt die Zeile → `signals = []` (Abwärtskompatibilität, kein Breaking Change)
- Unbekannte Signal-Typen werden stillschweigend ignoriert

---

## 3. Signal-Zählung und Vorschlag-Logik

Läuft im `IMAPWorker` nach jeder erfolgreichen KI-Klassifizierung mit nicht-leerem `signals`-Array.

### Ablauf pro Signal

1. **Upsert `ai_signal`** — suche Eintrag mit `(signal_type, signal_value, action, target, account_id)`:
   - Gefunden: `count += 1`, `last_seen = now`
   - Nicht gefunden: neuer Eintrag mit `count = 1`

2. **Schwellwert prüfen** — `count >= suggestion_threshold`?  
   Nein → fertig.

3. **Doppelprüfung** (wenn Schwellwert erreicht):
   - Existiert bereits eine aktive Regel mit demselben Signal? → kein Vorschlag
   - Existiert ein `rule_suggestion` mit `status = pending`? → kein Vorschlag
   - Existiert ein `rule_suggestion` mit `status = snoozed` und `snooze_until > now`? → kein Vorschlag
   - Existiert ein `rule_suggestion` mit `status = dismissed`? → kein Vorschlag

4. **Vorschlag erstellen** — neuer `rule_suggestion`-Eintrag:
   - `suggested_conditions`: `[{"type": signal_type, "value": signal_value, "operator": "contains"}]`
   - `suggested_rule_name`: `f"[KI] {signal_value} → {target}"`
   - `status: pending`

### Snooze-Ablauf

Abgelaufene Snoozes (`snooze_until < now`) gelten in der Doppelprüfung als nicht existent → ein neuer Vorschlag kann entstehen. Der alte `rule_suggestion`-Eintrag wird dabei auf `status = pending` zurückgesetzt (kein Duplikat).

---

## 4. REST API

### Neuer Router: `/api/suggestions`

| Method | Endpoint | Beschreibung |
|--------|----------|-------------|
| `GET` | `/api/suggestions` | Alle Vorschläge (filter: `status`) |
| `GET` | `/api/suggestions/count` | Anzahl offener Vorschläge (für Badge) |
| `POST` | `/api/suggestions/{id}/accept` | Annehmen → Regel erstellen, Status `accepted` |
| `POST` | `/api/suggestions/{id}/snooze` | Body: `{"days": 30}` → Status `snoozed` |
| `POST` | `/api/suggestions/{id}/dismiss` | Dauerhaft ablehnen → Status `dismissed` |

### Accept-Logik

Bei `POST /api/suggestions/{id}/accept`:
1. `suggested_conditions` aus dem Vorschlag laden
2. Neue `Rule` erstellen mit:
   - `name`: `suggested_rule_name`
   - `conditions`: `suggested_conditions`
   - `action` + `action_params`: aus Vorschlag
   - `priority`: höchste vorhandene Priorität + 1 (ans Ende der Liste)
   - `enabled`: `true`
3. `rule_suggestion.status = accepted`

---

## 5. UI

### Dashboard (bestehend, erweitert)

- Badge `"{N} Regelvorschläge"` — nur sichtbar wenn N > 0
- Klick navigiert zu `/suggestions`
- Daten kommen von `GET /api/suggestions/count`

### Neue Seite: `/suggestions`

**Tab "Offen":**
- Tabelle: Signal-Typ | Signal-Wert | Aktion | Ziel | Erkannt N× | Zuletzt gesehen
- Pro Zeile: Button **Annehmen** (öffnet Bestätigungs-Modal mit Regel-Vorschau) | Dropdown **Snooze** (7 / 30 / 90 Tage) | Button **Ablehnen**
- Leerzustand: "Keine offenen Vorschläge"

**Tab "Verlauf":**
- Tabelle aller `accepted`, `snoozed`, `dismissed` Vorschläge mit Status und Datum

**Einstellungen auf der Seite:**
- Schwellwert N: Spinner (min 1, max 20, Standard 3)
- Standard-Snooze: Dropdown (7 / 30 / 90 Tage)

### Einstellungen-Seite (bestehend, erweitert)

- Neuer Abschnitt "KI-Regelvorschläge" mit denselben zwei Feldern

---

## Nicht im Scope

- Automatisches Annehmen ohne Nutzer-Bestätigung
- Vorschläge für komplexe Mehr-Bedingungs-Regeln (AND-Verknüpfung)
- Vorschläge basierend auf Body-Inhalt (`body_contains`) — zu unspezifisch
- Betreff-Regex-Regeln (`subject_regex`) aus KI-Vorschlägen
