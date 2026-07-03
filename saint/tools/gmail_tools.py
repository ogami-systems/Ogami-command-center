"""Gmail tools: search, read, trash, and label management.

gmail.send is never requested as a scope (see accounts/registry.py) and no send or
compose function exists in this module, or anywhere else in Saint. This is a
structural guarantee, not a gated one — the capability does not exist to be misused.

Trash and label changes are reversible (Gmail retains trashed messages for ~30 days)
and are kept ungated here, matching the read+trash+label tier the gmail.modify scope
grants. Only actions that are harder to reverse (calendar deletes, Sheets appends,
future destructive Drive actions) are gated via CONSEQUENTIAL — see tools/__init__.py.
"""

from __future__ import annotations

import base64
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
                "account": {"type": "string", "enum": ["personal_google", "ogami_google"]},
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
                "account": {"type": "string", "enum": ["personal_google", "ogami_google"]},
                "message_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["account", "message_ids"],
        },
    },
    {
        "name": "gmail_trash_message",
        "description": "Move a Gmail message to Trash (reversible; Gmail retains trashed messages for ~30 days).",
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["personal_google", "ogami_google"]},
                "message_id": {"type": "string"},
            },
            "required": ["account", "message_id"],
        },
    },
    {
        "name": "gmail_modify_labels",
        "description": (
            "Add and/or remove labels on a Gmail message (e.g. archive by removing INBOX, "
            "or mark read by removing UNREAD)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["personal_google", "ogami_google"]},
                "message_id": {"type": "string"},
                "add_labels": {"type": "array", "items": {"type": "string"}, "default": []},
                "remove_labels": {"type": "array", "items": {"type": "string"}, "default": []},
            },
            "required": ["account", "message_id"],
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


def gmail_trash_message(registry: AccountRegistry, account: str, message_id: str) -> dict:
    service = registry.get(account).get_gmail_service()
    service.users().messages().trash(userId="me", id=message_id).execute()
    return {"account": account, "message_id": message_id, "trashed": True}


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


HANDLERS = {
    "gmail_search": gmail_search,
    "gmail_read_messages": gmail_read_messages,
    "gmail_trash_message": gmail_trash_message,
    "gmail_modify_labels": gmail_modify_labels,
}

# Nothing in this module is gated — see module docstring for why.
CONSEQUENTIAL: dict[str, str] = {}
