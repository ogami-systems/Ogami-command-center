# Authoring Standard — The Grammar of Every Artifact

This document defines the **form** every artifact in the repository must take: its structure, metadata, references, voice, and level of detail.

It defines **form, not policy.** It does not decide *whether* to create an artifact (`extension-policy.md`), *what is safe* (`security-boundaries.md`), *whether it needs a container* (`runtime-environment.md`), or *how we reason and communicate* (`CLAUDE.md`). Where a rule about content already exists elsewhere, this document **references it, never restates it.**

It is the last foundational governance document before executable capabilities. Like every `01-rules/` document, client overlays may tighten it, never loosen it.

---

## Why a grammar exists

Every artifact here is read by **two audiences at once**: humans who must understand it, and AI agents (OpenClaw, Claude) who must parse and act on it. A shared grammar is what lets both read any file reliably without re-learning its shape. Consistency *is* the maintainability strategy.

Five principles govern all authoring:

1. **Write for human and machine simultaneously.** Structured metadata at the top; clear prose below.
2. **One artifact, one responsibility.** (The test lives in `extension-policy.md` §1 — not repeated here.)
3. **Single source of truth.** Every fact lives in exactly one file. Everywhere else **links**. Never copy a rule; reference it.
4. **Say *what*, *why*, and *constraints* — reserve *how* for implementation artifacts.**
5. **Stable identity, evolving content.** An artifact's `id` and purpose are stable; its body changes through Git.

---

## Universal frontmatter

Every authored artifact begins with YAML frontmatter. This is what makes the repository machine-loadable.

```yaml
---
id: ogami-operator            # stable kebab-case slug; never changes
type: agent                   # document | prompt | agent | workflow | spec | plan | service | client-overlay
title: Ogami Operator
status: draft                 # stub | draft | active | deprecated
owner: ogami-core             # who is responsible (team, person, or "ogami-core")
classification: internal      # per security-boundaries.md data classification (referenced, not redefined)
governed-by:                  # the documents this artifact must obey
  - 01-rules/security-boundaries.md
  - 01-rules/authoring-standard.md
references:                   # other artifacts this one points to (optional)
  - 01-rules/model-routing.md
---
```

Rules:

- `status: stub` is permitted, but a stub MUST still state its intended contract in the body (per `extension-policy.md` §5 — no bare `TODO`).
- `classification` uses the levels defined in `security-boundaries.md`; it is not redefined here.
- Runtime artifacts (agent, workflow, service) MUST list every governing document in `governed-by`. This makes inheritance explicit and auditable.

---

## Cross-references

- Reference other files by **repository-relative path in backticks**: `` `01-rules/security-boundaries.md` ``.
- **Link, do not duplicate.** If a fact is defined elsewhere, point to it. Duplicated rules drift apart and become contradictions.
- An artifact declares what governs it in `governed-by`; it should not re-explain those governing rules in prose.
- A reference MUST resolve to a file that exists. Dangling references are drift (`extension-policy.md` §5).

---

## Explanation vs. implementation, by artifact type

How much *why* versus *how* belongs in a file depends on its type. Use unambiguous modal verbs in normative statements — **MUST / MUST NOT / SHOULD / MAY** — so both humans and agents read requirements without guessing.

