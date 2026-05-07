# backend/tests/test_suggestion_service.py
from __future__ import annotations
import pytest
from datetime import datetime, timedelta
from sqlmodel import Session, create_engine, SQLModel, select
from app.models.suggestion import AISignal, RuleSuggestion, SuggestionStatus
from app.models.settings import Settings
from app.core.suggestion_service import process_signals


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    from app import models  # noqa
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        s.add(Settings(key="suggestion_threshold", value="3"))
        s.add(Settings(key="suggestion_snooze_days", value="30"))
        s.commit()
    with Session(engine) as s:
        yield s


def _signals(typ: str = "from_domain", val: str = "amazon.de") -> list[dict]:
    return [{"type": typ, "value": val}]


class TestProcessSignals:
    def test_upserts_signal_count(self, session):
        process_signals(_signals(), "move", "Rechnungen", None, session)
        sig = session.exec(select(AISignal)).first()
        assert sig is not None
        assert sig.count == 1
        assert sig.signal_type == "from_domain"
        assert sig.signal_value == "amazon.de"

    def test_increments_on_second_call(self, session):
        process_signals(_signals(), "move", "Rechnungen", None, session)
        process_signals(_signals(), "move", "Rechnungen", None, session)
        sig = session.exec(select(AISignal)).first()
        assert sig.count == 2

    def test_no_suggestion_below_threshold(self, session):
        process_signals(_signals(), "move", "Rechnungen", None, session)
        process_signals(_signals(), "move", "Rechnungen", None, session)
        suggestions = session.exec(select(RuleSuggestion)).all()
        assert len(suggestions) == 0

    def test_creates_suggestion_at_threshold(self, session):
        for _ in range(3):
            process_signals(_signals(), "move", "Rechnungen", None, session)
        suggestions = session.exec(select(RuleSuggestion)).all()
        assert len(suggestions) == 1
        s = suggestions[0]
        assert s.status == SuggestionStatus.pending
        assert s.signal_type == "from_domain"
        assert s.signal_value == "amazon.de"
        assert s.suggested_rule_name == "[KI] amazon.de → Rechnungen"
        assert s.suggested_conditions == [
            {"type": "from_domain", "value": "amazon.de", "operator": "contains"}
        ]

    def test_no_duplicate_suggestion_when_pending(self, session):
        for _ in range(6):
            process_signals(_signals(), "move", "Rechnungen", None, session)
        suggestions = session.exec(select(RuleSuggestion)).all()
        assert len(suggestions) == 1

    def test_dismissed_blocks_new_suggestion(self, session):
        for _ in range(3):
            process_signals(_signals(), "move", "Rechnungen", None, session)
        suggestion = session.exec(select(RuleSuggestion)).first()
        suggestion.status = SuggestionStatus.dismissed
        session.add(suggestion)
        session.commit()
        for _ in range(3):
            process_signals(_signals(), "move", "Rechnungen", None, session)
        suggestions = session.exec(select(RuleSuggestion)).all()
        assert len(suggestions) == 1
        assert suggestions[0].status == SuggestionStatus.dismissed

    def test_expired_snooze_reactivates(self, session):
        for _ in range(3):
            process_signals(_signals(), "move", "Rechnungen", None, session)
        suggestion = session.exec(select(RuleSuggestion)).first()
        suggestion.status = SuggestionStatus.snoozed
        suggestion.snooze_until = datetime.utcnow() - timedelta(days=1)
        session.add(suggestion)
        session.commit()
        process_signals(_signals(), "move", "Rechnungen", None, session)
        refreshed = session.exec(select(RuleSuggestion)).first()
        assert refreshed.status == SuggestionStatus.pending
        assert refreshed.snooze_until is None

    def test_active_snooze_blocks(self, session):
        for _ in range(3):
            process_signals(_signals(), "move", "Rechnungen", None, session)
        suggestion = session.exec(select(RuleSuggestion)).first()
        suggestion.status = SuggestionStatus.snoozed
        suggestion.snooze_until = datetime.utcnow() + timedelta(days=10)
        session.add(suggestion)
        session.commit()
        process_signals(_signals(), "move", "Rechnungen", None, session)
        refreshed = session.exec(select(RuleSuggestion)).first()
        assert refreshed.status == SuggestionStatus.snoozed
