"""Google Calendar tools.

Reading events is ungated (Read class). Creating and deleting events are
consequential — declared in CONSEQUENTIAL below — and must never be dispatched
directly from the model's tool-call loop; agent.py intercepts these before dispatch
and queues a Telegram approval instead. delete_calendar_event is Destructive (per
security-boundaries.md) and additionally forces Heavy-tier reasoning for the turn
that decides to call it (see agent.py's _pick_model).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from accounts.registry import AccountRegistry

TOOLS = [
    {
        "name": "calendar_list_events",
        "description": "List upcoming events on a Google Calendar within a time window.",
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["personal_google", "ogami_google", "imago_google"]},
                "calendar_id": {"type": "string", "default": "primary"},
                "time_min": {"type": "string", "description": "RFC3339 timestamp, defaults to now"},
                "time_max": {
                    "type": "string",
                    "description": "RFC3339 timestamp, defaults to 7 days after time_min",
                },
                "max_results": {"type": "integer", "default": 10},
            },
            "required": ["account"],
        },
    },
    {
        "name": "create_calendar_event",
        "description": (
            "Propose creating a calendar event. This is a consequential action: it is queued "
            "for the human's Approve/Reject via Telegram, not created immediately."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["personal_google", "ogami_google", "imago_google"]},
                "calendar_id": {"type": "string", "default": "primary"},
                "summary": {"type": "string"},
                "start": {"type": "string", "description": "RFC3339 start datetime"},
                "end": {"type": "string", "description": "RFC3339 end datetime"},
                "description": {"type": "string"},
                "location": {"type": "string"},
            },
            "required": ["account", "summary", "start", "end"],
        },
    },
    {
        "name": "delete_calendar_event",
        "description": (
            "Propose deleting a calendar event. This is a consequential, Destructive action: "
            "it is queued for the human's Approve/Reject via Telegram, not deleted immediately."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["personal_google", "ogami_google", "imago_google"]},
                "calendar_id": {"type": "string", "default": "primary"},
                "event_id": {"type": "string"},
            },
            "required": ["account", "event_id"],
        },
    },
]


def calendar_list_events(
    registry: AccountRegistry,
    account: str,
    calendar_id: str = "primary",
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    max_results: int = 10,
) -> dict:
    service = registry.get(account).get_calendar_service()
    time_min = time_min or datetime.now(timezone.utc).isoformat()
    time_max = time_max or (datetime.fromisoformat(time_min) + timedelta(days=7)).isoformat()
    resp = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = [
        {
            "id": e["id"],
            "summary": e.get("summary", "(no title)"),
            "start": e.get("start", {}),
            "end": e.get("end", {}),
            "location": e.get("location"),
        }
        for e in resp.get("items", [])
    ]
    return {"account": account, "calendar_id": calendar_id, "events": events}


def create_calendar_event(
    registry: AccountRegistry,
    account: str,
    summary: str,
    start: str,
    end: str,
    calendar_id: str = "primary",
    description: Optional[str] = None,
    location: Optional[str] = None,
) -> dict:
    service = registry.get(account).get_calendar_service()
    body = {"summary": summary, "start": {"dateTime": start}, "end": {"dateTime": end}}
    if description:
        body["description"] = description
    if location:
        body["location"] = location
    created = service.events().insert(calendarId=calendar_id, body=body).execute()
    return {"account": account, "calendar_id": calendar_id, "event": created}


def delete_calendar_event(
    registry: AccountRegistry,
    account: str,
    event_id: str,
    calendar_id: str = "primary",
) -> dict:
    service = registry.get(account).get_calendar_service()
    service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
    return {"account": account, "calendar_id": calendar_id, "event_id": event_id, "deleted": True}


HANDLERS = {
    "calendar_list_events": calendar_list_events,
    "create_calendar_event": create_calendar_event,
    "delete_calendar_event": delete_calendar_event,
}

CONSEQUENTIAL: dict[str, str] = {
    "create_calendar_event": "Communicate",
    "delete_calendar_event": "Destructive",
}
