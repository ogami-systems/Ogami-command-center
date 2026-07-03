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
import sys
import traceback

import anthropic

import scheduler as scheduler_module
import telegram_bot
from accounts.registry import AccountRegistry
from config import Config
from db import Database
from redact import redact

logger = logging.getLogger(__name__)

# These libraries can log full outbound request URLs at INFO level. Telegram's
# Bot API embeds the token directly in the URL path (unlike Anthropic/Google,
# which use Authorization headers), so an unmuted httpx/telegram logger would
# print the token in plain text. Force these to WARNING regardless of
# SAINT_LOG_LEVEL, so a future "turn on DEBUG for my own app logic" session
# never accidentally re-exposes a credential.
_QUIET_LOGGER_NAMES = [
    "httpx",
    "httpcore",
    "telegram",
    "telegram.ext",
    "telegram.request",
    "googleapiclient",
    "googleapiclient.discovery",
    "google.auth",
    "google_auth_httplib2",
    "urllib3",
    "requests",
    "anthropic",
]


class RedactingFormatter(logging.Formatter):
    """Redacts credential-shaped substrings from every formatted log line,
    including exception tracebacks (exc_info) — see redact.py for why a
    logger-level mute alone isn't sufficient."""

    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def _setup_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), handlers=[handler])

    for name in _QUIET_LOGGER_NAMES:
        logging.getLogger(name).setLevel(logging.WARNING)

    def _redacting_excepthook(exc_type, exc_value, exc_tb) -> None:
        # A safety net for exceptions that never pass through the logging module at
        # all — e.g. one that propagates out of main() past asyncio.run() to
        # Python's default top-level handler, which prints straight to stderr.
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        sys.stderr.write(redact(text))

    sys.excepthook = _redacting_excepthook


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
        try:
            await application.bot.send_message(
                chat_id=config.telegram_owner_id,
                text=f"Saint restarted. {len(still_pending)} approval(s) still awaiting your decision: {names}",
            )
        except Exception as exc:  # noqa: BLE001 — never let a notification failure crash startup
            logger.error("Failed to send restart-reconciliation message: %s", redact(str(exc)))


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
