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
            return self._parse_response(response.choices[0].message.content, folders)
        except Exception as exc:
            log.exception("OpenAI classifier error")
            return ClassificationResult(ActionType.keep, {}, f"AI failed: {exc}")

    async def list_models(self) -> list[str]:
        is_ollama = self.api_key == "ollama"
        fallback = (
            ["llama3.2", "llama3.1", "mistral", "qwen2.5", "phi4", "gemma3", "deepseek-r2"]
            if is_ollama
            else ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo", "o1", "o1-mini", "o3", "o3-mini", "o4-mini"]
        )
        try:
            response = await self.client.models.list()
            ids = [m.id for m in response.data]
            if is_ollama:
                return sorted(ids)
            chat = [i for i in ids if i.startswith("gpt-") or (len(i) >= 2 and i[0] == "o" and i[1].isdigit())]
            return sorted(chat) or fallback
        except Exception:
            return fallback

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
