---
id: openclaw-runtime-policy
type: document
title: OpenClaw Runtime Policy
status: active
owner: ogami-core
classification: internal
governed-by:
  - 01-rules/security-boundaries.md
  - 01-rules/authoring-standard.md
references:
  - 01-rules/runtime-environment.md
  - 01-rules/model-routing.md
  - 01-rules/extension-policy.md
---

# OpenClaw Runtime Policy

This document answers one question: **how does OpenClaw's exec-approval mechanism concretely enforce the action classes defined in `security-boundaries.md`, on which machines?**

It is not a new law. Every rule below traces back to an existing action class or trust zone. `security-boundaries.md` deliberately stays abstract — any runtime could enforce it. This is the one concrete binding to OpenClaw, the runtime this constitution has chosen. Like every `01-rules/` document, client overlays may tighten it, never loosen it.

---

## Action class → OpenClaw enforcement

| Action class (`security-boundaries.md`) | Approval tier | OpenClaw mechanism |
|---|---|---|
| **Read** | None required | `approvals allowlist` glob patterns for read/search tools (e.g. file read, grep, `git status`, `git diff`) |
| **Draft** — file edits inside an active worktree | None required while confined to the worktree | The OpenClaw agent's workspace boundary + the workflow always operating inside a freshly provisioned `git worktree`, never the primary checkout |
| **Draft → Commit** — promoting a draft into durable Git history | **Explicit approval** | `git commit` exec pattern set to `ask=on`; a live prompt the human resolves in the moment |
| **Communicate** — `git push` to GitHub | **Explicit approval** | `git push` exec pattern set to `ask=on` |
| **Financial / Credential / Destructive / Administrative** | **Hard approval** | Pattern is **absent from the allowlist and explicitly denied** — never resolvable via a live prompt |

When one exec call spans multiple classes, the most restrictive class governs (mirrors `security-boundaries.md`).

---

## Two approval tiers, not one

This repository's action classes map to two distinct enforcement mechanisms in OpenClaw, not one:

1. **Explicit approval** (`ask=on`) — the agent may request the action; OpenClaw pauses and presents a live prompt; a human approves or rejects it in the moment. Used for Draft→Commit and Communicate.
2. **Hard approval** (deny by default) — the pattern is not in the allowlist at all, and `askFallback` resolves to deny. The agent cannot even surface a prompt for it. A human must edit the allowlist **out-of-band, before the run**, to permit it. Used for Financial, Credential, Destructive, and Administrative patterns (deletes, resets, `sudo`, secret access, system-level config changes).

Hard approval is strictly stronger than explicit approval: a rejected explicit-approval prompt can be retried next run if circumstances change; a hard-denied pattern requires a deliberate configuration change first.

---

## Secrets

`security-boundaries.md` rule #1 already forbids secrets in Git. This document adds the enforcement mechanism:

- A pre-commit secret-scan step is part of the one-time setup (`03-workflows/openclaw-setup-log.md`) and must reject a commit containing credential-shaped content before it ever reaches `git commit`.
- No OpenClaw config file committed to this repository may contain a live token, password, or key — gateway tokens and similar live only in `~/.openclaw/` (Secret store trust zone), never in `01-rules/`, `02-agents/`, `03-workflows/`, or any tracked file.

---

## Workspace scope

The OpenClaw `--workspace` boundary is set to a single directory: the target repository the Operator is actually working in, named explicitly (`~/Developer/Ogami` today) — **not** `~/Developer` (every project on this machine, most of which have nothing to do with Ogami) and **not** `~/ogami-command-center` (the control plane; rule 7 already forbids the Operator from self-modifying policy, so it should not even have read/write reach into the repo that defines its own constraints). Scope expands one named repository at a time, as a deliberate decision, when a real second target exists — mirroring the Rule of Two in `extension-policy.md` rather than granting reach ahead of need.

## Environments

| Environment | Machine | Role | Approval strictness |
|---|---|---|---|
| **MacBook** | Michael's MacBook Pro | Development and testing | Full policy above applies; no loosening for being "just dev." |
| **Mac mini** | Mac mini | Production, always-on | Same policy, plus: because it runs unattended, a human approver must be reachable (an OpenClaw channel/notification) for any gated prompt. An always-on box MUST NOT auto-approve a gated action merely because no one is watching. |

**Rule: environment changes *where* things run, never *whether* gates apply.** This is the "tighten, never loosen" principle from `extension-policy.md` §7, applied across physical environments rather than client tenants. Production being always-on is a reason for *more* caution around reachability of the human approver, never a reason to relax a gate.

---

## Relationship to other components

| Document | Relationship |
|---|---|
| `security-boundaries.md` | Defines the action classes and their abstract approval requirements; this document supplies the concrete OpenClaw mechanism for each. |
| `model-routing.md` | Independent of approval tier — routing decides *which model reasons*, this document decides *what a human must approve*. Both apply to the same step. |
| `runtime-environment.md` | Covers Docker as the portable execution boundary; this document covers OpenClaw as the exec-approval boundary. Distinct responsibilities, both part of the Runtime trust zone. |
| `extension-policy.md` | This document is justified under §4's explicit exception: a security boundary is necessary even with one current consumer. |
| `02-agents/ogami-operator.md` | The first and current consumer of this policy. |
| `03-workflows/build-and-review.md` | The workflow whose commit/push/destructive-action steps this policy gates. |
| `03-workflows/openclaw-setup-log.md` | The one-time procedure that applies this policy to live OpenClaw configuration. |

---

## Summary

OpenClaw enforces what `security-boundaries.md` already decided: free inspection, worktree-scoped drafts, explicit human approval before a draft becomes a commit or a commit becomes a push, and hard, out-of-band-only approval for anything destructive, credentialed, financial, or administrative. The physical machine changes only where this runs — the gates are identical on a MacBook and an always-on Mac mini.
