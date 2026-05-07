from __future__ import annotations
import asyncio
import email
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from email import policy
from email.utils import parseaddr
from typing import Any
from imapclient import IMAPClient
from sqlmodel import Session, select
from ..db import engine
from ..config import get_setting
from ..models import Rule, AuditLog, AuditStatus
from .rule_engine import RuleEngine, MailData
from .action_executor import ActionExecutor

log = logging.getLogger(__name__)


@dataclass
class RawMail:
    uid: int
    message_id: str
    from_address: str
    subject: str
    to_address: str
    body: str
    has_attachment: bool
    attachment_types: list[str]
    raw_attachments: list[tuple[str, bytes]] = field(default_factory=list)  # (filename, data)


def _extract_body(msg: email.message.Message) -> str:
    plain = None
    html = None
    for part in msg.walk():
        ct = part.get_content_type()
        if ct == "text/plain" and plain is None:
            plain = part.get_payload(decode=True).decode(errors="replace")
        elif ct == "text/html" and html is None:
            html = part.get_payload(decode=True).decode(errors="replace")
    if plain:
        return plain
    if html:
        try:
            from bs4 import BeautifulSoup
            return BeautifulSoup(html, "html.parser").get_text(separator="\n")
        except Exception:
            return html
    return ""


def _parse_mail(uid: int, raw: bytes) -> RawMail:
    msg = email.message_from_bytes(raw, policy=policy.compat32)
    _, from_addr = parseaddr(msg.get("From", ""))
    _, to_addr = parseaddr(msg.get("To", ""))
    subject = msg.get("Subject", "")
    message_id = msg.get("Message-ID", "")
    body = _extract_body(msg)

    attachment_types: list[str] = []
    raw_attachments: list[tuple[str, bytes]] = []
    for part in msg.walk():
        if part.get_content_disposition() == "attachment":
            ct = part.get_content_type()
            attachment_types.append(ct)
            filename = part.get_filename() or "attachment"
            data = part.get_payload(decode=True) or b""
            raw_attachments.append((filename, data))

    return RawMail(
        uid=uid,
        message_id=message_id,
        from_address=from_addr,
        subject=subject,
        to_address=to_addr,
        body=body,
        has_attachment=bool(attachment_types),
        attachment_types=attachment_types,
        raw_attachments=raw_attachments,
    )


def test_imap_connection(host: str, port: int, user: str, password: str, tls: bool) -> tuple[bool, str]:
    missing = [name for name, val in [("Host", host), ("Benutzer", user), ("Passwort", password)] if not val]
    if missing:
        return False, f"IMAP nicht vollständig konfiguriert – fehlt: {', '.join(missing)}"
    try:
        with IMAPClient(host, port=port, ssl=tls) as imap:
            imap.login(user, password)
        return True, "Connection successful"
    except Exception as exc:
        return False, str(exc)


