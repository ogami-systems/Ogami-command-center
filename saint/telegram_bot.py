"""Telegram interface: owner-only allowlist, /briefing stub, free-text routing
into agent.py, and the Approve/Reject inline-keyboard flow for consequential
actions.

agent.run_turn is synchronous (blocking) by design — it's run in a thread-pool
executor from each async handler so a slow Claude/Google API call never blocks
Telegram polling or the scheduler sharing this process's event loop. Pending-
approval callbacks fire from that worker thread, so they hop back onto the main
event loop via asyncio.run_coroutine_threadsafe rather than creating a task
directly (which is only safe from the loop's own thread).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import agent
import db as dbmod
from accounts.registry import AccountRegistry
from config import Config
from redact import redact

logger = logging.getLogger(__name__)


def _owner_only(config: Config):
    def decorator(handler):
        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user = update.effective_user
            if user is None or user.id != config.telegram_owner_id:
                logger.warning("Rejected update from non-owner user_id=%s", user.id if user else None)
                return
            return await handler(update, context)

        return wrapped

    return decorator


def build_application(
    config: Config,
    registry: AccountRegistry,
    database: dbmod.Database,
    anthropic_client,
) -> Application:
    application = ApplicationBuilder().token(config.telegram_bot_token).build()
    owner_only = _owner_only(config)

    # One Run + message history per chat. Single-owner bot, low volume — a plain
    # dict with no locking is an accepted simplicity tradeoff at this scale.
    conversations: dict[int, tuple] = {}

    def _get_conversation(chat_id: int):
        if chat_id not in conversations:
            conversations[chat_id] = (agent.Run.new(config, registry, database), [])
        return conversations[chat_id]

    @owner_only
    async def briefing_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # Stub — the real scheduler-driven briefing content is future work (Phase B).
        await update.message.reply_text("Good morning. (Briefing content isn't wired up yet — this is a stub.)")

    @owner_only
    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        run, messages = _get_conversation(chat_id)
        loop = asyncio.get_running_loop()

        def on_pending_approval(approval_id: int, tool_name: str, tool_args: dict, account: Optional[str]) -> None:
            asyncio.run_coroutine_threadsafe(
                send_approval_request(application, database, chat_id, approval_id, tool_name, tool_args, account),
                loop,
            )

        run.on_pending_approval = on_pending_approval
        messages.append({"role": "user", "content": update.message.text})
        reply = await loop.run_in_executor(None, agent.run_turn, run, anthropic_client, messages)
        await update.message.reply_text(reply)

    async def handle_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query.from_user is None or query.from_user.id != config.telegram_owner_id:
            await query.answer("Not authorized.")
            return

        action, _, approval_id_str = (query.data or "").partition(":")
        try:
            approval_id = int(approval_id_str)
        except ValueError:
            await query.answer("Malformed callback.")
            return

        # Always re-read from disk, never trust anything cached in memory — this
        # is what makes a double-tap or a post-restart tap safe (security-boundaries.md).
        approval = database.get_approval(approval_id)
        if approval is None or approval.status != dbmod.PENDING:
            await query.answer("Already handled.")
            return

        if action == "reject":
            database.update_status(approval_id, dbmod.REJECTED)
            await query.edit_message_text(f"Rejected: {approval.tool_name}")
            await query.answer()
            return

        if action != "approve":
            await query.answer("Unknown action.")
            return

        database.update_status(approval_id, dbmod.APPROVED)
        try:
            result = agent.execute_approved(registry, approval)
            database.update_status(approval_id, dbmod.EXECUTED, result=result)
            await query.edit_message_text(f"Approved and executed: {approval.tool_name}")
        except Exception as exc:  # noqa: BLE001 — surface any failure to Michael, never retry silently
            safe_error = redact(str(exc))
            database.update_status(approval_id, dbmod.FAILED, result={"error": safe_error})
            await query.edit_message_text(f"Approved but failed: {approval.tool_name} — {safe_error}")
        await query.answer()

    application.add_handler(CommandHandler("briefing", briefing_command))
    application.add_handler(CallbackQueryHandler(handle_approval_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return application


async def send_approval_request(
    application: Application,
    database: dbmod.Database,
    chat_id: int,
    approval_id: int,
    tool_name: str,
    tool_args: dict,
    account: Optional[str],
) -> None:
    text = f"Approval needed: *{tool_name}*\nAccount: {account or 'n/a'}\nArgs: `{json.dumps(tool_args)}`"
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Approve", callback_data=f"approve:{approval_id}"),
                InlineKeyboardButton("Reject", callback_data=f"reject:{approval_id}"),
            ]
        ]
    )
    message = await application.bot.send_message(
        chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard
    )
    database.set_telegram_message(approval_id, chat_id=chat_id, message_id=message.message_id)
