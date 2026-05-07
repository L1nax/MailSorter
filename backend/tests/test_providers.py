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
