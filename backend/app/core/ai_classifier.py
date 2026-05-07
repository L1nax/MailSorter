"""Thin compatibility shim – provider logic lebt in app.core.providers.*"""
from __future__ import annotations
from .providers.base import ClassificationResult  # noqa: F401 – re-export für alte Imports
from .providers import get_provider, make_provider


async def test_ai_connection(api_key: str, model: str) -> tuple[bool, str]:
    """Für Rückwärtskompatibilität; neuer Code nutzt provider.test_connection()."""
    provider = make_provider("claude", api_key, model, "")
    return await provider.test_connection()
