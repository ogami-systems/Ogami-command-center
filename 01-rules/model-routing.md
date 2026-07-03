---
id: model-routing
type: document
title: Model Routing
status: active
owner: ogami-core
classification: internal
governed-by:
  - 01-rules/security-boundaries.md
  - 01-rules/authoring-standard.md
references:
  - CLAUDE.md
---

# Model Routing

This document defines **which model performs which work**. It is both a cost control and a security control: agents request inference through this routing policy, never by calling models directly.

Its governing principle is the Model & Cost Philosophy in `CLAUDE.md` §5 and the reasoning-depth rule in `CLAUDE.md` §6 — referenced here, not restated. In one line: **match the model tier to the cost of being wrong, then to the cost of the compute.**

---

## Tiers

| Tier | Models | Use for |
|------|--------|---------|
| **Heavy reasoning** | Claude Opus | Architecture, security, workflow design, client-data boundaries, approval logic, difficult debugging, irreversible decisions |
| **Standard reasoning** | Claude Sonnet | Drafting, summarization, audits, most workflow steps, day-to-day judgment |
| **Fast / bulk** | Groq Llama 70B · Groq Qwen · Groq GPT OSS | High-volume classification, simple extraction, routine formatting, cheap parallel work |
| **Cross-check (alternate)** | GPT-5.5 · OpenAI Codex CLI (code review) | Independent second opinion on high-stakes output; diversity when one model's bias is a risk. For code specifically, Codex CLI is invoked directly (`codex exec review`), not roleplayed by another tier — the value is a genuinely separate model, not a persona. |

Tiers map to decision cost: the higher the cost of being wrong (`CLAUDE.md` §6 — reversibility, security, financial, blast radius), the higher the tier required.

---

## Routing rules

1. **Default to the lowest tier that does the task well.** Do not spend Opus on formatting or Llama on architecture.
2. **Escalate by decision cost, not task size.** A one-line change to a security boundary routes to Heavy; a large but reversible doc cleanup routes to Standard or Fast.
3. **High-stakes action classes require Heavy reasoning.** Any step whose action class is **Financial**, **Credential**, **Destructive**, or **Administrative** (`security-boundaries.md`) MUST be reasoned at the Heavy tier and MUST NOT run on an unapproved tier.
4. **No direct model calls.** Agents request inference through this policy. The model tier an agent may use is declared in its definition and bounded by this table.
5. **Cross-check on irreversible or high-blast-radius output.** Route a second pass through the Cross-check tier before committing to it.

---

## Mapping by action class

| Action class | Minimum tier |
|--------------|--------------|
| Read | Fast or Standard |
| Draft | Standard |
| Communicate | Standard (Heavy if stakes are high) |
| Financial | Heavy |
| Credential | Heavy |
| Destructive | Heavy |
| Administrative | Heavy |

When a step spans multiple classes, the most restrictive class sets the minimum tier — mirroring the "most restrictive class governs" rule in `security-boundaries.md`.

---

## Current consumers

- `02-agents/repo-steward.md` — read-only audit; routes to **Standard** (Sonnet) by default, escalating to **Heavy** only when asked to judge the severity of architectural drift.
- `02-agents/ogami-operator.md` — implementation; routes to **Standard** (Sonnet) by default, escalating to **Heavy** for architecturally significant changes. Its adversarial review step in `03-workflows/build-and-review.md` routes to **Cross-check** (Codex CLI) — the first real consumer of that tier.
