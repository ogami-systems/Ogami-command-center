"""Google Tasks tools. Personal task-list items are low-stakes and reversible
(unlike a calendar event visible to other attendees), so CRUD here is ungated —
the same judgment call as Gmail trash/labels in gmail_tools.py.
"""

from __future__ import annotations

from typing import Optional

from accounts.registry import AccountRegistry

TOOLS = [
    {
        "name": "tasks_list",
        "description": "List tasks on a Google Tasks list.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["personal_google", "ogami_google"]},
                "tasklist_id": {"type": "string", "default": "@default"},
                "show_completed": {"type": "boolean", "default": False},
            },
            "required": ["account"],
        },
    },
    {
        "name": "tasks_create",
        "description": "Create a new task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["personal_google", "ogami_google"]},
                "title": {"type": "string"},
                "notes": {"type": "string"},
                "due": {"type": "string", "description": "RFC3339 due date"},
                "tasklist_id": {"type": "string", "default": "@default"},
            },
            "required": ["account", "title"],
        },
    },
    {
        "name": "tasks_complete",
        "description": "Mark a task as completed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["personal_google", "ogami_google"]},
                "task_id": {"type": "string"},
                "tasklist_id": {"type": "string", "default": "@default"},
            },
            "required": ["account", "task_id"],
        },
    },
]


def tasks_list(
    registry: AccountRegistry, account: str, tasklist_id: str = "@default", show_completed: bool = False
) -> dict:
    service = registry.get(account).get_tasks_service()
    resp = service.tasks().list(tasklist=tasklist_id, showCompleted=show_completed).execute()
    return {"account": account, "tasklist_id": tasklist_id, "tasks": resp.get("items", [])}


def tasks_create(
    registry: AccountRegistry,
    account: str,
    title: str,
    notes: Optional[str] = None,
    due: Optional[str] = None,
    tasklist_id: str = "@default",
) -> dict:
    service = registry.get(account).get_tasks_service()
    body = {"title": title}
    if notes:
        body["notes"] = notes
    if due:
        body["due"] = due
    created = service.tasks().insert(tasklist=tasklist_id, body=body).execute()
    return {"account": account, "tasklist_id": tasklist_id, "task": created}


def tasks_complete(registry: AccountRegistry, account: str, task_id: str, tasklist_id: str = "@default") -> dict:
    service = registry.get(account).get_tasks_service()
    updated = service.tasks().patch(tasklist=tasklist_id, task=task_id, body={"status": "completed"}).execute()
    return {"account": account, "tasklist_id": tasklist_id, "task": updated}


HANDLERS = {
    "tasks_list": tasks_list,
    "tasks_create": tasks_create,
    "tasks_complete": tasks_complete,
}

# Nothing in this module is gated — see module docstring for why.
CONSEQUENTIAL: dict[str, str] = {}