| Type | Contains | Does **not** contain | Required body sections |
|------|----------|----------------------|------------------------|
| **Document / policy** | The *what* and *why*; rules, decisions, rationale | Implementation detail; step-by-step procedure | Purpose · the rules/decisions · relationship to other docs |
| **Prompt** | Role, task, constraints, required output format | Policy rationale (link it); business explanation | Role · task · constraints · output format |
| **Agent** | Identity, responsibilities, tool allowlist, model tier, forbidden actions, escalation rules | Step logic (that's a workflow); reasoning narrative | Identity · responsibilities · tool allowlist · model tier · forbidden actions · escalation |
| **Workflow** | Ordered steps, each with action class, gates, inputs/outputs | Role identity; model-by-model reasoning | Trigger · steps (with action class + gates) · inputs/outputs · failure/escalation path |
| **Spec** | The *what* and acceptance criteria | The *how*; chosen implementation | Goal · requirements · constraints · acceptance criteria |
| **Implementation plan** | Ordered *how* steps | Re-justification of the *why* (link the spec/decision) | Reference to spec · ordered steps · verification |
| **Service** | Interface/contract, lifecycle, dependencies, runtime boundary | Source code (that lives in code) | Contract · lifecycle · dependencies · runtime boundary (`runtime-environment.md`) |
| **Client overlay** | Only the *deltas* that tighten core, scoped to one `client_id` | Any restatement or loosening of core | Client id · tightened constraints only |

---

## Distinctions the grammar must keep clear

**Prompt vs. policy.** A **policy** is a durable, normative *rule* that governs behavior and changes only through governance. A **prompt** is an operational *instruction to a model* to perform a task — a reusable building block invoked at runtime, optimized for model performance, free to iterate. A prompt may *reference* a policy; it never *defines* one. Policies say what is allowed; prompts direct work within those limits.

**Workflow vs. agent.** An **agent** is a *who* — a persistent role with identity, judgment, a tool allowlist, and a model tier. A **workflow** is a *how* — an ordered process of steps with gates and action classes. Workflows invoke agents; agents do not contain process logic. If you are writing steps, it's a workflow; if you are defining a role, it's an agent.

---

## Writing standards (clarity · maintainability · AI readability)

- **Front-load purpose.** The first line states what the file is and the one question it answers.
- **One `#` H1 title. Predictable `##` sections. Shallow nesting.** Avoid headings deeper than `###`.
- **Prefer tables and lists for anything enumerable** — they are scannable by humans and parseable by machines.
- **Short, declarative sentences.** Define a term once; link to the glossary when one exists rather than redefining.
- **Use canonical terms consistently.** Same concept, same word, every file.
- **Normative statements use MUST / MUST NOT / SHOULD / MAY.** Remove ambiguity from anything an agent must obey.
- **Mark examples as illustrative, not normative.**
- **Honest status.** A stub declares its contract; a deprecated file points to its replacement.

---

## What must never appear in any artifact

- Secrets or credentials of any kind (`security-boundaries.md`).
- Restricted or client-confidential data in core/platform files (`security-boundaries.md` classification).
- A duplicated copy of a rule defined elsewhere — link instead.
- Implementation detail inside a policy document, or policy rationale buried inside code.
- A reference to a file that does not exist.
- A bare `TODO` with no stated contract.

---

## How artifacts evolve

- **Identity is stable; content is versioned in Git.** Change the body, not the `id`.
- **Edit the single source.** Never fork a file to avoid editing the original — that creates duplication and drift.
- **Deprecate, don't silently delete,** anything other files reference: set `status: deprecated` and link the replacement, then remove references before deletion.
- Amendment authority lives in `CLAUDE.md` §9 (constitution) and `extension-policy.md` (growth) — referenced here, not repeated.

---

## Relationship to the rest of the constitution

| Document | Relationship |
|----------|--------------|
| `CLAUDE.md` | Source of the clarity-over-convenience ethos; this is its artifact-level expression. |
| `extension-policy.md` | Decides *whether* and *what* to create (the artifact-type ladder); this decides *how* the chosen artifact is written. |
| `security-boundaries.md` | Supplies the `classification` levels and the secrets/data rules that frontmatter and content must honor. |
| `runtime-environment.md` | Service/runtime artifacts must declare their runtime boundary; this requires that declaration. |

---

## Summary

Every artifact: structured frontmatter, one responsibility, single source of truth, the right *what/why/how* ratio for its type, unambiguous normative language, resolving references, and honest status. Form is consistent so both people and agents can read any file on sight. This is the grammar; the constitution is now able to produce executable capabilities.
