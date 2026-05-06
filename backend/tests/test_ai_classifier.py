from __future__ import annotations
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.core.ai_classifier import AIClassifier
from app.core.imap_worker import RawMail
from app.models.rule import ActionType


def _make_mail(subject: str = "Test", body: str = "Hello") -> RawMail:
    return RawMail(
        uid=1,
        message_id="<test@test>",
        from_address="test@example.com",
        subject=subject,
        to_address="me@example.com",
        body=body,
        has_attachment=False,
        attachment_types=[],
    )


def _make_classifier(folders: list[str] | None = None) -> AIClassifier:
    return AIClassifier(
        api_key="test-key",
        model="claude-sonnet-4-20250514",
        system_prompt="Classify.",
        folders=folders or ["INBOX.Work", "INBOX.Shopping", "INBOX.News"],
    )


class TestClassify:
    def test_known_folder_returned(self):
        classifier = _make_classifier()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="INBOX.Work")]

        with patch.object(classifier.client.messages, "create", return_value=mock_response):
            result = asyncio.run(classifier.classify(_make_mail()))

        assert result.action == ActionType.move
        assert result.params == {"folder": "INBOX.Work"}
        assert result.warning == ""

    def test_unknown_folder_keeps_mail(self):
        classifier = _make_classifier()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="INBOX.Unknown")]

        with patch.object(classifier.client.messages, "create", return_value=mock_response):
            result = asyncio.run(classifier.classify(_make_mail()))

        assert result.action == ActionType.keep
        assert "INBOX.Unknown" in result.warning

    def test_rate_limit_retries_then_keeps(self):
        import anthropic
        classifier = _make_classifier()

        with patch.object(
            classifier.client.messages,
            "create",
            side_effect=anthropic.RateLimitError.__new__(anthropic.RateLimitError),
        ):
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = asyncio.run(classifier.classify(_make_mail()))

        assert result.action == ActionType.keep
        assert result.warning != ""
