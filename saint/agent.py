"""The Claude tool-call loop: model tier selection, daily budget governor,
self-escalation, and the single point where consequential tool calls are
intercepted before ever reaching a real side effect.

Model tiers here are a subset of 01-rules/model-routing.md's table (Heavy=Opus,
Standard=Sonnet) — Saint has no Groq/Fast-tier key configured, so everything
that isn't Heavy runs at Standard. Destructive-class tool calls always force a
fresh Heavy-tier reasoning pass before they're ever queued for approval, per
model-routing.md's "high-stakes action classes MUST use Heavy tier" rule.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

import anthropic

import tools
from accounts.registry import AccountRegistry
from config import Config
from db import Database

STANDARD = "standard"
HEAVY = "heavy"

TIER_MODELS = {
    STANDARD: "claude-sonnet-5",
    HEAVY: "claude-opus-4-8",
}

# Pricing per million tokens (USD). Sonnet 5 is at its introductory rate through
# 2026-08-31 ($2/$10) — revert to $3/$15 after that date. Opus 4.8 has no
# introductory period. Source: Anthropic pricing, checked 2026-07-03.
PRICING_PER_MTOK = {
    "claude-sonnet-5": {"input": 2.00, "output": 10.00},
    "claude-opus-4-8": {"input": 5.00, "output": 25.00},
}

# Mirrors security-boundaries.md's action-class table. Any class not listed
# (Read, Draft, Communicate) is fine at Standard tier.
MIN_TIER_FOR_CLASS = {
    "Financial": HEAVY,
    "Credential": HEAVY,
    "Destructive": HEAVY,
    "Administrative": HEAVY,
}

MAX_TOKENS = 4096

ESCALATE_TOOL = {
    "name": "escalate_model",
    "description": (
        "Request that the rest of this conversation turn run on the Heavy (Opus) "
        "model tier instead of Standard (Sonnet) — use only when the task is "
        "unusually difficult, security-sensitive, or high-stakes. Capped per run; "
        "calling this after the cap is reached has no effect."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {"type": "string", "description": "Why Heavy-tier reasoning is needed"},
        },
        "required": ["reason"],
    },
}

SYSTEM_PROMPT = """\
You are Saint, Michael's personal executive assistant. You operate across two \
Google account contexts: "personal_google" (Michael's personal Gmail/Drive/\
Calendar/Tasks) and "ogami_google" (the Ogami business account). Every Google \
tool call takes an `account` parameter — always pick the correct one for the \
request, and ask if it's ambiguous.

You cannot send email. There is no send tool and none will ever be added — \
if asked to send something, draft it in the reply or as a Doc instead.

Some tools are consequential: calendar event creation/deletion and Sheets \
appends do not execute when you call them. They are queued for Michael's \
explicit Approve/Reject via Telegram. When a tool result has \
status="pending_approval", tell Michael in plain language what you've queued \
and that it's awaiting his decision — do not claim the action is done.

Be concise. Michael is a CEO, not an engineer — skip implementation detail \
unless asked."""


@dataclass
class Run:
    run_id: str
    config: Config
    registry: AccountRegistry
    db: Database
    tier: str = STANDARD
    escalations_used: int = 0
    on_pending_approval: Optional[Callable[[int, str, dict, Optional[str]], None]] = None

    @classmethod
    def new(cls, config: Config, registry: AccountRegistry, db: Database, **kwargs) -> "Run":
        return cls(run_id=str(uuid.uuid4()), config=config, registry=registry, db=db, **kwargs)


def _cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = PRICING_PER_MTOK[model]
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


def _destructive_tool_names(response_content) -> list[str]:
    return [
        block.name
        for block in response_content
        if block.type == "tool_use" and tools.action_class(block.name) == "Destructive"
    ]


def _tool_result(tool_use_id: str, result: dict) -> dict:
    return {"type": "tool_result", "tool_use_id": tool_use_id, "content": json.dumps(result)}


def _budget_exhausted(run: Run) -> bool:
    return run.db.get_daily_spend() >= run.config.model_daily_budget_usd


def run_turn(run: Run, client: anthropic.Anthropic, messages: list) -> str:
    """Runs one full tool-use turn (possibly several tool round-trips) and
    returns the final assistant text. Mutates `messages` in place."""

    while True:
        tier = run.tier
        model = TIER_MODELS[tier]

        response = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=[ESCALATE_TOOL] + tools.TOOLS,
        )

        # Destructive-class intent must be reasoned at Heavy tier — if a Standard-tier
        # response wants to call one, discard it and re-ask at Heavy before honoring it.
        if tier != HEAVY and _destructive_tool_names(response.content):
            tier = HEAVY
            model = TIER_MODELS[tier]
            response = client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=[ESCALATE_TOOL] + tools.TOOLS,
            )

        run.db.record_usage(
            tier=tier,
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cost_usd=_cost_usd(model, response.usage.input_tokens, response.usage.output_tokens),
        )

        if response.stop_reason != "tool_use":
            return "".join(b.text for b in response.content if b.type == "text")

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            if block.name == "escalate_model":
                if run.escalations_used >= run.config.max_escalations_per_run:
                    result = {"escalated": False, "reason": "escalation cap reached for this run"}
                elif _budget_exhausted(run):
                    result = {"escalated": False, "reason": "daily model budget exhausted"}
                else:
                    run.escalations_used += 1
                    run.tier = HEAVY
                    result = {"escalated": True, "reason": block.input.get("reason")}
                tool_results.append(_tool_result(block.id, result))
                continue

            if tools.is_consequential(block.name):
                approval_id = run.db.create_approval(
                    tool_name=block.name,
                    tool_args=block.input,
                    action_class=tools.action_class(block.name),
                    account=block.input.get("account"),
                    requested_by_run_id=run.run_id,
                )
                if run.on_pending_approval:
                    run.on_pending_approval(approval_id, block.name, block.input, block.input.get("account"))
                result = {"status": "pending_approval", "approval_id": approval_id}
                tool_results.append(_tool_result(block.id, result))
                continue

            try:
                result = tools.dispatch(block.name, run.registry, **block.input)
            except Exception as exc:
                result = {"error": str(exc)}
            tool_results.append(_tool_result(block.id, result))

        messages.append({"role": "user", "content": tool_results})


def execute_approved(run_or_registry, approval) -> dict:
    """Invoked only by the Telegram Approve callback, never by the model loop.
    Executes the real tool call for an approved consequential action."""
    return tools.dispatch(approval.tool_name, run_or_registry, **approval.tool_args)


if __name__ == "__main__":
    import sys

    cfg = Config.from_env()
    registry = AccountRegistry(cfg)
    db = Database(cfg.saint_db_path)
    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)

    def _print_pending(approval_id, tool_name, tool_args, account):
        print(f"\n[queued approval #{approval_id}] {tool_name} on {account}: {tool_args}\n")

    run = Run.new(cfg, registry, db, on_pending_approval=_print_pending)
    messages: list = []
    print("Saint CLI REPL. Ctrl-D to exit.")
    while True:
        try:
            text = input("> ")
        except EOFError:
            sys.exit(0)
        messages.append({"role": "user", "content": text})
        reply = run_turn(run, client, messages)
        print(reply)
