from __future__ import annotations
import asyncio
import logging
from typing import TYPE_CHECKING
import google.generativeai as genai
from .base import AIProvider, ClassificationResult
from ...models.rule import ActionType

if TYPE_CHECKING:
    from ..imap_worker import RawMail

log = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model or "gemini-2.0-flash"
        if api_key:
            genai.configure(api_key=api_key)
        self._model: genai.GenerativeModel | None = None

    def _get_model(self, system_prompt: str) -> genai.GenerativeModel:
        return genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt,
        )

    async def classify(
        self, mail: "RawMail", folders: list[str], prompt: str
    ) -> ClassificationResult:
        if not self.api_key:
            return ClassificationResult(ActionType.keep, {}, "AI not configured: API key missing")

        user_msg = self._build_prompt(mail, folders)
        try:
            model = self._model or self._get_model(prompt)
            response = await asyncio.to_thread(model.generate_content, user_msg)
            return self._parse_response(response.text, folders)
        except Exception as exc:
            log.exception("Gemini classifier error")
            return ClassificationResult(ActionType.keep, {}, f"AI failed: {exc}")

    async def list_models(self) -> list[str]:
        fallback = ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.5-flash-8b"]
        if not self.api_key:
            return fallback
        try:
            models = await asyncio.to_thread(genai.list_models)
            ids = [
                m.name.removeprefix("models/")
                for m in models
                if "generateContent" in (m.supported_generation_methods or [])
            ]
            return sorted(ids) or fallback
        except Exception:
            return fallback

    async def test_connection(self) -> tuple[bool, str]:
        if not self.api_key:
            return False, "No API key configured"
        try:
            model = genai.GenerativeModel(model_name=self.model)
            await asyncio.to_thread(model.generate_content, "ping")
            return True, "Connection successful"
        except Exception as exc:
            return False, str(exc)
