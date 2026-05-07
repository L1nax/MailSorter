from __future__ import annotations
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select
from ..db import get_session
from ..models.account import MailAccount, MailAccountCreate, MailAccountUpdate, MailAccountRead
from ..core.imap_worker import test_imap_connection

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

_SENTINEL = "***"
_manager_ref = None


def set_account_manager(manager) -> None:
    global _manager_ref
    _manager_ref = manager


def _mask(account: MailAccount) -> MailAccountRead:
    return MailAccountRead(
        id=account.id,
        name=account.name,
        imap_host=account.imap_host,
        imap_port=account.imap_port,
        imap_user=account.imap_user,
        imap_password="***" if account.imap_password else "",
        imap_tls=account.imap_tls,
        imap_folder=account.imap_folder,
        trash_folder=account.trash_folder,
        poll_interval_seconds=account.poll_interval_seconds,
        use_idle=account.use_idle,
        enabled=account.enabled,
        created_at=account.created_at,
    )


def _get_or_404(account_id: str, session: Session) -> MailAccount:
    account = session.get(MailAccount, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.get("", response_model=list[MailAccountRead])
def list_accounts(session: Session = Depends(get_session)):
    accounts = session.exec(select(MailAccount).order_by(MailAccount.created_at)).all()
    return [_mask(a) for a in accounts]


@router.post("", response_model=MailAccountRead, status_code=201)
def create_account(body: MailAccountCreate, session: Session = Depends(get_session)):
    account = MailAccount(**body.model_dump())
    session.add(account)
    session.commit()
    session.refresh(account)
    if _manager_ref and account.enabled:
        _manager_ref.start_account(account)
    return _mask(account)


class ImapTestRequest(BaseModel):
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    imap_tls: bool = True


@router.post("/test-imap")
def test_imap_params(body: ImapTestRequest):
    """Verbindungstest mit beliebigen Parametern (vor dem Speichern)."""
    ok, msg = test_imap_connection(
        body.imap_host, body.imap_port,
        body.imap_user, body.imap_password,
        body.imap_tls,
    )
    return {"ok": ok, "message": msg}


@router.put("/{account_id}", response_model=MailAccountRead)
def update_account(account_id: str, body: MailAccountUpdate, session: Session = Depends(get_session)):
    account = _get_or_404(account_id, session)
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        if k == "imap_password" and v == _SENTINEL:
            continue
        setattr(account, k, v)
    session.add(account)
    session.commit()
    session.refresh(account)
    if _manager_ref:
        _manager_ref.restart_account(account)
    return _mask(account)


@router.delete("/{account_id}", status_code=204)
def delete_account(account_id: str, session: Session = Depends(get_session)):
    account = _get_or_404(account_id, session)
    if _manager_ref:
        _manager_ref.stop_account(account_id)
    session.delete(account)
    session.commit()


@router.post("/{account_id}/test-imap")
def test_account_imap(account_id: str, session: Session = Depends(get_session)):
    account = _get_or_404(account_id, session)
    ok, msg = test_imap_connection(
        account.imap_host, account.imap_port,
        account.imap_user, account.imap_password,
        account.imap_tls,
    )
    return {"ok": ok, "message": msg}


@router.post("/{account_id}/process-now", status_code=204)
async def process_account_now(account_id: str, session: Session = Depends(get_session)):
    _get_or_404(account_id, session)
    if _manager_ref:
        await _manager_ref.process_account_now(account_id)


@router.post("/{account_id}/reset-flags", status_code=204)
def reset_account_flags(account_id: str, session: Session = Depends(get_session)):
    account = _get_or_404(account_id, session)
    _reset_flags_sync(account)


def _reset_flags_sync(account) -> None:
    from imapclient import IMAPClient
    if not account.imap_host or not account.imap_user or not account.imap_password:
        return
    with IMAPClient(account.imap_host, port=account.imap_port, ssl=account.imap_tls) as imap:
        imap.login(account.imap_user, account.imap_password)
        imap.select_folder(account.imap_folder, readonly=False)
        try:
            uids = imap.search(["KEYWORD", "$MailSortProcessed"])
        except Exception:
            return
        if uids:
            imap.remove_flags(uids, [b"$MailSortProcessed"])
