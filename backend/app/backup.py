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
