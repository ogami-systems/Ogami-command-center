"""Tests for Layer 2 of Gmail's defense-in-depth model (see
saint/GMAIL_ARCHITECTURE.md and accounts/gmail_safety.py).

These use the real googleapiclient library's Gmail resource objects, built
offline via static_discovery=True (bundled discovery document, no network
call, no credentials) — proving the proxy works against the actual library's
object shape, not a hand-rolled approximation of it. Pass-through checks
compare method identity/equality rather than invoking the methods, so no
network call is ever attempted (blocked methods are safe to invoke — the
block raises before any real call happens; unblocked methods are only ever
attribute-checked here, never called).
"""

from __future__ import annotations

from googleapiclient.discovery import build

from accounts.gmail_safety import BLOCKED_METHODS, SafeGmailService, SendBlockedError, _SafeResourceProxy


def _real_gmail_service():
    return build("gmail", "v1", developerKey="unused", static_discovery=True)


def test_messages_send_blocked():
    safe = SafeGmailService(_real_gmail_service())
    try:
        safe.users().messages().send(userId="me", body={})
        assert False, "expected SendBlockedError"
    except SendBlockedError:
        pass


def test_drafts_send_blocked():
    safe = SafeGmailService(_real_gmail_service())
    try:
        safe.users().drafts().send(userId="me", body={})
        assert False, "expected SendBlockedError"
    except SendBlockedError:
        pass


def test_other_message_methods_pass_through():
    """googleapiclient builds a fresh Resource object on every .users()/
    .messages() call rather than caching — so comparing two independently
    -fetched resource chains' bound methods is never equal even when
    delegation is correct. Testing _SafeResourceProxy directly against one
    captured resource instance is the precise way to prove delegation."""
    real_messages = _real_gmail_service().users().messages()
    proxy = _SafeResourceProxy(real_messages, "messages", BLOCKED_METHODS, allow_send=False)
    for method_name in ("get", "list", "modify", "trash", "untrash"):
        assert getattr(proxy, method_name) == getattr(real_messages, method_name)


def test_other_draft_methods_pass_through():
    real_drafts = _real_gmail_service().users().drafts()
    proxy = _SafeResourceProxy(real_drafts, "drafts", BLOCKED_METHODS, allow_send=False)
    for method_name in ("create", "get", "list", "update", "delete"):
        assert getattr(proxy, method_name) == getattr(real_drafts, method_name)


def test_allow_send_explicit_override_works():
    """The escape hatch: allow_send=True must be an explicit, hardcoded
    constructor argument — never read from config — but when it IS set, send
    must actually work (not remain silently blocked)."""
    real_messages = _real_gmail_service().users().messages()
    proxy = _SafeResourceProxy(real_messages, "messages", BLOCKED_METHODS, allow_send=True)
    assert proxy.send == real_messages.send, "allow_send=True must return the real send method, not a block"


def test_other_resources_untouched():
    """Resources with no send-capable method (threads, labels, history) are
    never wrapped at all — proxying is scoped exactly to messages/drafts."""
    real = _real_gmail_service()
    safe = SafeGmailService(real)
    assert type(safe.users().threads()) is type(real.users().threads())
    assert type(safe.users().labels()) is type(real.users().labels())
    assert type(safe.users().history()) is type(real.users().history())
