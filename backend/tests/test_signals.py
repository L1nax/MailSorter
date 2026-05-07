# backend/tests/test_signals.py
from __future__ import annotations
import pytest
from app.core.providers.claude import ClaudeProvider
from app.core.providers.base import ClassificationResult
from app.models.rule import ActionType


def _provider() -> ClaudeProvider:
    return ClaudeProvider(api_key="test", model="claude-sonnet-4-6")


class TestSignalsParsing:
    def test_no_signals_line_returns_empty(self):
        p = _provider()
        result = p._parse_response("move:Rechnungen", ["Rechnungen"])
        assert result.action == ActionType.move
        assert result.signals == []

    def test_signals_line_parsed(self):
        p = _provider()
        result = p._parse_response(
            "move:Rechnungen\nsignals: from_domain:amazon.de, subject_contains:Rechnung",
            ["Rechnungen"],
        )
        assert result.action == ActionType.move
        assert result.params == {"folder": "Rechnungen"}
        assert {"type": "from_domain", "value": "amazon.de"} in result.signals
        assert {"type": "subject_contains", "value": "Rechnung"} in result.signals

    def test_unknown_signal_type_ignored(self):
        p = _provider()
        result = p._parse_response(
            "move:Spam\nsignals: unknown_type:foo, from_address:test@example.com",
            ["Spam"],
        )
        assert len(result.signals) == 1
        assert result.signals[0] == {"type": "from_address", "value": "test@example.com"}

    def test_signals_with_keep_action(self):
        p = _provider()
        result = p._parse_response(
            "keep\nsignals: from_domain:newsletter.com",
            [],
        )
        assert result.action == ActionType.keep
        assert result.signals == [{"type": "from_domain", "value": "newsletter.com"}]

    def test_signals_field_on_classification_result(self):
        r = ClassificationResult(ActionType.keep, {}, signals=[{"type": "from_domain", "value": "test.de"}])
        assert r.signals == [{"type": "from_domain", "value": "test.de"}]

    def test_classification_result_default_signals_empty(self):
        r = ClassificationResult(ActionType.keep, {})
        assert r.signals == []
