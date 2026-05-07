from __future__ import annotations
import pytest
from sqlmodel import Session, create_engine, SQLModel, select
from app.models.rule import Rule, ActionType
from app.models.account import MailAccount
from app.models.settings import Settings
from app.models.suggestion import AISignal, RuleSuggestion, SuggestionStatus
from app.core.backup import export_data, import_data


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    from app import models  # noqa
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def populated(session):
    session.add(Rule(
        name="Test-Regel", priority=1, enabled=True,
        conditions=[{"type": "from_domain", "value": "test.de"}],
        action=ActionType.move, action_params={"folder": "Test"},
    ))
    session.add(MailAccount(
        name="Test-Account", imap_host="imap.test.com",
        imap_user="user@test.com", imap_password="secret",
    ))
    session.add(Settings(key="paperless_url", value="http://paperless"))
    session.add(AISignal(
        signal_type="from_domain", signal_value="test.de",
        action="move", target="Test",
    ))
    session.commit()
    return session


class TestExportData:
    def test_exports_all_sections(self, populated):
        data = export_data(populated, ["rules", "accounts", "settings", "suggestions"])
        assert data["version"] == 1
        assert set(data["sections"]) == {"rules", "accounts", "settings", "suggestions"}
        assert len(data["rules"]) == 1
        assert len(data["accounts"]) == 1
        assert "paperless_url" in data["settings"]
        assert len(data["suggestions"]["ai_signals"]) == 1
        assert "exported_at" in data

    def test_exports_only_requested_sections(self, populated):
        data = export_data(populated, ["rules"])
        assert "rules" in data
        assert "accounts" not in data
        assert "settings" not in data
        assert "suggestions" not in data
        assert data["sections"] == ["rules"]

    def test_rule_fields_present(self, populated):
        data = export_data(populated, ["rules"])
        rule = data["rules"][0]
        assert rule["name"] == "Test-Regel"
        assert rule["action"] == "move"
        assert rule["action_params"] == {"folder": "Test"}
        assert "id" in rule
        assert "created_at" in rule

    def test_account_password_in_plaintext(self, populated):
        data = export_data(populated, ["accounts"])
        assert data["accounts"][0]["imap_password"] == "secret"

    def test_empty_db_exports_empty_lists(self, session):
        data = export_data(session, ["rules", "accounts"])
        assert data["rules"] == []
        assert data["accounts"] == []


class TestImportMerge:
    def test_merge_adds_new_rule(self, session):
        data = {
            "version": 1,
            "sections": ["rules"],
            "rules": [{
                "id": "rule-1", "name": "Neue Regel", "priority": 1,
                "enabled": True, "conditions": [], "action": "move",
                "action_params": {"folder": "X"}, "account_id": None,
                "created_at": "2026-01-01T00:00:00",
            }],
        }
        counts = import_data(session, data, "merge")
        assert counts["rules"] == 1
        assert session.get(Rule, "rule-1") is not None

    def test_merge_skips_existing_rule(self, populated):
        existing = populated.exec(select(Rule)).first()
        data = {
            "version": 1,
            "sections": ["rules"],
            "rules": [{
                "id": existing.id, "name": "Geändert", "priority": 99,
                "enabled": False, "conditions": [], "action": "trash",
                "action_params": {}, "account_id": None,
                "created_at": existing.created_at.isoformat(),
            }],
        }
        counts = import_data(populated, data, "merge")
        assert counts["rules"] == 0
        assert populated.get(Rule, existing.id).name == "Test-Regel"

    def test_merge_settings_skips_existing_key(self, populated):
        data = {
            "version": 1,
            "sections": ["settings"],
            "settings": {"paperless_url": "http://other", "new_key": "new_val"},
        }
        counts = import_data(populated, data, "merge")
        assert counts["settings"] == 1
        assert populated.get(Settings, "paperless_url").value == "http://paperless"
        assert populated.get(Settings, "new_key").value == "new_val"


class TestImportReplace:
    def test_replace_deletes_existing_rules(self, populated):
        data = {
            "version": 1,
            "sections": ["rules"],
            "rules": [{
                "id": "new-id", "name": "Ersatz", "priority": 1,
                "enabled": True, "conditions": [], "action": "keep",
                "action_params": {}, "account_id": None,
                "created_at": "2026-01-01T00:00:00",
            }],
        }
        import_data(populated, data, "replace")
        all_rules = populated.exec(select(Rule)).all()
        assert len(all_rules) == 1
        assert all_rules[0].name == "Ersatz"

    def test_replace_does_not_touch_other_sections(self, populated):
        data = {
            "version": 1,
            "sections": ["rules"],
            "rules": [],
        }
        import_data(populated, data, "replace")
        accounts = populated.exec(select(MailAccount)).all()
        assert len(accounts) == 1

    def test_only_imports_declared_sections(self, session):
        data = {
            "version": 1,
            "sections": ["rules"],
            "rules": [],
            "accounts": [{"id": "acc-1", "name": "Phantom"}],
        }
        counts = import_data(session, data, "replace")
        assert "accounts" not in counts
