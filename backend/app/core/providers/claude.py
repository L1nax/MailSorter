from __future__ import annotations
import asyncio
import logging
from typing import TYPE_CHECKING
import anthropic
from .base import AIProvider, ClassificationResult
from ...models.rule import ActionType

if TYPE_CHECKING:
    from ..imap_worker import RawMail

log = logging.getLogger(__name__)
BACKOFF_DELAYS = [1, 2, 4]


class ClaudeProvider(AIProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model or "claude-sonnet-4-6"
        self.client = anthropic.Anthropic(api_key=api_key)

    async def classify(
        self, mail: "RawMail", folders: list[str], prompt: str
    ) -> ClassificationResult:
        if not self.api_key:
            return ClassificationResult(ActionType.keep, {}, "AI not configured: API key missing")

        user_msg = self._build_prompt(mail, folders)
        last_error: Exception | None = None

        for attempt, delay in enumerate([0] + BACKOFF_DELAYS):
            if delay:
                await asyncio.sleep(delay)
            try:
                response = await asyncio.to_thread(
                    self.client.messages.create,
                    model=self.model,
                    max_tokens=64,
                    system=prompt,
                    messages=[{"role": "user", "content": user_msg}],
                )
                folder = response.content[0].text.strip()
                if not folder or len(folder) > 100:
                    return ClassificationResult(ActionType.keep, {}, f"AI returned invalid folder: {folder!r}")
                if folder not in folders:
                    log.info("Claude suggested new folder %r", folder)
                return ClassificationResult(ActionType.move, {"folder": folder})
            except anthropic.RateLimitError as exc:
                last_error = exc
                log.warning("Claude rate limit (attempt %d/%d)", attempt + 1, len(BACKOFF_DELAYS) + 1)
            except Exception as exc:
                last_error = exc
                log.exception("Claude classifier error (attempt %d)", attempt + 1)
                break

        log.error("Claude classifier failed after retries: %s", last_error)
        return ClassificationResult(ActionType.keep, {}, f"AI failed: {last_error}")

    async def list_models(self) -> list[str]:
        return [
            "claude-opus-4-7",
            "claude-sonnet-4-6",
            "claude-haiku-4-5-20251001",
            "claude-opus-4-5",
            "claude-sonnet-4-5",
            "claude-haiku-4-5",
        ]

    async def test_connection(self) -> tuple[bool, str]:
        if not self.api_key:
            return False, "No API key configured"
        try:
            await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True, "Connection successful"
        except Exception as exc:
            return False, str(exc)
