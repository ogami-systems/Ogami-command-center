"""Google Sheets tools. Split out from drive_tools.py deliberately: sheets_read
is Read-class and ungated, but sheets_append mutates a real sheet and is
consequential (Communicate class, gated via CONSEQUENTIAL below). Keeping a
gated and an ungated capability in separate files makes it easier to visually
confirm gating is complete just by looking at file boundaries.
"""

from __future__ import annotations

from typing import Optional

from accounts.registry import AccountRegistry

TOOLS = [
    {
        "name": "sheets_read",
        "description": (
            "Read a range from a Google Sheet. Returns computed/displayed values "
            "(e.g. the live result of a GOOGLEFINANCE() formula), never the raw formula text."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["personal_google", "ogami_google", "imago_google"]},
                "spreadsheet_id": {"type": "string"},
                "range": {"type": "string", "description": "A1 notation, e.g. 'Sheet1!A1:D20'"},
            },
            "required": ["account", "spreadsheet_id", "range"],
        },
    },
    {
        "name": "sheets_append",
        "description": (
            "Propose appending a row to a Google Sheet. This is a consequential action: "
            "it is queued for the human's Approve/Reject via Telegram, not written immediately."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string", "enum": ["personal_google", "ogami_google", "imago_google"]},
                "spreadsheet_id": {"type": "string"},
                "range": {"type": "string", "description": "A1 notation, e.g. 'Sheet1!A:D'"},
                "values": {
                    "type": "array",
                    "items": {"type": "array"},
                    "description": "Rows to append, each an array of cell values",
                },
            },
            "required": ["account", "spreadsheet_id", "range", "values"],
        },
    },
]


def sheets_read(registry: AccountRegistry, account: str, spreadsheet_id: str, range: str) -> dict:
    service = registry.get(account).get_sheets_service()
    # UNFORMATTED_VALUE returns the calculated value (e.g. 187.42), not the formula
    # string and not a formatted display string (e.g. "$187.42") — the most directly
    # usable shape for the model to reason over.
    resp = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range, valueRenderOption="UNFORMATTED_VALUE")
        .execute()
    )
    return {"account": account, "spreadsheet_id": spreadsheet_id, "range": range, "values": resp.get("values", [])}


def sheets_append(
    registry: AccountRegistry, account: str, spreadsheet_id: str, range: str, values: list[list]
) -> dict:
    service = registry.get(account).get_sheets_service()
    resp = (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=spreadsheet_id,
            range=range,
            valueInputOption="USER_ENTERED",
            body={"values": values},
        )
        .execute()
    )
    return {"account": account, "spreadsheet_id": spreadsheet_id, "updates": resp.get("updates")}


HANDLERS = {
    "sheets_read": sheets_read,
    "sheets_append": sheets_append,
}

CONSEQUENTIAL: dict[str, str] = {
    "sheets_append": "Communicate",
}
