from __future__ import annotations
import pytest
from app.core.rule_engine import RuleEngine, MailData
from app.models.rule import Rule, ActionType, ConditionType


def make_rule(conditions: list[dict], action: ActionType = ActionType.move, params: dict | None = None, priority: int = 0) -> Rule:
    return Rule(
        name="test",
        priority=priority,
        enabled=True,
        conditions=conditions,
        action=action,
        action_params=params or {"folder": "Test"},
    )


class TestFromDomain:
    def test_match(self):
        rule = make_rule([{"type": "from_domain", "value": "amazon.de"}])
        mail = MailData(from_address="order@amazon.de")
        assert RuleEngine([rule]).evaluate(mail) is rule

    def test_no_match(self):
        rule = make_rule([{"type": "from_domain", "value": "amazon.de"}])
        mail = MailData(from_address="order@amazon.com")
        assert RuleEngine([rule]).evaluate(mail) is None


class TestFromAddress:
    def test_match_case_insensitive(self):
        rule = make_rule([{"type": "from_address", "value": "User@Example.com"}])
        mail = MailData(from_address="user@example.com")
        assert RuleEngine([rule]).evaluate(mail) is rule


class TestSubjectContains:
    def test_match(self):
        rule = make_rule([{"type": "subject_contains", "value": "Rechnung"}])
        mail = MailData(subject="Ihre Rechnung Nr. 123")
        assert RuleEngine([rule]).evaluate(mail) is rule

    def test_case_insensitive(self):
        rule = make_rule([{"type": "subject_contains", "value": "rechnung"}])
        mail = MailData(subject="Ihre RECHNUNG")
        assert RuleEngine([rule]).evaluate(mail) is rule


class TestSubjectRegex:
    def test_match(self):
        rule = make_rule([{"type": "subject_regex", "value": r"Rechnung\s+#\d+"}])
        mail = MailData(subject="Rechnung #42")
        assert RuleEngine([rule]).evaluate(mail) is rule

    def test_no_match(self):
        rule = make_rule([{"type": "subject_regex", "value": r"^\d{4}$"}])
        mail = MailData(subject="hello")
        assert RuleEngine([rule]).evaluate(mail) is None


class TestHasAttachment:
    def test_true(self):
        rule = make_rule([{"type": "has_attachment", "value": "true"}])
        mail = MailData(has_attachment=True)
        assert RuleEngine([rule]).evaluate(mail) is rule

    def test_false(self):
        rule = make_rule([{"type": "has_attachment", "value": "true"}])
        mail = MailData(has_attachment=False)
        assert RuleEngine([rule]).evaluate(mail) is None


class TestAttachmentType:
    def test_match(self):
        rule = make_rule([{"type": "attachment_type", "value": "application/pdf"}])
        mail = MailData(has_attachment=True, attachment_types=["application/pdf"])
        assert RuleEngine([rule]).evaluate(mail) is rule


class TestBodyContains:
    def test_match(self):
        rule = make_rule([{"type": "body_contains", "value": "Kündigung"}])
        mail = MailData(body="Hiermit beantrage ich die Kündigung meines Vertrages.")
        assert RuleEngine([rule]).evaluate(mail) is rule


class TestMultipleConditionsAnd:
    def test_all_match(self):
        rule = make_rule([
            {"type": "from_domain", "value": "paypal.com"},
            {"type": "subject_contains", "value": "Zahlung"},
        ])
        mail = MailData(from_address="noreply@paypal.com", subject="Zahlungseingang bestätigt")
        assert RuleEngine([rule]).evaluate(mail) is rule

    def test_partial_match(self):
        rule = make_rule([
            {"type": "from_domain", "value": "paypal.com"},
            {"type": "subject_contains", "value": "Zahlung"},
        ])
        mail = MailData(from_address="noreply@paypal.com", subject="Konto gesperrt")
        assert RuleEngine([rule]).evaluate(mail) is None


class TestFirstMatch:
    def test_priority_order(self):
        rule1 = make_rule([{"type": "from_domain", "value": "example.com"}], priority=0)
        rule2 = make_rule([{"type": "from_domain", "value": "example.com"}], priority=1)
        mail = MailData(from_address="a@example.com")
        assert RuleEngine([rule1, rule2]).evaluate(mail) is rule1

    def test_disabled_rule_skipped(self):
        rule1 = make_rule([{"type": "from_domain", "value": "example.com"}], priority=0)
        rule1.enabled = False
        rule2 = make_rule([{"type": "from_domain", "value": "example.com"}], priority=1)
        mail = MailData(from_address="a@example.com")
        assert RuleEngine([rule1, rule2]).evaluate(mail) is rule2
