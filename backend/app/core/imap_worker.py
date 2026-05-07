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
from sqlmodel import Session, select, or_
from ..db import engine
from ..config import get_setting
from ..models import Rule, AuditLog, AuditStatus
from ..models.account import MailAccount
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
    raw_attachments: list[tuple[str, bytes]] = field(default_factory=list)


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
        msg = exc.args[0] if exc.args else exc
        if isinstance(msg, bytes):
            msg = msg.decode('utf-8', errors='replace')
        else:
            msg = str(msg)
            if len(msg) > 3 and msg[0] == 'b' and msg[1] in ('"', "'") and msg[-1] == msg[1]:
                msg = msg[2:-1]
        return False, str(msg)


class IMAPWorker:
    def __init__(self, account: MailAccount) -> None:
        self.account = account
        self.running = False
        self._process_event = threading.Event()

    async def run(self) -> None:
        self.running = True
        try:
            await self._run()
        except asyncio.CancelledError:
            pass
        finally:
            self.running = False

    async def _run(self) -> None:
        while self.running:
            if self.account.use_idle:
                try:
                    await asyncio.to_thread(self._run_idle_sync)
                except Exception:
                    log.exception("IDLE error for account '%s', reconnecting in 30s", self.account.name)
                    await asyncio.sleep(30)
            else:
                try:
                    await self.process_once()
                except Exception:
                    log.exception("IMAPWorker loop error for account '%s'", self.account.name)
                await asyncio.sleep(self.account.poll_interval_seconds)

    async def process_once(self) -> None:
        if self.account.use_idle and self.running:
            self._process_event.set()
            return

        if not self.account.imap_host or not self.account.imap_user or not self.account.imap_password:
            log.debug("Account '%s' not configured, skipping", self.account.name)
            return

        with Session(engine) as session:
            ai_enabled = get_setting(session, "ai_enabled") == "true"
            ai_key = get_setting(session, "ai_api_key")
            ai_model = get_setting(session, "ai_model")
            ai_prompt = get_setting(session, "ai_system_prompt")

        try:
            await asyncio.to_thread(
                self._process_imap,
                self.account.imap_host,
                self.account.imap_port,
                self.account.imap_user,
                self.account.imap_password,
                self.account.imap_tls,
                self.account.imap_folder,
                self.account.trash_folder,
                ai_enabled, ai_key, ai_model, ai_prompt,
            )
        except Exception:
            log.exception("IMAP processing error for account '%s'", self.account.name)

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
        try:
            uids = imap.search(["UNSEEN", "UNKEYWORD", "$MailSortProcessed"])
        except Exception:
            uids = imap.search(["UNSEEN"])
        if not uids:
            return
        log.info("Account '%s': %d ungelesene Mails gefunden", self.account.name, len(uids))

        with Session(engine) as session:
            rules = session.exec(
                select(Rule)
                .where(Rule.enabled == True)
                .where(or_(Rule.account_id == None, Rule.account_id == self.account.id))
                .order_by(Rule.priority)
            ).all()

        rule_engine = RuleEngine(list(rules))
        executor = ActionExecutor(imap, trash_folder=trash)

        rule_folders = [
            r.action_params.get("folder")
            for r in rules
            if r.action == "move" and r.action_params and r.action_params.get("folder")
        ]
        if rule_folders:
            executor.subscribe_rule_folders(rule_folders)

        for uid in uids:
            try:
                raw_data = imap.fetch([uid], ["BODY.PEEK[]"])
                raw_bytes = raw_data[uid][b"BODY[]"]
                mail = _parse_mail(uid, raw_bytes)
                self._process_single(mail, rule_engine, executor, imap, ai_enabled, ai_key, ai_model, ai_prompt, folder)
            except Exception:
                log.exception("Error processing UID %s on account '%s'", uid, self.account.name)
            finally:
                try:
                    imap.add_flags([uid], [b"$MailSortProcessed"])
                except Exception:
                    pass

    def _run_idle_sync(self) -> None:
        IDLE_REFRESH_SECS = 20 * 60
        IDLE_CHECK_SECS = 30

        host = self.account.imap_host
        port = self.account.imap_port
        user = self.account.imap_user
        password = self.account.imap_password
        tls = self.account.imap_tls
        folder = self.account.imap_folder
        trash = self.account.trash_folder

        if not host or not user or not password:
            log.debug("Account '%s' not configured, skipping IDLE", self.account.name)
            return

        with Session(engine) as s:
            ai_enabled = get_setting(s, "ai_enabled") == "true"
            ai_key = get_setting(s, "ai_api_key")
            ai_model = get_setting(s, "ai_model")
            ai_prompt = get_setting(s, "ai_system_prompt")

        with IMAPClient(host, port=port, ssl=tls) as imap:
            imap.login(user, password)
            imap.select_folder(folder, readonly=False)
            self._process_imap_session(imap, folder, trash, ai_enabled, ai_key, ai_model, ai_prompt)

            log.info("Account '%s': IDLE-Modus aktiv", self.account.name)
            imap.idle()
            idle_start = time.monotonic()

            while self.running:
                try:
                    responses = imap.idle_check(timeout=IDLE_CHECK_SECS)
                except Exception:
                    log.exception("IDLE: idle_check fehlgeschlagen für '%s'", self.account.name)
                    return

                elapsed = time.monotonic() - idle_start
                has_new = any(
                    typ == b"EXISTS"
                    for entry in (responses or [])
                    for _, typ in [entry[:2]]
                )
                force = self._process_event.is_set()

                if has_new or elapsed >= IDLE_REFRESH_SECS or force:
                    try:
                        imap.idle_done()
                    except Exception:
                        log.exception("IDLE: idle_done fehlgeschlagen für '%s'", self.account.name)
                        return

                    self._process_event.clear()

                    if has_new or force:
                        try:
                            imap.select_folder(folder, readonly=False)
                            self._process_imap_session(imap, folder, trash, ai_enabled, ai_key, ai_model, ai_prompt)
                        except Exception:
                            log.exception("IDLE: Verarbeitung fehlgeschlagen für '%s'", self.account.name)
                            return
                    else:
                        log.info("IDLE: Verbindung für '%s' nach %.0fs erneuert", self.account.name, elapsed)

                    try:
                        imap.select_folder(folder, readonly=False)
                        imap.idle()
                        idle_start = time.monotonic()
                    except Exception:
                        log.exception("IDLE: Neustart fehlgeschlagen für '%s'", self.account.name)
                        return

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
                _provider = _get_provider(s)
                account_rules = s.exec(
                    select(Rule)
                    .where(Rule.enabled == True)
                    .where(or_(Rule.account_id == None, Rule.account_id == self.account.id))
                ).all()
                target_folders = [
                    r.action_params.get("folder", "")
                    for r in account_rules
                    if r.action_params and r.action_params.get("folder")
                ]
                paperless_url = get_setting(s, "paperless_url")
                paperless_token = get_setting(s, "paperless_token")
            has_pdf = any("pdf" in t.lower() for t in mail.attachment_types)
            paperless_ok = bool(paperless_url and paperless_token)
            effective_prompt = ai_prompt
            if paperless_ok and has_pdf:
                effective_prompt += (
                    "\n\nPaperless-NGX ist konfiguriert. "
                    "Nutze paperless:<Ordner> oder paperless für PDF-Anhänge, die archiviert werden sollen."
                )
            format_lines = ["move:<Ordner>"]
            if paperless_ok and has_pdf:
                format_lines += ["paperless:<Ordner>", "paperless"]
            format_lines += ["keep", "trash"]
            effective_prompt += (
                "\n\nAntworte ausschließlich mit einer der folgenden Aktionen – "
                "kein weiterer Text, keine Erklärung:\n"
                + "\n".join(f"  {a}" for a in format_lines)
            )
            effective_prompt += (
                "\n\nOptional: Füge nach der Aktionszeile eine zweite Zeile mit dem "
                "ausschlaggebenden Signal hinzu:\n"
                "signals: <typ>:<wert>\n"
                "Erlaubte Typen: from_domain, from_address, subject_contains, "
                "has_attachment, attachment_type, to_address"
            )
            ai_result = _asyncio.run(_provider.classify(mail, target_folders, effective_prompt))
            rule_name = "AI"
            action_type = ai_result.action
            action_params = ai_result.params
            ai_warning = ai_result.warning
            if ai_result.signals:
                from .suggestion_service import process_signals as _track_signals
                with Session(engine) as _s:
                    _track_signals(
                        ai_result.signals,
                        str(action_type),
                        action_params.get("folder", ""),
                        self.account.id,
                        _s,
                    )

        if action_type is None:
            action_type = "keep"
            rule_name = rule_name or "no match"

        log_id = self._create_log_entry(
            mail, rule_id, rule_name, str(action_type),
            self.account.id, self.account.name,
        )

        mark_as_read: bool = action_params.get("mark_as_read", False)

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
        self._finalize_log_entry(log_id, exec_result.target, status, exec_result.error or ai_warning)

        if exec_result.success and mark_as_read:
            imap.set_flags(mail.uid, [b"\\Seen"])

    @staticmethod
    def _create_log_entry(
        mail: RawMail,
        rule_id: str | None,
        rule_name: str | None,
        action: str,
        account_id: str = "",
        account_name: str = "",
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
                account_id=account_id or None,
                account_name=account_name or None,
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
