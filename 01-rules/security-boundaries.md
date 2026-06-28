# Security Boundaries

These are the non-negotiable rules for the Ogami operating system.

Every agent, workflow, runtime, tool integration, and client overlay must comply with this document. Client-specific rules may only **tighten** these boundaries — never weaken them.

This file applies to all companies Ogami runs. Client facts, domain logic, and experiments belong in `04-clients/<client-id>/`, not here.

---

## Purpose

Ogami is an AI-native operating system. Agents will read data, make decisions, and eventually take actions in the real world. Without explicit security boundaries, automation becomes unpredictable and unsafe.

This document defines:

- what agents may and may not do
- how client data is isolated
- when humans must be involved
- how the system must behave when uncertain

When any rule conflicts with convenience, **this document wins**.

---

## Trust Zones

Ogami components operate in distinct zones. Data and authority flow according to these boundaries.

| Zone | What it holds | Trust level |
|------|---------------|-------------|
| **Control plane** | This repository — rules, agents, workflows, prompts, curated memory | Highest integrity; changes require human review via Git |
| **Runtime** | OpenClaw and execution environment — loads definitions, runs workflows | Executes policy; does not define policy |
| **Tools & integrations** | External APIs, browsers, file systems, payment systems | Highest risk; side effects originate here |
| **Secret store** | API keys, credentials, tokens | Never in Git; injected at runtime only |
| **Event log** | Append-only record of runs, steps, tool calls, approvals | Audit evidence; lives outside Git |
| **Client memory** | Durable facts scoped to one `client_id` | Isolated per tenant |
| **Platform memory** | Curated OS-level decisions and promoted patterns | Client-agnostic; no raw client PII |
| **Human approvers** | Founders, operators, designated client approvers | Final authority for gated actions |

Agents may read from zones their role permits. They may write only where explicitly allowed. They may never bypass a zone boundary.

---

## Non-Negotiable Rules

1. **No secrets in Git.** Passwords, API keys, tokens, bank credentials, and connection strings live in a secret manager and are injected at runtime. If a secret appears in a commit, treat it as compromised: rotate immediately.

2. **Fail closed.** When policy is unclear, a tool fails, or confidence is below threshold, the system stops and escalates to a human. Never guess on restricted actions.

3. **No silent side effects.** Any action that changes external state (payments, emails, file deletion, account changes) must occur inside an active workflow run, with an audit event recorded before and after.

4. **Client isolation.** Every run is tagged with a `client_id`. Client data, memory, and configuration are scoped to that tenant. One client's data must never appear in another client's context or outputs.

5. **Core before client, security before both.** Ogami core rules apply to all tenants. Client overlays may add constraints; they may not remove core constraints.

6. **Human gates are features, not bugs.** High-stakes actions require explicit human approval by design. Removing a gate requires a change to this document and human review.

7. **Agents do not self-modify policy.** Agents may not edit rules, workflows, prompts, or security boundaries. Proposed changes go through Git and human review.

8. **Least privilege.** Agents receive the minimum tool access required for their role. Default is no tools until explicitly granted.

---

## Action Classes

Every operation falls into one of these classes. The class determines approval and logging requirements.

| Class | Description | Examples | Requirements |
|-------|-------------|----------|--------------|
| **Read** | Observe data without mutation | Fetch records, read files, query status | Log at step level; no approval unless data is highly sensitive |
| **Draft** | Produce output for human review | Draft email, proposed payment batch, summary report | Must be clearly marked as draft; no external send/submit |
| **Communicate** | Send message to external party | Email, SMS, Slack to client contacts | Human approval required before send |
| **Financial** | Move money or commit to payment | ACH, wire, card charge, payment authorization | Human approval required; dual logging; idempotency key mandatory |
| **Credential** | Access or use authentication material | Login to bank, use API key, assume service account | Human approval for first use per session; secrets from secret store only |
| **Destructive** | Delete or irreversibly alter data | Delete records, overwrite files, revoke access | Human approval required; rollback plan documented in workflow |
| **Administrative** | Change system or policy configuration | Edit rules, grant tool access, modify production config | Human approval via Git PR; never at runtime by agents |

When an action spans multiple classes, **the most restrictive class governs**.

---

## Agent Constraints

### Tool access

- Each agent has an explicit **tool allowlist** defined in `02-agents/`.
- Tools not on the allowlist are unavailable — not "discouraged."
- Side-effecting tools require an active `run_id` and valid workflow context.
- Financial and credential tools require a recorded `approval_id` before execution.

