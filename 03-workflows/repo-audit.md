---
id: repo-audit
type: workflow
title: Repository Audit
status: active
owner: ogami-core
classification: internal
governed-by:
  - 01-rules/security-boundaries.md
  - 01-rules/authoring-standard.md
  - 01-rules/extension-policy.md
references:
  - 02-agents/repo-steward.md
---

# Repository Audit

A repeatable, read-only process that runs the `repo-steward` agent to check the repository against the constitution and produce a findings report. Every step is action class **Read**, except the final report, which is a **Draft** for human review. No step changes repository state.

## Trigger

On demand, or on a schedule. Runs against the repository at a specific Git SHA, which the report records.

## Steps

| # | Step | Action class | Gate |
|---|------|--------------|------|
| 1 | Inventory all artifacts and their `type` from frontmatter | Read | none |
| 2 | Verify every cross-reference resolves to an existing file | Read | none |
| 3 | Verify frontmatter and required sections per `authoring-standard.md` | Read | none |
| 4 | Verify every `status: stub` states a contract; flag bare `TODO` | Read | none |
| 5 | Detect drift/bloat per `extension-policy.md` §5 (orphans, duplication, folder mismatch) | Read | none |
| 6 | Compile findings into a clearly-marked draft report | Draft | marked draft; no external send |

## Inputs and outputs

- **Input:** the repository at a recorded Git SHA.
- **Output:** a findings report listing each issue, its location, the rule it violates, and a recommended remedy. The report is advisory only.

## Failure and escalation

- The workflow never edits or fixes anything; remediation is a separate, human-approved action.
- On repeated tool failure (default: 3) or ambiguity, the run halts and notifies a human (`security-boundaries.md`).