class IMAPWorker:
    def __init__(self) -> None:
        self.running = False
        self._task: asyncio.Task | None = None
        self._process_event = threading.Event()

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._run())
        log.info("IMAPWorker started")

    def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()
        log.info("IMAPWorker stopped")

    async def _run(self) -> None:
        while self.running:
            with Session(engine) as s:
                use_idle = get_setting(s, "use_idle") == "true"
            if use_idle:
                try:
                    await asyncio.to_thread(self._run_idle_sync)
                except Exception:
                    log.exception("IDLE error, reconnecting in 30s")
                    await asyncio.sleep(30)
            else:
                try:
                    await self.process_once()
                except Exception:
                    log.exception("IMAPWorker loop error")
                with Session(engine) as s:
                    interval = int(get_setting(s, "poll_interval_seconds"))
                await asyncio.sleep(interval)

    async def process_once(self) -> None:
        with Session(engine) as session:
            use_idle = get_setting(session, "use_idle") == "true"
            host = get_setting(session, "imap_host")
            port = int(get_setting(session, "imap_port"))
            user = get_setting(session, "imap_user")
            password = get_setting(session, "imap_password")
            tls = get_setting(session, "imap_tls") == "true"
            folder = get_setting(session, "imap_folder")
            trash = get_setting(session, "trash_folder")
            ai_enabled = get_setting(session, "ai_enabled") == "true"
            ai_key = get_setting(session, "ai_api_key")
            ai_model = get_setting(session, "ai_model")
            ai_prompt = get_setting(session, "ai_system_prompt")

        if use_idle and self.running:
            # IDLE-Loop läuft bereits – Verarbeitung über Event signalisieren
            self._process_event.set()
            return

        if not host or not user or not password:
            log.debug("IMAP not configured, skipping")
            return

        try:
            await asyncio.to_thread(self._process_imap, host, port, user, password, tls, folder, trash, ai_enabled, ai_key, ai_model, ai_prompt)
        except Exception:
            log.exception("IMAP processing error")

    def _process_imap(
        self,
        host: str, port: int, user: str, password: str, tls: bool,
        folder: str, trash: str,
        ai_enabled: bool, ai_key: str, ai_model: str, ai_prompt: str,
    ) -> None:
        with IMAPClient(host, port=port, ssl=tls) as imap:
            imap.login(user, password)
            imap.select_folder(folder, readonly=False)
            self._process_imap_session(imap, folder, trash, ai_enabled, ai_key, ai_model, ai_prompt)

    def _process_imap_session(
        self,
        imap: IMAPClient,
        folder: str, trash: str,
        ai_enabled: bool, ai_key: str, ai_model: str, ai_prompt: str,
    ) -> None:
        """Verarbeitet alle UNSEEN-Mails auf einer bereits offenen, authentifizierten Verbindung."""
        uids = imap.search(["UNSEEN"])
        if not uids:
            return
        log.info("Found %d unseen mails", len(uids))

        with Session(engine) as session:
            rules = session.exec(select(Rule).where(Rule.enabled == True).order_by(Rule.priority)).all()

        rule_engine = RuleEngine(list(rules))
        executor = ActionExecutor(imap, trash_folder=trash)

        for uid in uids:
            try:
                raw_data = imap.fetch([uid], ["RFC822"])
                raw_bytes = raw_data[uid][b"RFC822"]
                mail = _parse_mail(uid, raw_bytes)
                self._process_single(mail, rule_engine, executor, imap, ai_enabled, ai_key, ai_model, ai_prompt, folder)
            except Exception:
                log.exception("Error processing UID %s", uid)

    def _run_idle_sync(self) -> None:
        """Blockierender IDLE-Loop – läuft in einem Thread via asyncio.to_thread."""
        # RFC 2177: Server dürfen IDLE nach 29 min beenden; wir erneuern nach 20 min.
        IDLE_REFRESH_SECS = 20 * 60
        IDLE_CHECK_SECS = 30  # Granularität, mit der self.running geprüft wird

        with Session(engine) as s:
            host = get_setting(s, "imap_host")
            port = int(get_setting(s, "imap_port"))
            user = get_setting(s, "imap_user")
            password = get_setting(s, "imap_password")
            tls = get_setting(s, "imap_tls") == "true"
            folder = get_setting(s, "imap_folder")
            trash = get_setting(s, "trash_folder")
            ai_enabled = get_setting(s, "ai_enabled") == "true"
            ai_key = get_setting(s, "ai_api_key")
            ai_model = get_setting(s, "ai_model")
            ai_prompt = get_setting(s, "ai_system_prompt")

        if not host or not user or not password:
            log.debug("IMAP not configured, skipping IDLE")
            return

        with IMAPClient(host, port=port, ssl=tls) as imap:
            imap.login(user, password)
            imap.select_folder(folder, readonly=False)

            # Vorhandene ungelesene Mails vor IDLE-Eintritt verarbeiten
            self._process_imap_session(imap, folder, trash, ai_enabled, ai_key, ai_model, ai_prompt)

            log.info("IDLE mode: entering IDLE")
            imap.idle()
            idle_start = time.monotonic()

            while self.running:
                responses = imap.idle_check(timeout=IDLE_CHECK_SECS)
                elapsed = time.monotonic() - idle_start

                has_new = any(typ == b"EXISTS" for _, typ in (responses or []))
                force = self._process_event.is_set()

                if has_new or elapsed >= IDLE_REFRESH_SECS or force:
                    imap.idle_done()
                    self._process_event.clear()

                    if has_new or force:
                        log.info("IDLE: %s", "manuell ausgelöst" if force and not has_new else "EXISTS-Benachrichtigung, verarbeite Mails")
                        self._process_imap_session(imap, folder, trash, ai_enabled, ai_key, ai_model, ai_prompt)
                    else:
                        log.debug("IDLE: Verbindung nach %ds erneuert", IDLE_REFRESH_SECS)

                    imap.idle()
                    idle_start = time.monotonic()

            try:
                imap.idle_done()
            except Exception:
                pass

    def _process_single(
        self,
        mail: RawMail,
        rule_engine: RuleEngine,
        executor: ActionExecutor,
        imap: IMAPClient,
        ai_enabled: bool,
        ai_key: str,
        ai_model: str,
        ai_prompt: str,
        inbox_folder: str,
    ) -> None:
        mail_data = MailData(
            from_address=mail.from_address,
            subject=mail.subject,
            to_address=mail.to_address,
            body=mail.body,
            has_attachment=mail.has_attachment,
            attachment_types=mail.attachment_types,
        )

        matched_rule = rule_engine.evaluate(mail_data)
        rule_id: str | None = None
        rule_name: str | None = None
        action_type: Any = None
        action_params: dict[str, Any] = {}
        ai_warning = ""

        if matched_rule:
            rule_id = matched_rule.id
            rule_name = matched_rule.name
            action_type = matched_rule.action
            action_params = matched_rule.action_params or {}
        elif ai_enabled:
            import asyncio as _asyncio
            with Session(engine) as s:
                from .providers import get_provider as _get_provider
                from sqlmodel import select as _select
                _provider = _get_provider(s)
                target_folders = [r.action_params.get("folder", "") for r in s.exec(_select(Rule)).all() if r.action_params.get("folder")]
            ai_result = _asyncio.run(_provider.classify(mail, target_folders, ai_prompt))
            rule_name = "AI"
            action_type = ai_result.action
            action_params = ai_result.params
            ai_warning = ai_result.warning

        if action_type is None:
            action_type = "keep"
            rule_name = rule_name or "no match"

        # Phase 1: Log-Eintrag schreiben, bevor die Aktion ausgeführt wird
        log_id = self._create_log_entry(mail, rule_id, rule_name, str(action_type))

        mark_as_read: bool = action_params.get("mark_as_read", True)

        # Phase 2: Aktion ausführen
        if str(action_type) == "keep":
            if mark_as_read:
                imap.set_flags(mail.uid, [b"\\Seen"])
            self._finalize_log_entry(log_id, inbox_folder, AuditStatus.success, ai_warning)
            return

        if str(action_type) == "paperless":
            from ..services.paperless import upload_pdf_sync
            with Session(engine) as s:
                paperless_url = get_setting(s, "paperless_url")
                paperless_token = get_setting(s, "paperless_token")
            for filename, data in mail.raw_attachments:
                if filename.lower().endswith(".pdf"):
                    ok, err = upload_pdf_sync(paperless_url, paperless_token, filename, data, mail)
                    if not ok:
                        self._finalize_log_entry(log_id, filename, AuditStatus.error, err)
                        return

        if str(action_type) == "webhook":
            from ..services.webhook import fire_webhook_sync
            url = action_params.get("url", "")
            fire_webhook_sync(url, mail)

        exec_result = executor.execute(mail, action_type, action_params)
        status = AuditStatus.success if exec_result.success else AuditStatus.error

        # Phase 3: Log-Eintrag finalisieren
        self._finalize_log_entry(log_id, exec_result.target, status, exec_result.error or ai_warning)

        if exec_result.success and mark_as_read:
            imap.set_flags(mail.uid, [b"\\Seen"])

    @staticmethod
    def _create_log_entry(
        mail: RawMail,
        rule_id: str | None,
        rule_name: str | None,
        action: str,
    ) -> str:
        with Session(engine) as s:
            entry = AuditLog(
                timestamp=datetime.utcnow(),
                message_id=mail.message_id,
                from_address=mail.from_address,
                subject=mail.subject,
                rule_id=rule_id,
                rule_name=rule_name,
                action=action,
                status=AuditStatus.processing,
            )
            s.add(entry)
            s.commit()
            s.refresh(entry)
            return entry.id

    @staticmethod
    def _finalize_log_entry(
        log_id: str,
        target: str | None,
        status: AuditStatus,
        error_msg: str,
    ) -> None:
        with Session(engine) as s:
            entry = s.get(AuditLog, log_id)
            if entry:
                entry.target = target or None
                entry.status = status
                entry.error_msg = error_msg or None
                s.add(entry)
                s.commit()