### Inference and models

- Agents request inference through the model router (`01-rules/model-routing.md`), not by calling models directly.
- Model routing policy is a security control: high-stakes steps must not use unapproved model tiers.

### Memory access

| Access type | Allowed | Notes |
|-------------|---------|-------|
| Read platform memory | Yes, if role permits | Curated facts only |
| Read client memory | Yes, when `client_id` matches active run | Never cross-tenant |
| Write platform memory | No | Agents propose; humans or promotion workflow commit |
| Write client memory | Propose only | Structured proposals reviewed or auto-accepted per workflow rules |
| Write working memory | Yes, within run scope | Ephemeral; discarded when run completes |

### Prohibited agent behavior

- Executing actions outside an active workflow step
- Fabricating client facts, approvals, or policy exceptions
- Exfiltrating client data to external channels not defined in the workflow
- Chaining tool calls to circumvent approval gates
- Continuing after repeated tool failures without escalation (default: 3 failures → halt and notify human)

---

## Data Handling

### Classification

| Level | Description | Storage | Example |
|-------|-------------|---------|---------|
| **Public** | Safe to share broadly | Git or anywhere | Generic workflow templates |
| **Internal** | Ogami operational data | Git, event log | Architecture decisions, promotion log |
| **Client confidential** | Tenant-specific business data | Client memory store, scoped runtime | Vendor names, approval thresholds, account mappings |
| **Restricted** | PII, financial, credentials | Encrypted stores; minimal retention | Bank account numbers, API keys, SSNs |

### Rules by classification

- **Restricted** data never enters Git, prompts, or platform memory.
- **Client confidential** data never enters platform memory without anonymization and promotion review.
- Event logs record **hashes and summaries** of sensitive inputs/outputs — not raw restricted content.
- Client data at rest is logically partitioned by `client_id`. Physical storage may be shared, but access controls enforce isolation.

---

## Human Escalation

The system must pause and request human input when any of the following occur:

- Policy conflict between core rules and client overlay
- Action class requires approval and none has been granted
- Confidence or validation score below workflow-defined threshold
- Ambiguous instruction that could lead to a restricted action
- Tool returns unexpected or error state after retries
- Attempt to access data outside the active `client_id` scope
- Any behavior that would violate this document

### Escalation format

Escalations must include:

- `run_id`, `workflow_id`, `step_id`, `client_id`
- what the agent intended to do and why
- what blocked progress
- recommended options (never a single forced path on restricted actions)

Humans may approve, reject, or redirect. Rejections are logged and the run halts unless the workflow defines an alternate path.

---

## Violation Response

When a boundary is violated or attempted:

1. **Stop** the current step immediately
2. **Log** a security event with full context (no restricted payload data)
3. **Notify** a human operator
4. **Do not retry** the violating action automatically

Repeated violations from the same workflow or agent configuration trigger a mandatory review before that configuration runs again.

---

## Change Governance

This document is Ogami law. Changes require:

- A pull request with explicit description of what loosens or tightens
- Review by a designated human owner before merge
- A note in the PR if any existing workflow or agent definition must be updated to comply

Loosening a boundary (e.g., removing an approval gate for a financial action) demands stronger justification than tightening one.

Runtime environments must pin to a Git SHA that includes the active version of this document. Runs record which SHA was loaded.

---

## Relationship to Other Components

| Component | How this document governs it |
|-----------|------------------------------|
| `01-rules/extension-policy.md` | Defines how clients tighten — not loosen — these rules |
| `01-rules/model-routing.md` | Model selection as a security and cost control |
| `02-agents/` | Each agent's allowlist and forbidden actions derive from here |
| `03-workflows/` | Steps declare action class and approval gates per this document |
| `04-clients/` | Client overlays inherit all rules here; may add stricter local policy |
| `05-prompts/` | System prompts instruct agents to obey this document |
| `06-memory/` | Memory write rules and classification derive from here |
| Runtime (OpenClaw) | Enforces gates, logging, and fail-closed behavior at execution time |
| Event log | Implements audit requirements defined here |

---

## Summary

Ogami succeeds only if automation is **trustworthy**. Trust comes from clear boundaries, tenant isolation, human gates where stakes are high, and a system that stops rather than guesses.

Everything built after this file — agents, workflows, client overlays, runtime wiring — must point back here.
