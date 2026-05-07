# backend/app/core/providers/base.py
from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from ...models.rule import ActionType

if TYPE_CHECKING:
    from ..imap_worker import RawMail

log = logging.getLogger(__name__)

ALLOWED_SIGNAL_TYPES = frozenset({
    "from_domain", "from_address", "subject_contains",
    "has_attachment", "attachment_type", "to_address",
})


def _parse_signals(signals_str: str) -> list[dict]:
    signals = []
    for part in signals_str.split(","):
        part = part.strip()
        if ":" not in part:
            continue
        typ, _, val = part.partition(":")
        typ = typ.strip()
        val = val.strip()
        if typ in ALLOWED_SIGNAL_TYPES and val:
            signals.append({"type": typ, "value": val})
    return signals


class ClassificationResult:
    __slots__ = ("action", "params", "warning", "signals")

    def __init__(
        self,
        action: ActionType,
        params: dict,
        warning: str = "",
        signals: list[dict] | None = None,
    ) -> None:
        self.action = action
        self.params = params
        self.warning = warning
        self.signals: list[dict] = signals if signals is not None else []


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
        lines = text.split("\n", 1)
        action_line = lines[0].strip()
        signals_line = lines[1].strip() if len(lines) > 1 else ""

        signals: list[dict] = []
        if signals_line.lower().startswith("signals:"):
            signals = _parse_signals(signals_line[len("signals:"):].strip())

        if not action_line or len(action_line) > 200:
            return ClassificationResult(
                ActionType.keep, {}, f"AI: ungültige Antwort: {action_line!r}", signals=signals
            )

        if action_line == "keep":
            return ClassificationResult(ActionType.keep, {}, signals=signals)

        if action_line == "trash":
            return ClassificationResult(ActionType.trash, {}, signals=signals)

        if action_line == "paperless":
            return ClassificationResult(ActionType.paperless, {}, signals=signals)

        if action_line.startswith("paperless:"):
            folder = action_line[len("paperless:"):].strip()
            params = {"folder": folder} if folder else {}
            return ClassificationResult(ActionType.paperless, params, signals=signals)

        if action_line.startswith("move:"):
            folder = action_line[len("move:"):].strip()
            if not folder:
                return ClassificationResult(
                    ActionType.keep, {}, "AI: move ohne Ordner", signals=signals
                )
            if folder not in folders:
                log.info("AI schlug neuen Ordner vor: %r", folder)
            return ClassificationResult(ActionType.move, {"folder": folder}, signals=signals)

        if action_line not in folders:
            log.info("AI schlug neuen Ordner vor (plain): %r", action_line)
        return ClassificationResult(ActionType.move, {"folder": action_line}, signals=signals)
