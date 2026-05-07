from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from ...models.rule import ActionType

if TYPE_CHECKING:
    from ..imap_worker import RawMail


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
        folders_str = "\n".join(f"- {f}" for f in folders)
        return (
            f"Available folders:\n{folders_str}\n\n"
            f"From: {mail.from_address}\n"
            f"Subject: {mail.subject}\n\n"
            f"{mail.body[:4000]}"
        )
