from __future__ import annotations
from typing import TYPE_CHECKING
from .base import AIProvider
from .claude import ClaudeProvider
from .openai import OpenAIProvider
from .gemini import GeminiProvider

if TYPE_CHECKING:
    from sqlmodel import Session

DEFAULT_MODELS: dict[str, str] = {
    "claude": "claude-sonnet-4-6",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.0-flash",
    "ollama": "llama3.2",
}


def make_provider(provider: str, api_key: str, model: str, base_url: str) -> AIProvider:
    model = model or DEFAULT_MODELS.get(provider, "")
    match provider:
        case "openai":
            return OpenAIProvider(api_key, model, base_url or "https://api.openai.com/v1")
        case "ollama":
            return OpenAIProvider("ollama", model, base_url or "http://localhost:11434/v1")
        case "gemini":
            return GeminiProvider(api_key, model)
        case _:  # "claude" and unknown providers
            return ClaudeProvider(api_key, model or DEFAULT_MODELS["claude"])


def get_provider(session: "Session") -> AIProvider:
    from ...config import get_setting
    provider = get_setting(session, "ai_provider") or "claude"
    api_key = get_setting(session, "ai_api_key")
    model = get_setting(session, "ai_model")
    base_url = get_setting(session, "ai_base_url")
    return make_provider(provider, api_key, model, base_url)
