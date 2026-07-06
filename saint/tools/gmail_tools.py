"""Gmail tools: read, search, and every write operation Saint supports.

Defense-in-depth (see saint/GMAIL_ARCHITECTURE.md for the full design):
gmail.modify is the OAuth scope in use, and it technically permits Gmail's
send endpoint — there is no narrower Google scope that keeps archive/label/
draft capability without also granting send. Given that, Saint's guarantees
here come from three independent layers, not the OAuth grant:

  1. No send/reply-send tool is registered in this module or anywhere in the
     codebase — the capability doesn't exist to be called.
  2. Even if one existed, GoogleAccount.get_gmail_service() returns a
     SafeGmailService (accounts/gmail_safety.py) that unconditionally blocks
     .users().messages().send and .users().drafts().send, regardless of
     caller.
  3. Every write operation below is CONSEQUENTIAL — queued for Michael's
     Telegram Approve/Reject, never executed directly from the model loop.
     This is a deliberate tightening beyond what earlier versions of this
     module did (trash/label were previously ungated) — superseded per
     Michael's explicit "every Gmail write is gated by default" decision.

Read-only operations (search, read) remain ungated, per the Read row of
security-boundaries.md's Action Classes table.

Permanent deletion (users.messages.delete) requires the mail.google.com scope
alone — never requested here — so no delete tool exists or ever will; the
capability is excluded at the OAuth layer, before any gating question arises.
"""

from __future__ import annotations

import base64
from email.mime.text import MIMEText
from typing import Optional

from accounts.registry import AccountRegistry

TOOLS = [
    {
        "name": "gmail_search",
        "description": (
            "Search a Gmail account using Gmail search syntax (e.g. 'from:someone is:unread'). "
            "Returns message summaries (id, snippet, from, subject, date), not full bodies."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["personal_google", "ogami_google", "imago_google"]},
                "query": {"type": "string", "description": "Gmail search query syntax"},
                "max_results": {"type": "integer", "default": 10},
            },
            "required": ["account", "query"],
        },
    },
    {
        "name": "gmail_read_messages",
        "description": "Fetch full content (subject, from, date, body) for one or more Gmail message IDs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["personal_google", "ogami_google", "imago_google"]},
                "message_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["account", "message_ids"],
        },
    },
    {
        "name": "gmail_archive_message",
        "description": (
            "Propose archiving a Gmail message (removes it from Inbox; fully reversible). "
            "Consequential — queued for Michael's Telegram Approve/Reject, not executed immediately."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["personal_google", "ogami_google", "imago_google"]},
                "message_id": {"type": "string"},
            },
            "required": ["account", "message_id"],
        },
    },
    {
        "name": "gmail_trash_message",
        "description": (
            "Propose moving a Gmail message to Trash (reversible; Gmail retains trashed messages "
            "for ~30 days). Consequential — queued for approval, not executed immediately."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["personal_google", "ogami_google", "imago_google"]},
                "message_id": {"type": "string"},
            },
            "required": ["account", "message_id"],
        },
    },
    {
        "name": "gmail_untrash_message",
        "description": "Propose restoring a Gmail message out of Trash. Consequential.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["personal_google", "ogami_google", "imago_google"]},
                "message_id": {"type": "string"},
            },
            "required": ["account", "message_id"],
        },
    },
    {
        "name": "gmail_mark_read_status",
        "description": "Propose marking a Gmail message as read or unread. Consequential.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["personal_google", "ogami_google", "imago_google"]},
                "message_id": {"type": "string"},
                "read": {"type": "boolean", "description": "true = mark read, false = mark unread"},
            },
            "required": ["account", "message_id", "read"],
        },
    },
    {
        "name": "gmail_modify_labels",
        "description": (
            "Propose adding and/or removing arbitrary labels on a Gmail message, beyond the named "
            "archive/mark-read conveniences above. Consequential."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["personal_google", "ogami_google", "imago_google"]},
                "message_id": {"type": "string"},
                "add_labels": {"type": "array", "items": {"type": "string"}, "default": []},
                "remove_labels": {"type": "array", "items": {"type": "string"}, "default": []},
            },
            "required": ["account", "message_id"],
        },
    },
    {
        "name": "gmail_create_draft",
        "description": (
            "Propose creating a new, unsent Gmail draft. Never sent automatically — Saint has no "
            "send capability at all (see saint/GMAIL_ARCHITECTURE.md). Consequential."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["personal_google", "ogami_google", "imago_google"]},
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["account", "to", "subject", "body"],
        },
    },
    {
        "name": "gmail_update_draft",
        "description": "Propose updating an existing, unsent Gmail draft. Consequential.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["personal_google", "ogami_google", "imago_google"]},
                "draft_id": {"type": "string"},
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
            "required": ["account", "draft_id", "to", "subject", "body"],
        },
    },
    {
        "name": "gmail_create_reply_draft",
        "description": (
            "Propose creating an unsent draft reply within an existing email thread. Kept distinct "
            "from gmail_create_draft so the Telegram approval prompt clearly reads as a reply, not a "
            "new message. Consequential."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["personal_google", "ogami_google", "imago_google"]},
                "thread_id": {"type": "string"},
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "in_reply_to_message_id": {
                    "type": "string",
                    "description": "RFC822 Message-ID header of the message being replied to, for correct threading",
                },
            },
            "required": ["account", "thread_id", "to", "subject", "body"],
        },
    },
]


