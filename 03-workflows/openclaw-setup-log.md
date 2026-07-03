---
id: openclaw-setup-log
type: workflow
title: OpenClaw Setup
status: active
owner: ogami-core
classification: internal
governed-by:
  - 01-rules/security-boundaries.md
  - 01-rules/authoring-standard.md
  - 01-rules/openclaw-runtime-policy.md
references:
  - 02-agents/ogami-operator.md
---

# OpenClaw Setup

The one-time procedure that applies `01-rules/openclaw-runtime-policy.md` to live OpenClaw configuration: registers the `ogami-operator` agent and writes its exec-approval policy. Action class **Administrative** (`security-boundaries.md`) — run deliberately via reviewed commands, never silently by an agent at runtime.

## Trigger

On demand, once per machine (MacBook and Mac mini each run this independently — see `openclaw-runtime-policy.md` § Environments). Re-run after any change to the exec-approval design below.

## Schema note

`openclaw approvals set --file` accepts a JSON file of this shape (confirmed from OpenClaw's own type definitions, `exec-approvals.d.ts`, not guessed):

```
{
  version: 1,
  defaults?: { security: "deny"|"allowlist"|"full", ask: "off"|"on-miss"|"always", askFallback: "deny"|"allowlist"|"full" },
  agents?: { "<agentId>": { security, ask, askFallback, allowlist: [{ pattern, argPattern? }] } }
}
```

`allowlist.pattern` matches a **resolved executable path** (e.g. a `git` binary), not a full command line — `argPattern` narrows which arguments are permitted for that binary. This matters: allowlisting the `git` binary alone would allow *every* git subcommand, including destructive ones. Every git allowlist entry below therefore carries an `argPattern` restricting it to safe subcommands only.

## Steps

| # | Step | Action class | Gate |
|---|------|--------------|------|
| 1 | Confirm no `~/.openclaw/exec-approvals.json` already governs a conflicting agent (`openclaw approvals get --json`) | Read | none |
| 2 | Register the agent: `openclaw agents add ogami-operator --workspace ~/Developer/Ogami --model anthropic/claude-sonnet-4-6` | Administrative | human runs this command directly; not run by an agent |
| 3 | Write the exec-approval policy below to a local file and apply: `openclaw approvals set --file exec-approvals.ogami-operator.json` | Administrative | human runs this command directly |
| 4 | Install a pre-commit secret scan in each target repo the Operator will work in (rejects commits containing credential-shaped strings), per `openclaw-runtime-policy.md` § Secrets | Administrative | human runs this command directly |
| 5 | Verify: `openclaw approvals get --json` shows tier 1 patterns resolving without a prompt, `git commit`/`git push` resolving to a live prompt, and a deliberately dangerous command (`rm -rf`, `git push --force`, `sudo`) refused outright by the Claude Code layer before OpenClaw is even asked | Read | none |

## Exec-approval policy (step 3 content)

```json
{
  "version": 1,
  "defaults": {
    "security": "deny",
    "ask": "always",
    "askFallback": "deny"
  },
  "agents": {
    "ogami-operator": {
      "security": "allowlist",
      "ask": "on-miss",
      "askFallback": "deny",
      "allowlist": [
        { "pattern": "*/git", "argPattern": "^(status|diff|show|log|add|worktree) " },
        { "pattern": "*/rg" },
        { "pattern": "*/node", "argPattern": "^--test" },
        { "pattern": "*/npm", "argPattern": "^(test|run lint|run build) " }
      ]
    }
  }
}
```

Everything else for `ogami-operator` — including `git commit` and `git push`, deliberately absent from `argPattern` above — falls through to `ask: "on-miss"`: a live prompt, resolved by a human, failing closed (`askFallback: "deny"`) if unanswered. This implements tiers 1 and 2 of `openclaw-runtime-policy.md`.

**Tier 3 (hard approval) is not expressed in this file** — OpenClaw's allowlist schema has no per-pattern deny, only allow. Destructive/Credential/Administrative shapes (`rm -rf`, `sudo`, `git reset --hard`, `git push --force`, reads under `~/.ssh` or `~/.aws`, edits to `01-rules/`) are hard-blocked one layer up, at the Claude Code CLI layer OpenClaw's `claude-cli` agent runtime wraps: a `permissions.deny` Bash-pattern list in `~/.claude/settings.json`, confirmed to support explicit deny patterns. That layer enforces independently of OpenClaw's own supervision, so these commands are never even attempted — not just unapproved. The Operator's own instructions (`02-agents/ogami-operator.md`, and inlined in `.claude/workflows/build-and-review.js` since workflow scripts cannot read files at runtime) additionally forbid attempting them at all, as a first line of defense.

## Inputs and outputs

- **Input:** this document, plus the machine it's being run on (MacBook or Mac mini).
- **Output:** a registered `ogami-operator` OpenClaw agent and a live `~/.openclaw/exec-approvals.json` matching the policy above. No repository state changes.

## Failure and escalation

- If `openclaw approvals get --json` after step 3 doesn't match the intended policy, halt before running anything through the new agent and re-diff the applied file against this document.
- Any allowlist pattern that turns out too broad during dry-run testing (`03-workflows/build-and-review.md`) is tightened here first, then reapplied — never loosened elsewhere to route around it.

## Run log

### 2026-07-03 — MacBook (dev)

- `openclaw agents add ogami-operator --workspace ~/Developer/Ogami --model anthropic/claude-sonnet-4-6 --non-interactive` — **succeeded**. Agent dir: `~/.openclaw/agents/ogami-operator/agent`.
- Workspace confirmed via `openclaw agents list`: `~/Developer/Ogami` — not `~/Developer`, not `~/ogami-command-center`.
- `openclaw approvals set --file ~/ogami-command-center/03-workflows/exec-approvals.ogami-operator.json` — **succeeded**. Verified via `openclaw approvals get --json`, not just the command's own output:
  - **Default policy (any agent other than `ogami-operator`) is now locked down**: `security=deny, ask=always, askFallback=deny` → effective mode `deny`. Before this run, no `exec-approvals.json` existed at all and OpenClaw's baseline was wide open (`security=full, ask=off`); this run closed that gap for every agent, not only `ogami-operator`.
  - `ogami-operator` resolves to `security=allowlist, ask=on-miss, askFallback=deny` → effective mode `ask`. All 4 allowlist entries confirmed stored with `argPattern` intact (`git` restricted to status/diff/show/log/add/worktree, `rg`, `node --test`, `npm test`/`lint`/`build`). Everything else — including `git commit` and `git push` — falls to a live, fail-closed prompt, exactly as designed in the policy above.
- **Warning surfaced by `agents add`, pre-existing, not caused by this change:** `plugins.allow is empty; discovered non-bundled plugins may auto-load: brave, codex, groq`. Not remediated as part of this run — flagged here for a future decision on whether to pin `plugins.allow` explicitly.

**Undo, if needed:**
- Agent: `openclaw agents delete ogami-operator --force`
- Approval policy: `rm ~/.openclaw/exec-approvals.json` — **note:** since no prior policy file existed, this restores OpenClaw's original wide-open baseline (`security=full, ask=off`) for *every* agent, not just a removal of the `ogami-operator` entry. To keep the locked-down default while removing only `ogami-operator`, apply a replacement file that keeps `defaults` and omits the `agents.ogami-operator` block, via the same `openclaw approvals set --file` command.

### 2026-07-03 — OpenClaw-supervised gate test (MacBook, dev)

Distinct from the dry-run above, which exercised `build-and-review.js` through Claude Code's native Agent/Workflow tools directly — that path never goes through OpenClaw's exec-approvals at all. This test specifically targeted the remaining untested gate: `ogami-operator` running as an OpenClaw-*supervised* agent (`openclaw agent --agent ogami-operator`), where `exec-approvals.json` actually intercepts its exec calls.

- **Attempted, scoped to stop before any commit** — the first version of this test scripted an explicit `git commit` step (intending only to observe it get blocked); the harness correctly refused to run it, since a scripted commit attempt is indistinguishable from "commit this" and directly conflicts with the standing "do not commit" boundary. Re-scoped to stop after `git add`, no commit instruction at all.
- **Policy triggered.** The very first step (`git worktree add ...`) was intercepted by OpenClaw's exec-approval system and denied. It never ran.
- **Failed closed.** This was a one-shot, non-interactive call with no human watching an approval channel. Policy is `ask=on-miss` / `askFallback=deny`: with nobody to answer the ask, it resolved to deny rather than hanging or defaulting to allow — the fail-closed behavior working as designed.
- **No files, worktrees, or branches were created.** Confirmed via direct filesystem and `git worktree list`/`git branch` inspection after the run, not just the agent's self-report.
- **Live human approval prompt not yet tested.** This run had no one actively watching an OpenClaw approval channel to answer the ask — that path (a human actually seeing and resolving a live prompt) remains unverified.
- **Allowlist `argPattern` did not match as intended.** `git worktree add` was meant to be tier-1 (auto-run, no prompt) per the `argPattern` scoped to `status|diff|show|log|add|worktree`. Instead it received the same treatment as an unlisted command. Root cause not yet diagnosed — plausibly whether `argPattern` is matched against the arguments alone or the full command line including `git` itself.
- **Assessment: the remaining issue is allowlist tuning, not core safety.** The gate's failure mode is over-blocking (denies things intended to be frictionless), never under-blocking (nothing unapproved got through). Deliberately not debugged or widened as part of this entry — allowlist tuning is separate follow-up work, tracked here rather than acted on now.
