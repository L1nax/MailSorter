from __future__ import annotations
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session
from ..db import get_session
from ..models import SettingsRead, SettingsUpdate
from ..config import get_all_settings, get_setting, set_setting, MASKED_KEYS

router = APIRouter(prefix="/api/settings", tags=["settings"])

_SENTINEL = "***"


class AiTestRequest(BaseModel):
    ai_provider: str = "claude"
    ai_api_key: str = ""
    ai_model: str = ""
    ai_base_url: str = ""


class PaperlessTestRequest(BaseModel):
    paperless_url: str = ""
    paperless_token: str = ""


@router.get("", response_model=SettingsRead)
def read_settings(session: Session = Depends(get_session)):
    return get_all_settings(session)


@router.put("", response_model=SettingsRead)
def update_settings(body: SettingsUpdate, session: Session = Depends(get_session)):
    data = body.model_dump(exclude_none=True)
    for key, value in data.items():
        if key in MASKED_KEYS and value == _SENTINEL:
            continue
        if isinstance(value, bool):
            set_setting(session, key, "true" if value else "false")
        else:
            set_setting(session, key, str(value))
    return get_all_settings(session)


@router.post("/test-paperless")
async def test_paperless(body: PaperlessTestRequest, session: Session = Depends(get_session)):
    from ..services.paperless import test_paperless_connection
    url = body.paperless_url or get_setting(session, "paperless_url")
    token = (
        get_setting(session, "paperless_token")
        if body.paperless_token in (_SENTINEL, "")
        else body.paperless_token
    )
    ok, msg = await test_paperless_connection(url, token)
    return {"ok": ok, "message": msg}


@router.get("/ai-models")
async def list_ai_models(
    provider: str = "claude",
    api_key: str = "",
    base_url: str = "",
    session: Session = Depends(get_session),
):
    from ..core.providers import make_provider
    resolved_key = (
        get_setting(session, "ai_api_key")
        if api_key in (_SENTINEL, "")
        else api_key
    )
    resolved_base_url = base_url or get_setting(session, "ai_base_url")
    prov = make_provider(provider, resolved_key, "", resolved_base_url)
    models = await prov.list_models()
    return {"models": models}


@router.post("/test-ai")
async def test_ai(body: AiTestRequest, session: Session = Depends(get_session)):
    from ..core.providers import make_provider
    api_key = (
        get_setting(session, "ai_api_key")
        if body.ai_api_key in (_SENTINEL, "")
        else body.ai_api_key
    )
    model = body.ai_model or get_setting(session, "ai_model")
    provider_name = body.ai_provider or get_setting(session, "ai_provider") or "claude"
    base_url = body.ai_base_url or get_setting(session, "ai_base_url")
    provider = make_provider(provider_name, api_key, model, base_url)
    ok, msg = await provider.test_connection()
    return {"ok": ok, "message": msg}