def _decode_headers(headers: list[dict]) -> dict:
    wanted = {"From", "To", "Subject", "Date"}
    return {h["name"]: h["value"] for h in headers if h["name"] in wanted}


def _extract_body(payload: dict) -> str:
    def decode(data: str) -> str:
        return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")

    if payload.get("mimeType", "").startswith("text/") and payload.get("body", {}).get("data"):
        return decode(payload["body"]["data"])
    for part in payload.get("parts") or []:
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return decode(part["body"]["data"])
    for part in payload.get("parts") or []:
        text = _extract_body(part)
        if text:
            return text
    return ""


def _build_raw_message(to: str, subject: str, body: str, extra_headers: Optional[dict] = None) -> str:
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    for key, value in (extra_headers or {}).items():
        message[key] = value
    return base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")


def gmail_search(registry: AccountRegistry, account: str, query: str, max_results: int = 10) -> dict:
    service = registry.get(account).get_gmail_service()
    resp = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    results = []
    for m in resp.get("messages", []):
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=m["id"], format="metadata", metadataHeaders=["From", "Subject", "Date"])
            .execute()
        )
        headers = _decode_headers(msg.get("payload", {}).get("headers", []))
        results.append({"id": msg["id"], "snippet": msg.get("snippet", ""), **headers})
    return {"account": account, "query": query, "results": results}


def gmail_read_messages(registry: AccountRegistry, account: str, message_ids: list[str]) -> dict:
    service = registry.get(account).get_gmail_service()
    results = []
    for mid in message_ids:
        msg = service.users().messages().get(userId="me", id=mid, format="full").execute()
        headers = _decode_headers(msg.get("payload", {}).get("headers", []))
        body = _extract_body(msg.get("payload", {}))
        results.append({"id": mid, "snippet": msg.get("snippet", ""), "body": body, **headers})
    return {"account": account, "messages": results}


def gmail_archive_message(registry: AccountRegistry, account: str, message_id: str) -> dict:
    service = registry.get(account).get_gmail_service()
    service.users().messages().modify(userId="me", id=message_id, body={"removeLabelIds": ["INBOX"]}).execute()
    return {"account": account, "message_id": message_id, "archived": True}


def gmail_trash_message(registry: AccountRegistry, account: str, message_id: str) -> dict:
    service = registry.get(account).get_gmail_service()
    service.users().messages().trash(userId="me", id=message_id).execute()
    return {"account": account, "message_id": message_id, "trashed": True}


