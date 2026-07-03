"""Scrubs credential-shaped substrings from text before it is logged, or shown
to Michael, or sent back into the model's context.

Telegram's Bot API embeds the token directly in request URLs
(https://api.telegram.org/bot<TOKEN>/...) rather than in a header. python-
telegram-bot's own NetworkError wraps the underlying httpx exception's string
form verbatim (`f"httpx.{err.__class__.__name__}: {err}"`), and many httpx
exceptions' __str__ includes the full request URL — so the token can appear in
an exception *message*, not just in an HTTP-library debug log. Muting
httpx/httpcore/telegram logger levels (see main.py) stops the request itself
from being logged, but does not stop an already-raised exception's own message
from carrying the token wherever it's turned into text. This module is that
second, independent layer.
"""

from __future__ import annotations

import re

_PATTERNS = [
    re.compile(r"/bot\d+:[A-Za-z0-9_-]+"),  # Telegram bot token embedded in a URL
    re.compile(r"Bearer\s+[A-Za-z0-9\-_.]+"),  # generic Bearer auth header text, if ever logged
    re.compile(r"sk-ant-[A-Za-z0-9\-_]+"),  # Anthropic API keys
]


def redact(text: str) -> str:
    for pattern in _PATTERNS:
        text = pattern.sub("<redacted>", text)
    return text
