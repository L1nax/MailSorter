from __future__ import annotations
import re
from dataclasses import dataclass, field
from email.utils import parseaddr
from ..models.rule import Rule, ConditionType


@dataclass
class MailData:
    from_address: str = ""
    subject: str = ""
    to_address: str = ""
    body: str = ""
    has_attachment: bool = False
    attachment_types: list[str] = field(default_factory=list)

    @property
    def from_domain(self) -> str:
        _, addr = parseaddr(self.from_address)
        parts = addr.split("@")
        return parts[-1].lower() if len(parts) == 2 else ""


class RuleEngine:
    def __init__(self, rules: list[Rule]) -> None:
        self.rules = rules

    def evaluate(self, mail: MailData) -> Rule | None:
        for rule in self.rules:
            if not rule.enabled:
                continue
            if self._matches(rule, mail):
                return rule
        return None

    def _matches(self, rule: Rule, mail: MailData) -> bool:
        for condition in rule.conditions:
            ctype = condition.get("type")
            value = condition.get("value", "")
            if not self._check_condition(ctype, value, mail):
                return False
        return True

    def _check_condition(self, ctype: str, value: str, mail: MailData) -> bool:
        match ctype:
            case ConditionType.from_domain:
                return mail.from_domain == value.lower()
            case ConditionType.from_address:
                _, addr = parseaddr(mail.from_address)
                return addr.lower() == value.lower()
            case ConditionType.subject_contains:
                return value.lower() in mail.subject.lower()
            case ConditionType.subject_regex:
                return bool(re.search(value, mail.subject, re.IGNORECASE))
            case ConditionType.has_attachment:
                expected = str(value).lower() not in ("false", "0", "no")
                return mail.has_attachment == expected
            case ConditionType.attachment_type:
                return value.lower() in [t.lower() for t in mail.attachment_types]
            case ConditionType.body_contains:
                return value.lower() in mail.body.lower()
            case ConditionType.to_address:
                _, addr = parseaddr(mail.to_address)
                return addr.lower() == value.lower()
            case _:
                return False
