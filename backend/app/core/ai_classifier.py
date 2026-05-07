"""Thin compatibility shim – provider logic lebt in app.core.providers.*"""
from __future__ import annotations
from .providers.base import ClassificationResult  # noqa: F401 – re-export für alte Imports
from .providers import get_provider, make_provider


class AIClassifier:
    """Kompatibilität-Wrapper für alten Code; delegiert an ClaudeProvider."""
    def __init__(self, api_key: str, model: str, system_prompt: str, folders: list[str]) -> None:
        self.provider = make_provider("claude", api_key, model, "")
        self.system_prompt = system_prompt
        self.folders = folders

    async def classify(self, mail) -> ClassificationResult:
        """Delegiert an provider.classify()."""
        return await self.provider.classify(mail, self.folders, self.system_prompt)


async def test_ai_connection(api_key: str, model: str) -> tuple[bool, str]:
    """Für Rückwärtskompatibilität; neuer Code nutzt provider.test_connection()."""
    provider = make_provider("claude", api_key, model, "")
    return await provider.test_connection()
