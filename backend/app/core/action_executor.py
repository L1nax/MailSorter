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

    def execute(self, mail: "RawMail", action: ActionType, params: dict) -> ActionResult:
        try:
            match action:
                case ActionType.move:
                    folder = params.get("folder", "INBOX")
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
                    # Delegated to PaperlessService; ActionExecutor handles the final move
                    folder = params.get("folder", "INBOX.Paperless")
                    self._move(mail.uid, folder)
                    return ActionResult(success=True, target=folder)
                case ActionType.webhook:
                    # Webhooks are fire-and-forget HTTP calls handled by WebhookService
                    return ActionResult(success=True, target=params.get("url", ""))
                case _:
                    return ActionResult(success=False, error=f"Unknown action: {action}")
        except Exception as exc:
            log.exception("ActionExecutor error for uid %s", mail.uid)
            return ActionResult(success=False, error=str(exc))

    def _move(self, uid: int, folder: str) -> None:
        self._ensure_folder(folder)
        caps = self.imap.capabilities()
        if IMAP_MOVE_CAP in caps:
            self.imap.move(uid, folder)
        else:
            self.imap.copy(uid, folder)
            self.imap.delete_messages(uid)
            self.imap.expunge()

    def _ensure_folder(self, folder: str) -> None:
        existing = [f.decode() if isinstance(f, bytes) else f for _, _, f in self.imap.list_folders()]
        if folder not in existing:
            self.imap.create_folder(folder)
            log.info("Created IMAP folder: %s", folder)
