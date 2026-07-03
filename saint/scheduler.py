"""Scheduler skeleton: its own AsyncIOScheduler sharing main.py's asyncio event
loop, rather than python-telegram-bot's built-in JobQueue. This costs one more
moving part but keeps scheduler logic decoupled from Telegram internals and
matches the intended file layout. main.py is responsible for running both this
and telegram_bot.py on the same event loop.

Only the daily briefing job exists so far — stub content. The full backlog
(Growth Packet, wind-down, weekly review, self-improving news filter, etc.) is
Phase B, layered on this skeleton later.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram.ext import Application

from config import Config

logger = logging.getLogger(__name__)


def build_scheduler(config: Config, application: Application) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=config.saint_timezone)

    async def briefing_job() -> None:
        try:
            await application.bot.send_message(
                chat_id=config.telegram_owner_id,
                text="Good morning. (Scheduled briefing content isn't wired up yet — this is a stub.)",
            )
        except Exception:
            logger.exception("Daily briefing job failed to send")

    scheduler.add_job(
        briefing_job,
        CronTrigger(hour=6, minute=0),
        id="daily_briefing",
        replace_existing=True,
    )
    return scheduler
