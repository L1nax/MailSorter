from __future__ import annotations
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .db import init_db
from .core.account_manager import AccountManager
from .api import rules, logs, settings
from .api.accounts import router as accounts_router, set_account_manager
from .api.status import router as status_router, set_account_manager as set_status_manager
from .api.suggestions import router as suggestions_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

account_manager = AccountManager()

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    set_account_manager(account_manager)
    set_status_manager(account_manager)
    account_manager.start()
    yield
    account_manager.stop()


app = FastAPI(title="MailSort", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rules.router)
app.include_router(logs.router)
app.include_router(settings.router)
app.include_router(accounts_router)
app.include_router(status_router)
app.include_router(suggestions_router)


@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        from sqlmodel import Session
        from .db import engine
        from .config import get_setting
        with Session(engine) as s:
            required_key = get_setting(s, "api_key")
        if required_key:
            provided = request.headers.get("X-API-Key", "")
            if provided != required_key:
                raise HTTPException(status_code=401, detail="Invalid API key")
    return await call_next(request)


if os.path.isdir(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        index = os.path.join(STATIC_DIR, "index.html")
        return FileResponse(index)
