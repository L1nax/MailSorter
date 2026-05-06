from __future__ import annotations
import asyncio
import logging
from typing import TYPE_CHECKING
import httpx

if TYPE_CHECKING:
    from ..core.imap_worker import RawMail

log = logging.getLogger(__name__)


async def fire_webhook(url: str, mail: "RawMail") -> None:
    if not url:
        return
    payload = {
        "message_id": mail.message_id,
        "from": mail.from_address,
        "subject": mail.subject,
        "has_attachment": mail.has_attachment,
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, json=payload, timeout=10)
    except Exception as exc:
        log.warning("Webhook failed for %s: %s", url, exc)


def fire_webhook_sync(url: str, mail: "RawMail") -> None:
    asyncio.run(fire_webhook(url, mail))
