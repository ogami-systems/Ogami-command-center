"""Layer 2 of Gmail's defense-in-depth model (see saint/GMAIL_ARCHITECTURE.md):
a service-level guarantee that Saint's Gmail client refuses to send, even
though the gmail.modify OAuth scope technically permits it, and even if a
future tool, agent, or prompt mistake tried to call send directly.

This is independent of every other layer. It does not know or care whether a
tool exists, whether an approval was granted, or why the caller wants to send
— it blocks unconditionally. The only way to lift the block is a hardcoded
`allow_send=True` at construction time in source code (never from .env,
config, or any runtime input) — a deliberate, reviewable, git-tracked change,
not a toggle.
"""

from __future__ import annotations

BLOCKED_METHODS = {"send"}


class SendBlockedError(RuntimeError):
    """Raised whenever code attempts to call a blocked Gmail send endpoint."""


class _BlockedMethod:
    """A callable that always raises SendBlockedError, regardless of args."""

    def __init__(self, resource_name: str, method_name: str):
        self._resource_name = resource_name
        self._method_name = method_name

    def __call__(self, *args, **kwargs):
        raise SendBlockedError(
            f"Gmail {self._resource_name}.{self._method_name}() is permanently blocked at the "
            f"service layer. This is not a bug — Saint's Gmail client refuses to send, "
            f"structurally, regardless of what code, approval, or prompt requested it. "
            f"See saint/GMAIL_ARCHITECTURE.md."
        )


class _SafeResourceProxy:
    """Wraps one Gmail sub-resource (e.g. users().messages()). Blocks the
    named methods in `blocked_methods` unconditionally; every other attribute
    delegates straight through to the real resource, untouched."""

    def __init__(self, real_resource, resource_name: str, blocked_methods: set[str], allow_send: bool):
        self._real_resource = real_resource
        self._resource_name = resource_name
        self._blocked_methods = blocked_methods
        self._allow_send = allow_send

    def __getattr__(self, name: str):
        if name in self._blocked_methods and not self._allow_send:
            return _BlockedMethod(self._resource_name, name)
        return getattr(self._real_resource, name)


class _SafeUsersProxy:
    """Wraps service.users(). Only .messages() and .drafts() are proxied
    (they're the two resources with a send-capable method); everything else
    on the users() resource delegates straight through."""

    def __init__(self, real_users, allow_send: bool):
        self._real_users = real_users
        self._allow_send = allow_send

    def messages(self):
        return _SafeResourceProxy(
            self._real_users.messages(), "messages", BLOCKED_METHODS, self._allow_send
        )

    def drafts(self):
        return _SafeResourceProxy(
            self._real_users.drafts(), "drafts", BLOCKED_METHODS, self._allow_send
        )

    def __getattr__(self, name: str):
        return getattr(self._real_users, name)


class SafeGmailService:
    """Wraps a raw Gmail API service object (from googleapiclient.discovery.build).
    .users().messages().send and .users().drafts().send are permanently
    blocked; every other capability (read, search, modify, trash, untrash,
    draft create/update, labels, threads, history, ...) passes through
    untouched — this is a send-block, not a general-purpose restriction."""

    def __init__(self, real_service, *, allow_send: bool = False):
        self._real_service = real_service
        self._allow_send = allow_send

    def users(self):
        return _SafeUsersProxy(self._real_service.users(), self._allow_send)

    def __getattr__(self, name: str):
        return getattr(self._real_service, name)
