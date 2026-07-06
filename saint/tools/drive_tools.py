"""Drive and Docs tools. Read and create are both ungated here — Docs/Sheets
have version history, so an unwanted create is cheaply reversible (unlike a
calendar event another attendee sees, or a destructive Drive action). A future
drive_delete / drive_move would be Destructive and MUST be added to
CONSEQUENTIAL — see tools/__init__.py.

The `drive` OAuth scope (accounts/registry.py) covers Docs API access to files
reachable via Drive, so no separate Docs scope is needed.
"""

from __future__ import annotations

from accounts.registry import AccountRegistry

TOOLS = [
    {
        "name": "drive_search",
        "description": "Search Google Drive by name/content using Drive query syntax.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["personal_google", "ogami_google", "imago_google"]},
                "query": {"type": "string", "description": "Drive search query, e.g. \"name contains 'budget'\""},
                "max_results": {"type": "integer", "default": 10},
            },
            "required": ["account", "query"],
        },
    },
    {
        "name": "docs_read",
        "description": "Read the plain-text content of a Google Doc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["personal_google", "ogami_google", "imago_google"]},
                "document_id": {"type": "string"},
            },
            "required": ["account", "document_id"],
        },
    },
    {
        "name": "docs_create",
        "description": "Create a new Google Doc with the given title and initial plain-text content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["personal_google", "ogami_google", "imago_google"]},
                "title": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["account", "title", "content"],
        },
    },
]


def _extract_doc_text(document: dict) -> str:
    parts = []
    for element in document.get("body", {}).get("content", []):
        paragraph = element.get("paragraph")
        if not paragraph:
            continue
        for run in paragraph.get("elements", []):
            text_run = run.get("textRun")
            if text_run:
                parts.append(text_run.get("content", ""))
    return "".join(parts)


def drive_search(registry: AccountRegistry, account: str, query: str, max_results: int = 10) -> dict:
    service = registry.get(account).get_drive_service()
    resp = (
        service.files()
        .list(q=query, pageSize=max_results, fields="files(id,name,mimeType,modifiedTime,webViewLink)")
        .execute()
    )
    return {"account": account, "query": query, "files": resp.get("files", [])}


def docs_read(registry: AccountRegistry, account: str, document_id: str) -> dict:
    service = registry.get(account).get_docs_service()
    document = service.documents().get(documentId=document_id).execute()
    return {"account": account, "document_id": document_id, "title": document.get("title"), "text": _extract_doc_text(document)}


def docs_create(registry: AccountRegistry, account: str, title: str, content: str) -> dict:
    service = registry.get(account).get_docs_service()
    created = service.documents().create(body={"title": title}).execute()
    document_id = created["documentId"]
    if content:
        service.documents().batchUpdate(
            documentId=document_id,
            body={"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]},
        ).execute()
    return {
        "account": account,
        "document_id": document_id,
        "title": title,
        "url": f"https://docs.google.com/document/d/{document_id}/edit",
    }


HANDLERS = {
    "drive_search": drive_search,
    "docs_read": docs_read,
    "docs_create": docs_create,
}

# Nothing in this module is gated — see module docstring for why.
CONSEQUENTIAL: dict[str, str] = {}
