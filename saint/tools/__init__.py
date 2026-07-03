"""Tool registry: aggregates schemas/handlers from every tools/*.py module and holds
the single CONSEQUENTIAL choke point agent.py checks before ever dispatching a tool
call for real. Individual tool modules never self-gate — this is deliberate: a future
contributor adding a new tool can't forget to wire the gate if agent.py is the sole
enforcer, reading this aggregated table, rather than trusting each module.

Per-tool action-class assignments (the authoritative table — 02-agents/saint.md links
here rather than restating it, per authoring-standard.md's single-source-of-truth rule):

| Tool                   | Action class  | Tier floor (model-routing.md) |
|-------------------------|--------------|--------------------------------|
| create_calendar_event    | Communicate  | Standard                       |
| delete_calendar_event    | Destructive  | Heavy (forced)                 |
| sheets_append            | Communicate  | Standard                       |

Everything else (Gmail search/read/trash/label, Drive/Docs read+create, Sheets read,
Calendar read, Tasks CRUD) is Read/Draft class and ungated.
"""

from __future__ import annotations

from typing import Callable

from tools import calendar_tools, drive_tools, gmail_tools, sheets_tools, tasks_tools

_MODULES = [gmail_tools, calendar_tools, drive_tools, sheets_tools, tasks_tools]

TOOLS: list[dict] = []
HANDLERS: dict[str, Callable[..., dict]] = {}
CONSEQUENTIAL: dict[str, str] = {}

for _module in _MODULES:
    TOOLS.extend(_module.TOOLS)
    HANDLERS.update(_module.HANDLERS)
    CONSEQUENTIAL.update(_module.CONSEQUENTIAL)

_tool_names = [t["name"] for t in TOOLS]
assert len(_tool_names) == len(set(_tool_names)), f"duplicate tool name(s): {_tool_names}"
assert set(_tool_names) == set(HANDLERS), "TOOLS/HANDLERS name mismatch"
assert set(CONSEQUENTIAL) <= set(_tool_names), "CONSEQUENTIAL references an unknown tool"


def is_consequential(tool_name: str) -> bool:
    return tool_name in CONSEQUENTIAL


def action_class(tool_name: str) -> str:
    return CONSEQUENTIAL.get(tool_name, "Read")


def dispatch(tool_name: str, registry, **kwargs) -> dict:
    """Executes a tool handler directly. Callers are responsible for having already
    resolved the approval queue for a consequential tool before calling this — this
    function does not gate anything itself. agent.py is the only caller that decides
    whether to call this immediately (Read/Draft) or queue an approval first
    (see is_consequential())."""
    handler = HANDLERS.get(tool_name)
    if handler is None:
        raise ValueError(f"Unknown tool '{tool_name}'")
    return handler(registry, **kwargs)
