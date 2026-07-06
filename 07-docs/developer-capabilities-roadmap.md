---
id: developer-capabilities-roadmap
type: document
title: Developer — Future Implementation Capabilities
status: active
owner: ogami-core
classification: internal
governed-by:
  - 01-rules/authoring-standard.md
  - 01-rules/extension-policy.md
references:
  - 02-agents/ogami-operator.md
---

# Developer — Future Implementation Capabilities

This document lists implementation domains Dev is expected to grow into over time. **It is aspirational and grants no capability by itself** — every item here requires its own separate, explicit change to `02-agents/ogami-operator.md`'s Tool allowlist and, where relevant, OpenClaw's exec-approval configuration (`01-rules/openclaw-runtime-policy.md`) before Dev may actually use it. Naming something here is a statement of intent, not an authorization.

## Relationship to the Decision Hierarchy

`02-agents/ogami-operator.md`'s Decision Hierarchy names two rungs — n8n workflow and MCP server — that belong on this roadmap rather than in current capability, because no integration for either exists yet. This document is where "not yet" gets tracked until it becomes "now," at which point the change moves to the agent document and its Tool allowlist, not here.

## Future implementation domains

- **n8n** — workflow automation platform; would let Dev compose integrations declaratively rather than writing bespoke glue code for every automation. No n8n instance or access is currently configured.
- **MCP servers** — Model Context Protocol servers; would let Dev expose or consume structured tool interfaces beyond what's directly wired into this session. No MCP server-building or -hosting capability is currently granted.
- **Python** — general-purpose implementation language for scripts, services, and automation.
- **TypeScript / JavaScript** — for web-facing or Node-based implementations.
- **Docker** — containerized services, per `01-rules/runtime-environment.md`'s existing decision rule for when a runtime boundary is warranted.
- **OpenClaw agents** — designing additional OpenClaw-supervised agents beyond Dev itself.
- **Saint workflows** — integrating with or extending Saint's existing capabilities rather than duplicating them (Decision Hierarchy rung 4).
- **PostgreSQL** — for implementations that outgrow file-based or SQLite storage.
- **SQLite** — for lightweight, embedded persistence needs.
- **REST APIs** — designing and implementing HTTP API interfaces.
- **Webhooks** — event-driven integration triggers.
- **GitHub Actions** — CI/CD automation.
- **Google Workspace APIs** — would require credential access Dev does not hold today; Saint currently owns Google OAuth (`02-agents/saint.md`) — any Dev use would need its own explicit Credential-class authorization, not a borrowed one.
- **CLI automation** — command-line tooling and scripting beyond what's used today.
- **Existing SaaS integrations** — connecting to third-party services already in use elsewhere in the stack.

## What this document is not

Not a tool grant. Not an approval-policy change. Not a commitment to build any of the above on any particular timeline. It exists so "what should Dev eventually be able to do" is written down somewhere durable, separate from "what Dev is allowed to do right now" (`02-agents/ogami-operator.md`'s Tool allowlist) — mixing the two in one place risks exactly the confusion `01-rules/security-boundaries.md`'s least-privilege rule warns against.
