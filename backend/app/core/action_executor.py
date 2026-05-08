from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING
from imapclient import IMAPClient
from ..models.rule import ActionType

if TYPE_CHECKING:
    from .imap_worker import RawMail

log = logging.getLogger(__name__)

IMAP_MOVE_CAP = b"MOVE"


@dataclass
class ActionResult:
    success: bool
    target: str = ""
    error: str = ""


class ActionExecutor:
    def __init__(self, imap: IMAPClient, trash_folder: str = "Trash") -> None:
        self.imap = imap
        self.trash_folder = trash_folder
        self._delimiter: str | None = None

    def execute(self, mail: "RawMail", action: ActionType, params: dict) -> ActionResult:
        try:
            match action:
                case ActionType.move:
                    folder = self._resolve_folder(params.get("folder", "INBOX"))
                    self._move(mail.uid, folder)
                    return ActionResult(success=True, target=folder)
                case ActionType.label:
                    label = params.get("label", "")
                    self.imap.set_flags(mail.uid, [label.encode()])
                    return ActionResult(success=True, target=label)
                case ActionType.trash:
                    self._move(mail.uid, self.trash_folder)
                    return ActionResult(success=True, target=self.trash_folder)
                case ActionType.keep:
                    return ActionResult(success=True, target="INBOX")
                case ActionType.paperless:
                    folder = self._resolve_folder(params.get("folder", "INBOX.Paperless"))
                    self._move(mail.uid, folder)
                    return ActionResult(success=True, target=folder)
                case ActionType.webhook:
                    return ActionResult(success=True, target=params.get("url", ""))
                case _:
                    return ActionResult(success=False, error=f"Unknown action: {action}")
        except Exception as exc:
            log.exception("ActionExecutor error for uid %s", mail.uid)
            return ActionResult(success=False, error=str(exc))

    def subscribe_rule_folders(self, folders: list[str]) -> None:
        """Stellt sicher, dass alle Regelzielordner abonniert sind – auch ohne eingehende Mails."""
        for folder in folders:
            self._ensure_folder(self._resolve_folder(folder))

    def _resolve_folder(self, folder: str) -> str:
        """Gibt den vollständigen IMAP-Pfad zurück (INBOX{delim}{folder} wenn kein Pfad angegeben)."""
        delim = self._get_delimiter()
        # Bereits ein Pfad mit Trennzeichen oder explizit mit INBOX → unverändert
        if delim in folder or folder.upper().startswith("INBOX"):
            return folder
        return f"INBOX{delim}{folder}"

    def _get_delimiter(self) -> str:
        if self._delimiter is None:
            folders = self.imap.list_folders()
            if folders:
                raw = folders[0][1]
                self._delimiter = raw.decode() if isinstance(raw, bytes) else (raw or ".")
            else:
                self._delimiter = "."
        return self._delimiter

    def _move(self, uid: int, folder: str) -> None:
        self._ensure_folder(folder)
        caps = self.imap.capabilities()
        try:
            if IMAP_MOVE_CAP in caps:
                self.imap.move(uid, folder)
            else:
                self.imap.copy(uid, folder)
                self.imap.delete_messages(uid)
                self.imap.expunge()
        except Exception as exc:
            if "EXPUNGEISSUED" in str(exc):
                log.warning("UID %s already gone on server (EXPUNGEISSUED), skipping move", uid)
                return
            raise

    def _ensure_folder(self, folder: str) -> None:
        existing = [f.decode() if isinstance(f, bytes) else f for _, _, f in self.imap.list_folders()]
        if folder not in existing:
            self.imap.create_folder(folder)
            log.info("Created IMAP folder: %s", folder)
        try:
            subscribed = {f.decode() if isinstance(f, bytes) else f for _, _, f in self.imap.list_sub_folders()}
            if folder not in subscribed:
                self.imap.subscribe_folder(folder)
                log.info("Subscribed to IMAP folder: %s", folder)
        except Exception:
            pass
