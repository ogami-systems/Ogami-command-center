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
