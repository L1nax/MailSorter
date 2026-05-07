from __future__ import annotations
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.core.providers.claude import ClaudeProvider
from app.core.providers.base import ClassificationResult
from app.core.imap_worker import RawMail
from app.models.rule import ActionType


def _make_mail(subject: str = "Test", body: str = "Hello") -> RawMail:
    return RawMail(
        uid=1, message_id="<test@test>", from_address="test@example.com",
        subject=subject, to_address="me@example.com", body=body,
        has_attachment=False, attachment_types=[],
    )


class TestClaudeProviderLegacy:
    """Smoke-Tests, die vorher in test_ai_classifier.py lagen."""

    def test_known_folder_returned(self):
        provider = ClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="INBOX.Work")]

        with patch.object(provider.client.messages, "create", return_value=mock_response):
            result = asyncio.run(
                provider.classify(_make_mail(), ["INBOX.Work", "INBOX.Shopping"], "Classify.")
            )

        assert result.action == ActionType.move
        assert result.params == {"folder": "INBOX.Work"}
        assert result.warning == ""

    def test_unknown_folder_keeps_mail(self):
        provider = ClaudeProvider(api_key="test-key", model="claude-sonnet-4-6")
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="INBOX.Unknown")]

        with patch.object(provider.client.messages, "create", return_value=mock_response):
            result = asyncio.run(
                provider.classify(_make_mail(), ["INBOX.Work"], "Classify.")
            )

        assert result.action == ActionType.keep
        assert "INBOX.Unknown" in result.warning
