# Saint

Michael's personal executive-assistant agent: a Claude API brain with a Telegram
interface, connected to two separate Google account contexts (`personal_google`
and `ogami_google`). Runs first on a MacBook via a plain virtualenv (for easy
interactive OAuth testing), then moves unchanged to a Mac mini via Docker for
steady-state operation.

See [`SETUP.md`](SETUP.md) to get it running. See
[`../02-agents/saint.md`](../02-agents/saint.md) for the identity/policy doc
that governs what Saint is allowed to do.

## What's here (Phase A — foundation)

- **Dual Google accounts, no shared OAuth app.** `personal_google` and
  `ogami_google` each have their own Google Cloud OAuth client and their own
  token file (`accounts/google_account.py`, `accounts/registry.py`). Tools take
  an `account` parameter rather than being duplicated per account.
- **Gmail send is structurally impossible.** Only the `gmail.modify` scope is
  ever requested; no send/compose tool exists anywhere in this codebase.
- **Consequential actions are gated.** Calendar create/delete and Sheets append
  never execute from the model's tool-call loop — they're queued in SQLite and
  require an explicit Approve/Reject via a Telegram inline keyboard
  (`tools/__init__.py`'s `CONSEQUENTIAL` table, `agent.py`'s interception,
  `telegram_bot.py`'s callback handler). Approvals and their audit trail survive
  a bot restart.
- **Model tiers + budget governor.** `agent.py` routes between Sonnet 5
  (Standard) and Opus 4.8 (Heavy), forces Heavy tier for the reasoning step that
  decides to call a Destructive-class tool, tracks daily spend in SQLite, and
  exposes a capped `escalate_model` self-escalation tool.
- **Memory stays plain files.** `data/memory/` — nothing product-related lives
  in SQLite; that's operational state only (approvals, audit log, model usage).

## Directory layout

```
saint/
├── main.py              # entrypoint — the only thing Docker runs
├── config.py            # .env loading, typed Config
├── agent.py              # Claude tool-call loop, tiers, budget, escalation
├── db.py                 # SQLite: approvals, audit_log, model_usage
├── scheduler.py          # AsyncIOScheduler, daily briefing job (stub)
├── telegram_bot.py        # PTB v21 app, owner allowlist, approval callbacks
├── authorize.py          # one-time OAuth consent script — never in Docker
├── accounts/              # GoogleAccount + AccountRegistry
├── tools/                 # gmail/calendar/drive/sheets/tasks tool modules
├── data/memory/           # plain-file memory, human-readable/editable
├── secrets/                # OAuth tokens land here at runtime, gitignored
├── Dockerfile, docker-compose.yml, .dockerignore
└── .env.example
```

## Explicitly out of scope for this build

The Growth Packet, wind-down/weekly-review scheduler jobs, weather/Notion/
package-tracking tools, self-improving news filter, quote/devotional seeding,
and the portfolio-tracking Sheet template are all future work layered on this
foundation — not part of Phase A.

## Future architecture directions (not yet implemented)

**Trust-boundary approval model.** Michael has agreed in principle (2026-07-06)
to eventually replace the current consequence/risk-based gating (each write
individually classified by its actual real-world risk — see `tools/__init__.py`'s
`CONSEQUENTIAL` table and `GMAIL_ARCHITECTURE.md`) with a simpler trust-boundary
model:

> Saint can freely observe the outside world.
> Saint can freely manage its own internal state.
> Saint asks before changing anything outside itself.

Concretely: reads always ungated; writes to Saint's own internal state (memory,
its SQLite db, logs, The Mine once built, caches) always ungated; any write to
an external system (Gmail, Calendar, Docs, Sheets, Tasks, and future Notion/CRM/
API integrations) gated by default. This is a generalization of the same
default-deny-plus-explicit-override pattern already used for Gmail's
`SafeGmailService` — applied to the whole tool surface instead of one service.

Adopting it would gate three currently-ungated tools that don't touch a
particularly risky surface (`docs_create`, `tasks_create`, `tasks_complete`) —
a deliberate, bounded friction tradeoff in exchange for a gating rule that
never needs re-litigating per tool and is robust to sloppy future additions.
Rollout, if and when undertaken: apply the boundary rule to all new
external-write tools going forward with zero disruption to what exists, then
separately and explicitly decide the fate of those three existing exceptions —
not a passive side effect of adopting the philosophy. Scoped/bulk approvals
(e.g. "approve all task creation for this meeting") are a candidate future
mechanism to recover usability without diluting the simple rule, but are a
separate feature with their own security surface, deserving their own design
pass when actually built.

Not implemented. No code or `CONSEQUENTIAL` table changes have been made under
this direction — it is a documented intent to revisit, not a current policy.
