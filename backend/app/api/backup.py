from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlmodel import Session
from ..db import get_session
from ..core.backup import export_data, import_data, ALL_SECTIONS

router = APIRouter(prefix="/api/backup", tags=["backup"])


class ImportRequest(BaseModel):
    mode: str = "merge"
    data: dict[str, Any]


@router.get("/export")
def backup_export(
    sections: str | None = Query(None, description="Kommasepariert: rules,accounts,settings,suggestions"),
    session: Session = Depends(get_session),
) -> Response:
    secs = [s.strip() for s in sections.split(",")] if sections else list(ALL_SECTIONS)
    unknown = set(secs) - set(ALL_SECTIONS)
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unbekannte Sektionen: {', '.join(unknown)}")
    data = export_data(session, secs)
    filename = f"mailsort-backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
    content = json.dumps(data, indent=2, default=str)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import")
def backup_import(
    body: ImportRequest,
    session: Session = Depends(get_session),
) -> dict[str, int]:
    if body.data.get("version") != 1:
        raise HTTPException(
            status_code=400,
            detail=f"Unbekannte Backup-Version: {body.data.get('version')!r}",
        )
    if body.mode not in ("merge", "replace"):
        raise HTTPException(status_code=400, detail="mode muss 'merge' oder 'replace' sein")
    return import_data(session, body.data, body.mode)
