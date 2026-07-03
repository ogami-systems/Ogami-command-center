"""Shared logging/security setup for every entrypoint that touches a live
credential — main.py, authorize.py, and agent.py's CLI REPL. Centralizing this
here means a future entrypoint inherits the same protections automatically,
rather than needing its own copy: this fixes the exact gap where main.py had
this hardening but authorize.py and agent.py's REPL did not.

Call setup_logging() first thing, before any code that might touch Telegram,
Google OAuth, or Anthropic.
"""

from __future__ import annotations

import logging
import sys
import traceback

from redact import redact

# These libraries can log full outbound request URLs at INFO level. Telegram's
# Bot API embeds the token directly in the URL path (unlike Anthropic/Google,
# which use Authorization headers), so an unmuted httpx/telegram logger would
# print the token in plain text. Force these to WARNING regardless of
# SAINT_LOG_LEVEL, so a future "turn on DEBUG for my own app logic" session
# never accidentally re-exposes a credential.
QUIET_LOGGER_NAMES = [
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


def _redacting_excepthook(exc_type, exc_value, exc_tb) -> None:
    # A safety net for exceptions that never pass through the logging module at
    # all — e.g. one that propagates past asyncio.run(), or out of a bare
    # script, straight to Python's default top-level handler, which writes to
    # stderr unredacted.
    text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    sys.stderr.write(redact(text))


def setup_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), handlers=[handler])

    for name in QUIET_LOGGER_NAMES:
        logging.getLogger(name).setLevel(logging.WARNING)

    sys.excepthook = _redacting_excepthook
