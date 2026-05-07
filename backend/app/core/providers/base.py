from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from ...models.rule import ActionType

if TYPE_CHECKING:
    from ..imap_worker import RawMail

log = logging.getLogger(__name__)


class ClassificationResult:
    __slots__ = ("action", "params", "warning")

    def __init__(self, action: ActionType, params: dict, warning: str = "") -> None:
        self.action = action
        self.params = params
        self.warning = warning


class AIProvider(ABC):
    @abstractmethod
    async def classify(
        self, mail: "RawMail", folders: list[str], prompt: str
    ) -> ClassificationResult: ...

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]: ...

    async def list_models(self) -> list[str]:
        return []

    def _build_prompt(self, mail: "RawMail", folders: list[str]) -> str:
        folders_str = "\n".join(f"- {f}" for f in folders) if folders else "(keine vorhanden)"
        has_pdf = any("pdf" in t.lower() for t in mail.attachment_types)
        if mail.attachment_types:
            attachment_info = f"Anhänge: {', '.join(mail.attachment_types)}"
        else:
            attachment_info = "Anhänge: keine"

        actions = "move:<Ordner> | keep | trash"
        if has_pdf:
            actions = "move:<Ordner> | paperless:<Ordner> | paperless | keep | trash"

        return (
            f"Aktion (genau eine): {actions}\n\n"
            f"Vorhandene Ordner:\n{folders_str}\n\n"
            f"From: {mail.from_address}\n"
            f"Subject: {mail.subject}\n"
            f"{attachment_info}\n\n"
            f"{mail.body[:4000]}"
        )

    def _parse_response(self, text: str, folders: list[str]) -> ClassificationResult:
        text = text.strip()
        if not text or len(text) > 200:
            return ClassificationResult(ActionType.keep, {}, f"AI: ungültige Antwort: {text!r}")

        if text == "keep":
            return ClassificationResult(ActionType.keep, {})

        if text == "trash":
            return ClassificationResult(ActionType.trash, {})

        if text == "paperless":
            return ClassificationResult(ActionType.paperless, {})

        if text.startswith("paperless:"):
            folder = text[len("paperless:"):].strip()
            params = {"folder": folder} if folder else {}
            return ClassificationResult(ActionType.paperless, params)

        if text.startswith("move:"):
            folder = text[len("move:"):].strip()
            if not folder:
                return ClassificationResult(ActionType.keep, {}, "AI: move ohne Ordner")
            if folder not in folders:
                log.info("AI schlug neuen Ordner vor: %r", folder)
            return ClassificationResult(ActionType.move, {"folder": folder})

        # Fallback: einfacher Ordnername (Abwärtskompatibilität)
        if text not in folders:
            log.info("AI schlug neuen Ordner vor (plain): %r", text)
        return ClassificationResult(ActionType.move, {"folder": text})
