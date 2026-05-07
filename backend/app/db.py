from __future__ import annotations
import logging
import os
from sqlmodel import SQLModel, Session, create_engine

log = logging.getLogger(__name__)

DATA_DIR = os.environ.get("MAILSORT_DATA_DIR", "/data")
DB_PATH = os.path.join(DATA_DIR, "mailsort.db")

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


def init_db() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    # Alle Models importieren damit SQLModel.metadata sie kennt
    from . import models  # noqa: F401
    SQLModel.metadata.create_all(engine)
    _migrate()


def _migrate() -> None:
    from sqlalchemy import text
    with engine.connect() as conn:
        for table, column, col_type in [
            ("rule", "account_id", "TEXT"),
            ("auditlog", "account_id", "TEXT"),
            ("auditlog", "account_name", "TEXT"),
        ]:
            cols = [row[1] for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()]
            if column not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                conn.commit()
                log.info("Migration: Spalte %s.%s hinzugefügt", table, column)

    # Alte IMAP-Settings als ersten Account migrieren
    from sqlmodel import select, func
    from .models.account import MailAccount
    from .models.settings import Settings
    from .config import get_setting

    with Session(engine) as s:
        count = s.exec(select(func.count(MailAccount.id))).one()
        if count == 0:
            host = get_setting(s, "imap_host")
            if host:
                account = MailAccount(
                    name="Standard",
                    imap_host=host,
                    imap_port=int(get_setting(s, "imap_port") or "993"),
                    imap_user=get_setting(s, "imap_user"),
                    imap_password=get_setting(s, "imap_password"),
                    imap_tls=get_setting(s, "imap_tls") == "true",
                    imap_folder=get_setting(s, "imap_folder") or "INBOX",
                    trash_folder=get_setting(s, "trash_folder") or "Trash",
                    poll_interval_seconds=int(get_setting(s, "poll_interval_seconds") or "60"),
                    use_idle=get_setting(s, "use_idle") == "true",
                )
                s.add(account)
                for key in [
                    "imap_host", "imap_port", "imap_user", "imap_password",
                    "imap_tls", "imap_folder", "trash_folder",
                    "poll_interval_seconds", "use_idle",
                ]:
                    row = s.get(Settings, key)
                    if row:
                        s.delete(row)
                s.commit()
                log.info("Migration: Account 'Standard' aus alten IMAP-Settings angelegt")


def get_session():
    with Session(engine) as session:
        yield session
