from __future__ import annotations
import asyncio
import email
import logging
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
from .ai_classifier import AIClassifier

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
    if not host or not user or not password:
        return False, "IMAP not fully configured"
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
            try:
                await self.process_once()
            except Exception:
                log.exception("IMAPWorker loop error")
            with Session(engine) as s:
                interval = int(get_setting(s, "poll_interval_seconds"))
            await asyncio.sleep(interval)

    async def process_once(self) -> None:
        with Session(engine) as session:
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
        rule_id = None
        rule_name = None
        action_type = None
        action_params: dict[str, Any] = {}

        if matched_rule:
            rule_id = matched_rule.id
            rule_name = matched_rule.name
            action_type = matched_rule.action
            action_params = matched_rule.action_params or {}
        elif ai_enabled and ai_key:
            # Run async AI in sync context via new event loop
            import asyncio as _asyncio
            with Session(engine) as s:
                from sqlmodel import select as _select
                target_folders = [r.action_params.get("folder", "") for r in s.exec(_select(Rule)).all() if r.action_params.get("folder")]
            classifier = AIClassifier(ai_key, ai_model, ai_prompt, target_folders)
            result = _asyncio.run(classifier.classify(mail))
            rule_name = "AI"
            action_type = result.action
            action_params = result.params

        if action_type is None:
            self._write_log(mail, rule_id, rule_name or "no match", "keep", inbox_folder, AuditStatus.success, "")
            imap.set_flags(mail.uid, [b"\\Seen"])
            return

        # Handle Paperless special case
        if action_type == "paperless":
            from ..services.paperless import upload_pdf_sync
            with Session(engine) as s:
                paperless_url = get_setting(s, "paperless_url")
                paperless_token = get_setting(s, "paperless_token")
            for filename, data in mail.raw_attachments:
                if filename.lower().endswith(".pdf"):
                    ok, err = upload_pdf_sync(paperless_url, paperless_token, filename, data, mail)
                    if not ok:
                        self._write_log(mail, rule_id, rule_name, action_type, filename, AuditStatus.error, err)
                        return

        # Handle Webhook
        if action_type == "webhook":
            from ..services.webhook import fire_webhook_sync
            url = action_params.get("url", "")
            fire_webhook_sync(url, mail)

        result = executor.execute(mail, action_type, action_params)
        status = AuditStatus.success if result.success else AuditStatus.error
        self._write_log(mail, rule_id, rule_name, str(action_type), result.target, status, result.error)

        if result.success:
            imap.set_flags(mail.uid, [b"\\Seen"])

    @staticmethod
    def _write_log(
        mail: RawMail,
        rule_id: str | None,
        rule_name: str | None,
        action: str,
        target: str,
        status: AuditStatus,
        error_msg: str,
    ) -> None:
        with Session(engine) as s:
            entry = AuditLog(
                timestamp=datetime.utcnow(),
                message_id=mail.message_id,
                from_address=mail.from_address,
                subject=mail.subject,
                rule_id=rule_id,
                rule_name=rule_name,
                action=action,
                target=target,
                status=status,
                error_msg=error_msg or None,
            )
            s.add(entry)
            s.commit()
