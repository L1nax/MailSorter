from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlmodel import Session
from ..db import get_session
from ..models import SettingsRead, SettingsUpdate
from ..config import get_all_settings, get_setting, set_setting

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsRead)
def read_settings(session: Session = Depends(get_session)):
    return get_all_settings(session)


@router.put("", response_model=SettingsRead)
def update_settings(body: SettingsUpdate, session: Session = Depends(get_session)):
    data = body.model_dump(exclude_none=True)
    for key, value in data.items():
        if isinstance(value, bool):
            set_setting(session, key, "true" if value else "false")
        else:
            set_setting(session, key, str(value))
    return get_all_settings(session)


@router.post("/test-imap")
async def test_imap(session: Session = Depends(get_session)):
    from ..core.imap_worker import test_imap_connection
    host = get_setting(session, "imap_host")
    port = int(get_setting(session, "imap_port"))
    user = get_setting(session, "imap_user")
    password = get_setting(session, "imap_password")
    tls = get_setting(session, "imap_tls") == "true"
    ok, msg = test_imap_connection(host, port, user, password, tls)
    return {"ok": ok, "message": msg}


@router.post("/test-paperless")
async def test_paperless(session: Session = Depends(get_session)):
    from ..services.paperless import test_paperless_connection
    url = get_setting(session, "paperless_url")
    token = get_setting(session, "paperless_token")
    ok, msg = await test_paperless_connection(url, token)
    return {"ok": ok, "message": msg}


@router.post("/test-ai")
async def test_ai(session: Session = Depends(get_session)):
    from ..core.ai_classifier import test_ai_connection
    api_key = get_setting(session, "ai_api_key")
    model = get_setting(session, "ai_model")
    ok, msg = await test_ai_connection(api_key, model)
    return {"ok": ok, "message": msg}
