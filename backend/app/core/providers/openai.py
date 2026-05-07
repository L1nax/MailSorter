from __future__ import annotations
import logging
from typing import TYPE_CHECKING
from openai import AsyncOpenAI
from .base import AIProvider, ClassificationResult
from ...models.rule import ActionType

if TYPE_CHECKING:
    from ..imap_worker import RawMail

log = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        self.api_key = api_key
        self.model = model or "gpt-4o-mini"
        self.client = AsyncOpenAI(api_key=api_key or "ollama", base_url=base_url)

    async def classify(
        self, mail: "RawMail", folders: list[str], prompt: str
    ) -> ClassificationResult:
        if not self.api_key:
            return ClassificationResult(ActionType.keep, {}, "AI not configured: API key missing")

        user_msg = self._build_prompt(mail, folders)
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                max_tokens=64,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_msg},
                ],
            )
            folder = response.choices[0].message.content.strip()
            if folder in folders:
                return ClassificationResult(ActionType.move, {"folder": folder})
            log.warning("OpenAI returned unknown folder %r", folder)
            return ClassificationResult(ActionType.keep, {}, f"AI returned unknown folder: {folder}")
        except Exception as exc:
            log.exception("OpenAI classifier error")
            return ClassificationResult(ActionType.keep, {}, f"AI failed: {exc}")

    async def test_connection(self) -> tuple[bool, str]:
        try:
            await self.client.chat.completions.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True, "Connection successful"
        except Exception as exc:
            return False, str(exc)
