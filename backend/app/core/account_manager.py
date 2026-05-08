from __future__ import annotations
import asyncio
import logging
from sqlmodel import Session, select
from ..db import engine
from ..models.account import MailAccount
from .imap_worker import IMAPWorker

log = logging.getLogger(__name__)


class AccountManager:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}
        self._workers: dict[str, IMAPWorker] = {}
        self.running = False

    def start(self) -> None:
        self.running = True
        loop = asyncio.get_running_loop()
        with Session(engine) as s:
            accounts = s.exec(select(MailAccount).where(MailAccount.enabled == True)).all()
        for account in accounts:
            self._launch(account, loop)
        log.info("AccountManager gestartet mit %d Accounts", len(accounts))

    def stop(self) -> None:
        self.running = False
        for worker in self._workers.values():
            worker.running = False
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
        self._workers.clear()
        log.info("AccountManager gestoppt")

    def start_account(self, account: MailAccount) -> None:
        loop = asyncio.get_running_loop()
        self._launch(account, loop)

    def stop_account(self, account_id: str) -> None:
        if account_id in self._workers:
            self._workers[account_id].running = False
        if account_id in self._tasks:
            self._tasks[account_id].cancel()
            del self._tasks[account_id]
        self._workers.pop(account_id, None)
        log.info("AccountManager: Worker für Account %s gestoppt", account_id)

    def restart_account(self, account: MailAccount) -> None:
        self.stop_account(account.id)
        if account.enabled:
            self.start_account(account)

    def _launch(self, account: MailAccount, loop: asyncio.AbstractEventLoop) -> None:
        worker = IMAPWorker(account)
        task = loop.create_task(worker.run())
        self._tasks[account.id] = task
        self._workers[account.id] = worker
        log.info("AccountManager: Worker für '%s' (%s) gestartet", account.name, account.id)

    async def process_all_now(self) -> None:
        await asyncio.gather(
            *[worker.process_once() for worker in self._workers.values()],
            return_exceptions=True,
        )

    async def process_account_now(self, account_id: str) -> None:
        if account_id in self._workers:
            await self._workers[account_id].process_once()
        else:
            with Session(engine) as s:
                account = s.get(MailAccount, account_id)
            if account:
                await IMAPWorker(account).process_once()
