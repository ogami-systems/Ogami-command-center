---
id: build-and-review
type: workflow
title: Build and Review
status: active
owner: ogami-core
classification: internal
governed-by:
  - 01-rules/security-boundaries.md
  - 01-rules/authoring-standard.md
  - 01-rules/extension-policy.md
  - 01-rules/model-routing.md
  - 01-rules/openclaw-runtime-policy.md
references:
  - 02-agents/ogami-operator.md
---

# Build and Review

A repeatable process that implements a requested code change via the `ogami-operator` agent, subjects it to an adversarial review from a genuinely independent model (the Cross-check tier, `model-routing.md`), and gates every state-changing step behind human approval per `openclaw-runtime-policy.md`. This is the current sole consumer of the Cross-check tier.

## Trigger

On demand: a human requests a change to a target repository, with enough detail for the Operator to act. Never runs unattended without a reachable human approver (`openclaw-runtime-policy.md` environments).

## Steps

| # | Step | Action class | Gate |
|---|------|--------------|------|
| 1 | Provision a fresh `git worktree` for the target repository | Read/setup | none |
| 2 | `ogami-operator` implements the requested change in the worktree | Draft | none |
| 3 | Route the uncommitted diff to the Cross-check tier via `codex exec review --uncommitted --sandbox read-only` | Draft | none — Codex runs read-only; it cannot alter the worktree |
| 4 | If Codex reports issues, Operator revises and returns to step 3 | Draft | bounded retry: 3 rounds, then halt and escalate (`security-boundaries.md`) |
| 5 | Compile the diff, Codex's findings, and the Operator's summary into a report | Draft | clearly marked draft; no external send |
| 6 | Human reviews the report and approves or rejects the commit | Draft → Commit | **explicit approval required** (`openclaw-runtime-policy.md`) |
| 7 | Human reviews and approves the push to the remote | Communicate | **explicit approval required** (`openclaw-runtime-policy.md`) |

Any exec call the Operator attempts outside this table (deletes, resets, `sudo`, secret access, edits to `01-rules/`) is **hard-denied** per `openclaw-runtime-policy.md` — it never reaches a human prompt.

## Inputs and outputs

- **Input:** a target repository, a description of the requested change, and a recorded Git SHA the worktree is based on.
- **Output:** either (a) a committed and pushed change with a recorded `approval_id` for both the commit and the push, or (b) a halted run with a findings report and no repository state changed outside the discarded worktree.

## Failure and escalation

- A rejected commit or push halts the run; the worktree is preserved until the human decides whether to redirect the Operator or discard it.
- Exhausting the step-4 retry limit without a clean Cross-check review halts the run and escalates with the full finding history — the Operator does not force a commit past unresolved findings.
- On repeated tool failure (default: 3) or ambiguity, halt and notify a human (`security-boundaries.md`).
