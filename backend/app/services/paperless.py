from __future__ import annotations
import asyncio
import logging
from typing import TYPE_CHECKING
import httpx

if TYPE_CHECKING:
    from ..core.imap_worker import RawMail

log = logging.getLogger(__name__)


async def test_paperless_connection(url: str, token: str) -> tuple[bool, str]:
    if not url or not token:
        return False, "Paperless not configured"
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            r = await client.get(f"{url.rstrip('/')}/api/", headers={"Authorization": f"Token {token}"}, timeout=10)
            r.raise_for_status()
        return True, "Connection successful"
    except Exception as exc:
        return False, str(exc)


async def upload_pdf(url: str, token: str, filename: str, data: bytes, mail: "RawMail") -> tuple[bool, str]:
    if not url or not token:
        return False, "Paperless not configured"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{url.rstrip('/')}/api/documents/post_document/",
                headers={"Authorization": f"Token {token}"},
                files={"document": (filename, data, "application/pdf")},
                data={"title": mail.subject, "correspondent": mail.from_address},
                timeout=60,
            )
            r.raise_for_status()
        return True, ""
    except Exception as exc:
        log.exception("Paperless upload failed")
        return False, str(exc)


def upload_pdf_sync(url: str, token: str, filename: str, data: bytes, mail: "RawMail") -> tuple[bool, str]:
    return asyncio.run(upload_pdf(url, token, filename, data, mail))