def gmail_untrash_message(registry: AccountRegistry, account: str, message_id: str) -> dict:
    service = registry.get(account).get_gmail_service()
    service.users().messages().untrash(userId="me", id=message_id).execute()
    return {"account": account, "message_id": message_id, "restored": True}


def gmail_mark_read_status(registry: AccountRegistry, account: str, message_id: str, read: bool) -> dict:
    service = registry.get(account).get_gmail_service()
    body = {"removeLabelIds": ["UNREAD"]} if read else {"addLabelIds": ["UNREAD"]}
    service.users().messages().modify(userId="me", id=message_id, body=body).execute()
    return {"account": account, "message_id": message_id, "read": read}


def gmail_modify_labels(
    registry: AccountRegistry,
    account: str,
    message_id: str,
    add_labels: Optional[list[str]] = None,
    remove_labels: Optional[list[str]] = None,
) -> dict:
    service = registry.get(account).get_gmail_service()
    body = {"addLabelIds": add_labels or [], "removeLabelIds": remove_labels or []}
    service.users().messages().modify(userId="me", id=message_id, body=body).execute()
    return {"account": account, "message_id": message_id, **body}


def gmail_create_draft(registry: AccountRegistry, account: str, to: str, subject: str, body: str) -> dict:
    service = registry.get(account).get_gmail_service()
    raw = _build_raw_message(to=to, subject=subject, body=body)
    created = service.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
    return {"account": account, "draft": created}


def gmail_update_draft(
    registry: AccountRegistry, account: str, draft_id: str, to: str, subject: str, body: str
) -> dict:
    service = registry.get(account).get_gmail_service()
    raw = _build_raw_message(to=to, subject=subject, body=body)
    updated = service.users().drafts().update(userId="me", id=draft_id, body={"message": {"raw": raw}}).execute()
    return {"account": account, "draft": updated}


def gmail_create_reply_draft(
    registry: AccountRegistry,
    account: str,
    thread_id: str,
    to: str,
    subject: str,
    body: str,
    in_reply_to_message_id: Optional[str] = None,
) -> dict:
    service = registry.get(account).get_gmail_service()
    extra_headers = {}
    if in_reply_to_message_id:
        extra_headers["In-Reply-To"] = in_reply_to_message_id
        extra_headers["References"] = in_reply_to_message_id
    raw = _build_raw_message(to=to, subject=subject, body=body, extra_headers=extra_headers)
    created = (
        service.users()
        .drafts()
        .create(userId="me", body={"message": {"raw": raw, "threadId": thread_id}})
        .execute()
    )
    return {"account": account, "draft": created}


HANDLERS = {
    "gmail_search": gmail_search,
    "gmail_read_messages": gmail_read_messages,
    "gmail_archive_message": gmail_archive_message,
    "gmail_trash_message": gmail_trash_message,
    "gmail_untrash_message": gmail_untrash_message,
    "gmail_mark_read_status": gmail_mark_read_status,
    "gmail_modify_labels": gmail_modify_labels,
    "gmail_create_draft": gmail_create_draft,
    "gmail_update_draft": gmail_update_draft,
    "gmail_create_reply_draft": gmail_create_reply_draft,
}

# Every Gmail write operation is gated by default, per Michael's explicit
# decision — see saint/GMAIL_ARCHITECTURE.md. Only gmail_search and
# gmail_read_messages (Read class, not listed here) are ungated.
CONSEQUENTIAL: dict[str, str] = {
    "gmail_archive_message": "Communicate",
    "gmail_trash_message": "Communicate",
    "gmail_untrash_message": "Communicate",
    "gmail_mark_read_status": "Communicate",
    "gmail_modify_labels": "Communicate",
    "gmail_create_draft": "Communicate",
    "gmail_update_draft": "Communicate",
    "gmail_create_reply_draft": "Communicate",
}
