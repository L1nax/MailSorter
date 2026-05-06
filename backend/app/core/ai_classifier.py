from __future__ import annotations
import asyncio
import logging
from typing import TYPE_CHECKING
import anthropic
from ..models.rule import ActionType

if TYPE_CHECKING:
    from .imap_worker import RawMail

log = logging.getLogger(__name__)

BACKOFF_DELAYS = [1, 2, 4]


class ClassificationResult:
    __slots__ = ("action", "params", "warning")

    def __init__(self, action: ActionType, params: dict, warning: str = "") -> None:
        self.action = action
        self.params = params
        self.warning = warning


class AIClassifier:
    def __init__(self, api_key: str, model: str, system_prompt: str, folders: list[str]) -> None:
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.system_prompt = system_prompt
        self.folders = folders

    async def classify(self, mail: "RawMail") -> ClassificationResult:
        user_msg = self._build_prompt(mail)
        last_error: Exception | None = None

        for attempt, delay in enumerate([0] + BACKOFF_DELAYS):
            if delay:
                await asyncio.sleep(delay)
            try:
                response = await asyncio.to_thread(
                    self.client.messages.create,
                    model=self.model,
                    max_tokens=64,
                    system=self.system_prompt,
                    messages=[{"role": "user", "content": user_msg}],
                )
                folder = response.content[0].text.strip()
                if folder in self.folders:
                    return ClassificationResult(action=ActionType.move, params={"folder": folder})
                log.warning("AI returned unknown folder %r, keeping mail", folder)
                return ClassificationResult(
                    action=ActionType.keep,
                    params={},
                    warning=f"AI returned unknown folder: {folder}",
                )
            except anthropic.RateLimitError as exc:
                last_error = exc
                log.warning("AI rate limit (attempt %d/%d)", attempt + 1, len(BACKOFF_DELAYS) + 1)
            except Exception as exc:
                last_error = exc
                log.exception("AI classifier error (attempt %d)", attempt + 1)
                break

        log.error("AI classifier failed after retries: %s", last_error)
        return ClassificationResult(
            action=ActionType.keep,
            params={},
            warning=f"AI failed: {last_error}",
        )

    def _build_prompt(self, mail: "RawMail") -> str:
        folders_str = "\n".join(f"- {f}" for f in self.folders)
        return (
            f"Available folders:\n{folders_str}\n\n"
            f"From: {mail.from_address}\n"
            f"Subject: {mail.subject}\n\n"
            f"{mail.body[:4000]}"
        )


async def test_ai_connection(api_key: str, model: str) -> tuple[bool, str]:
    if not api_key:
        return False, "No API key configured"
    try:
        client = anthropic.Anthropic(api_key=api_key)
        await asyncio.to_thread(
            client.messages.create,
            model=model,
            max_tokens=10,
            messages=[{"role": "user", "content": "ping"}],
        )
        return True, "Connection successful"
    except Exception as exc:
        return False, str(exc)
