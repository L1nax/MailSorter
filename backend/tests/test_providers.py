from __future__ import annotations
import asyncio
from app.core.providers.base import AIProvider, ClassificationResult
from app.models.rule import ActionType


class _DummyProvider(AIProvider):
    async def classify(self, mail, folders, prompt):
        return ClassificationResult(action=ActionType.keep, params={})

    async def test_connection(self):
        return True, "ok"


def test_classification_result_defaults():
    r = ClassificationResult(action=ActionType.move, params={"folder": "INBOX.Work"})
    assert r.action == ActionType.move
    assert r.params == {"folder": "INBOX.Work"}
    assert r.warning == ""


def test_build_prompt_contains_mail_fields():
    from app.core.imap_worker import RawMail
    mail = RawMail(
        uid=1, message_id="<t>", from_address="a@b.com",
        subject="Rechnung", to_address="me@c.com",
        body="Hallo Welt", has_attachment=False, attachment_types=[],
    )
    provider = _DummyProvider()
    prompt = provider._build_prompt(mail, ["INBOX.Rechnungen"])
    assert "a@b.com" in prompt
    assert "Rechnung" in prompt
    assert "INBOX.Rechnungen" in prompt


import anthropic
from unittest.mock import MagicMock, patch
from app.core.providers.claude import ClaudeProvider
from app.core.imap_worker import RawMail


def _mail(subject="Test", body="Hello"):
    return RawMail(uid=1, message_id="<t>", from_address="a@b.com",
                   subject=subject, to_address="me@c.com", body=body,
                   has_attachment=False, attachment_types=[])


class TestClaudeProvider:
    def test_known_folder(self):
        provider = ClaudeProvider(api_key="key", model="claude-sonnet-4-6")
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="INBOX.Work")]

        with patch.object(provider.client.messages, "create", return_value=mock_resp):
            result = asyncio.run(provider.classify(_mail(), ["INBOX.Work"], "Classify."))

        assert result.action == ActionType.move
        assert result.params["folder"] == "INBOX.Work"
        assert result.warning == ""

    def test_unknown_folder_keeps(self):
        provider = ClaudeProvider(api_key="key", model="claude-sonnet-4-6")
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text="INBOX.Unknown")]

        with patch.object(provider.client.messages, "create", return_value=mock_resp):
            result = asyncio.run(provider.classify(_mail(), ["INBOX.Work"], "Classify."))

        assert result.action == ActionType.keep
        assert "INBOX.Unknown" in result.warning

    def test_no_api_key_returns_keep(self):
        provider = ClaudeProvider(api_key="", model="claude-sonnet-4-6")
        result = asyncio.run(provider.classify(_mail(), ["INBOX.Work"], "Classify."))
        assert result.action == ActionType.keep
        assert "not configured" in result.warning

    def test_rate_limit_retries(self):
        provider = ClaudeProvider(api_key="key", model="claude-sonnet-4-6")
        from unittest.mock import AsyncMock
        with patch.object(
            provider.client.messages, "create",
            side_effect=anthropic.RateLimitError.__new__(anthropic.RateLimitError),
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = asyncio.run(provider.classify(_mail(), ["INBOX.Work"], "Classify."))
        assert result.action == ActionType.keep
        assert result.warning != ""


from unittest.mock import AsyncMock
from app.core.providers.openai import OpenAIProvider


class TestOpenAIProvider:
    def test_known_folder(self):
        provider = OpenAIProvider(
            api_key="key", model="gpt-4o-mini",
            base_url="https://api.openai.com/v1"
        )
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "INBOX.Work"

        with patch.object(
            provider.client.chat.completions, "create",
            new_callable=AsyncMock, return_value=mock_resp
        ):
            result = asyncio.run(provider.classify(_mail(), ["INBOX.Work"], "Classify."))

        assert result.action == ActionType.move
        assert result.params["folder"] == "INBOX.Work"

    def test_unknown_folder_keeps(self):
        provider = OpenAIProvider(api_key="key", model="gpt-4o-mini",
                                   base_url="https://api.openai.com/v1")
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "INBOX.Unknown"

        with patch.object(
            provider.client.chat.completions, "create",
            new_callable=AsyncMock, return_value=mock_resp
        ):
            result = asyncio.run(provider.classify(_mail(), ["INBOX.Work"], "Classify."))

        assert result.action == ActionType.keep
        assert "INBOX.Unknown" in result.warning

    def test_no_api_key_returns_keep(self):
        provider = OpenAIProvider(api_key="", model="gpt-4o-mini",
                                   base_url="https://api.openai.com/v1")
        result = asyncio.run(provider.classify(_mail(), ["INBOX.Work"], "Classify."))
        assert result.action == ActionType.keep
        assert "not configured" in result.warning


from unittest.mock import MagicMock, patch
from app.core.providers.gemini import GeminiProvider


class TestGeminiProvider:
    def test_known_folder(self):
        provider = GeminiProvider(api_key="key", model="gemini-2.0-flash")
        mock_resp = MagicMock()
        mock_resp.text = "INBOX.Work"

        with patch("google.generativeai.GenerativeModel") as MockModel:
            MockModel.return_value.generate_content.return_value = mock_resp
            with patch("google.generativeai.configure"):
                provider._model = MockModel.return_value
                result = asyncio.run(provider.classify(_mail(), ["INBOX.Work"], "Classify."))

        assert result.action == ActionType.move
        assert result.params["folder"] == "INBOX.Work"

    def test_no_api_key_returns_keep(self):
        provider = GeminiProvider(api_key="", model="gemini-2.0-flash")
        result = asyncio.run(provider.classify(_mail(), ["INBOX.Work"], "Classify."))
        assert result.action == ActionType.keep
        assert "not configured" in result.warning
