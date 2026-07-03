"""Entrypoint. Builds one asyncio event loop and wires config, db, accounts,
telegram_bot, and scheduler onto it — required because python-telegram-bot
v21+ is asyncio-native and a second, independent blocking scheduler would
never get control of the loop.

Docker only ever runs this file. authorize.py (the interactive OAuth consent
script) never runs in a container — see its own docstring.
"""

from __future__ import annotations

import asyncio
import logging

import anthropic

import scheduler as scheduler_module
import telegram_bot
from accounts.registry import AccountRegistry
from config import Config
from db import Database

logger = logging.getLogger(__name__)


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def _startup_reconciliation(config: Config, database: Database, application) -> None:
    """Fail-closed reconciliation: expire any approval that went stale while Saint
    was down, then tell Michael what's still pending so a restart is never a
    silent gap (security-boundaries.md: no silent side effects)."""
    expired_ids = database.expire_stale()
    if expired_ids:
        logger.warning("Expired %d stale pending approval(s): %s", len(expired_ids), expired_ids)

    still_pending = database.list_pending()
    if still_pending:
        names = ", ".join(f"#{a.id} {a.tool_name}" for a in still_pending)
        await application.bot.send_message(
            chat_id=config.telegram_owner_id,
            text=f"Saint restarted. {len(still_pending)} approval(s) still awaiting your decision: {names}",
        )


async def main() -> None:
    config = Config.from_env()
    _setup_logging(config.saint_log_level)

    database = Database(config.saint_db_path)
    registry = AccountRegistry(config)
    anthropic_client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    application = telegram_bot.build_application(config, registry, database, anthropic_client)
    scheduler = scheduler_module.build_scheduler(config, application)

    async with application:
        await application.start()
        # drop_pending_updates=False is required, not just the default: a button tap
        # made while the bot was offline must be delivered on reconnect, never dropped.
        await application.updater.start_polling(drop_pending_updates=False)
        scheduler.start()

        await _startup_reconciliation(config, database, application)
        logger.info("Saint is running. Accounts configured: %s", list(registry.all_accounts()))

        try:
            await asyncio.Event().wait()
        finally:
            scheduler.shutdown(wait=False)
            await application.updater.stop()
            await application.stop()


if __name__ == "__main__":
    asyncio.run(main())
