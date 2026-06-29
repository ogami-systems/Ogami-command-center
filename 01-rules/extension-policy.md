# Extension Policy — How the Repository Grows

This document answers one question:

> **When should the repository grow, and how should it grow without becoming chaotic?**

It is the evolutionary law of the Ogami Command Center. Every proposal to add a file, folder, agent, workflow, memory system, service, client space, or runtime component is judged against it. Like every `01-rules/` document, client overlays may tighten it, never loosen it.

---

## Prime directive

**Optimize for long-term clarity, not short-term convenience.**

The default answer to "should we add this?" is **no, until it earns its place.** Growth is a cost — every artifact is something future-us must understand, maintain, and keep consistent. Convenience today that creates confusion tomorrow is a bad trade. Avoid overengineering while making future growth predictable.

A useful frame: **Ogami extends by *tightening and reusing*, never by *loosening or duplicating*.** This applies to repository structure (below) and to runtime layers and client overlays (§7) alike.

---

## 1. The tests a new capability must pass

A new artifact is justified only when it passes **all** of these:

1. **Reuse test.** Does something existing already do this, or could it with a small, clean extension? If yes → extend, do not create.
2. **Single-responsibility test.** Can you name its one responsibility in a single sentence with no "and"? If it needs an "and," it is probably two things.
3. **Rule of Two.** Do **two** real, concrete uses exist *today*? One use → inline it where it's needed. Abstractions and shared components are earned by repetition, not anticipated.
4. **Stable-boundary test.** Is its interface understood and likely stable, or are we guessing at a seam we don't need yet? Don't freeze a boundary you can't yet see clearly.
5. **Cost-of-wrong test.** (See `CLAUDE.md` §6.) If creating it wrong is cheap to reverse, bias to action. If it's expensive — a new folder, runtime component, or client space — demand stronger justification.
6. **Owner-and-layer test.** Can you say where it sits in the layer model and what it's responsible for? Orphans with no clear home cause drift.
7. **Policy-exists test.** For anything executable (agent, workflow, service), do the governing policies it must obey already exist? An agent, for example, needs `security-boundaries.md`, `model-routing.md`, and the authoring standard *before* it is created. **Policy before implementation.**

If a proposal fails a test, the answer is usually "extend something, or wait" — not "create it anyway."

---

## 2. Extend an existing component, or create a new one?

**Extend by default.** Extension keeps one source of truth and adds the least surface area.

**Create new only when:**

- extending would force one component to do two unrelated jobs (violates single responsibility), or
- the change would loosen or complicate an otherwise-stable interface, or
- the new thing has a genuinely different lifecycle, owner, trust level, or audience.

**The "and" smell:** if describing the extended component starts requiring "and," you've created a second thing wearing one name. Split it.

---

## 3. The evolution ladder (preferred order)

When growth is justified, prefer earlier rungs over later ones. Each rung must be **earned by real need**, never taken speculatively.

1. **Extend before duplicate** — duplication is debt; reuse preserves one source of truth.
2. **Generalize before specialize** — once two or more concrete cases exist (§1.3), prefer one general solution over many special ones. Do not generalize before the cases are real.
3. **Compose before invent** — assemble from existing parts before building new primitives.
4. **Policy before implementation** — define the rule or standard before building the thing that obeys it.
5. **Implementation before optimization** — make it correct and clear before making it fast or clever.

---

## 4. Premature abstraction vs. necessary architecture

**The test: does this abstraction pay rent *today*?** Architecture that earns its keep now is necessary; architecture that only pays off in an imagined future is premature.

| Premature abstraction (avoid) | Necessary architecture (build) |
|-------------------------------|--------------------------------|
| Abstracting on a single use | A boundary with ≥2 real consumers |
| Configurability nobody asked for | A seam that is stable and understood |
| Interfaces for hypothetical futures ("we might need…") | A boundary imposed by security, tenancy, or irreversibility |
| Indirection with no second consumer | A boundary that meaningfully reduces blast radius |

**Deliberate exception:** a boundary that enforces a security or client-isolation rule is necessary **even with one consumer**, because the cost of getting it wrong is high (`CLAUDE.md` §6). Safety boundaries are not subject to the Rule of Two.

---

## 5. Detecting architectural drift and bloat

Review for these signals periodically and whenever the repo grows.

**Drift signals:**
- A file no longer matches the purpose of its folder.
- Two components doing the same job.
- Stub files that sit at bare `TODO` and never gain a contract (TODO-rot).
- Components with no clear owner or layer.
- Cross-references pointing at files that don't exist (broken constitutional links).
- A folder growing without a standard governing the shape of its files.
- Client-specific facts leaking into platform or core documents (also a security issue).
- Component descriptions accumulating "and"s.

**Bloat signals:** many near-empty files; abstractions with a single consumer; documents duplicating each other; capabilities created ahead of need.

**Remedy.** Prefer **deletion and merging** over accretion. Run a lightweight periodic audit that verifies: every reference resolves, every file earns its place, no orphans exist, and every stub states at least its intended contract. A stub may exist, but it must declare what it will be.

---

## 6. Choosing the artifact type

Before building, decide *what kind of thing* this is. Ask two questions, then pick from the ladder.

**Question A — is it read, or does it run?**
Read → documentation, prompt, policy. Run → workflow, agent, service, runtime component.

**Question B — is it platform-general, or tenant-specific?**
General → core (`01`–`07`). Tenant-specific → a client overlay under `04-clients/<client_id>/` that may only tighten core.

**The ladder — pick the least-committing type that fully serves the need:**

| Type | Use when the need is… | Notes |
|------|------------------------|-------|
| **Documentation** | to record knowledge, a decision, or a standard that humans/agents *read* | Cheapest, most reversible. Default home for anything not yet executable. |
| **Prompt** | reusable model instruction, invoked *inside* agents/workflows | A building block, not a standalone job. |
| **Workflow** | a repeatable multi-step *process* with steps, gates, and action classes | Orchestration; declares approval gates per `security-boundaries.md`. |
| **Agent** | a recurring *role* with a job, tool allowlist, and judgment, used across workflows | Don't create an agent for a one-off step — that's a workflow step or prompt. |
| **Service** | a long-running or networked capability (API, worker, queue consumer) with its own lifecycle/state | Triggers the Docker decision (`runtime-environment.md`). |
| **Runtime component** | shared infrastructure workers/services depend on (database, queue, cache, router) | Highest reuse bar; Docker boundary. |
| **Client deployment** | a tenant-scoped assembly of the above under a `client_id` | Governed by overlays that only tighten (§7). |

**Climb only when the lower rung genuinely can't do the job.** Each step up adds surface area, state, and cost-of-wrong. Executable rungs (service, runtime component, client deployment) trigger the runtime-boundary decision in `runtime-environment.md`; read-only rungs do not.

---

## 7. Extension across layers and client overlays

The same prime directive governs how runtime layers and tenants extend the system:

- **Core before client, security before both.** A new capability inherits *all* existing boundaries.
- **Client overlays may only tighten.** A client space (`04-clients/<client_id>/`) may add stricter constraints; it may never remove or weaken a core rule. This is the "tighten, never loosen" rule referenced by `security-boundaries.md`.
- **No growth may loosen a boundary.** Loosening requires an explicit, reviewed change to the governing document — never a new file that quietly routes around it.

Detailed per-tenant mechanics belong to a future `04-clients/` standard; this section establishes the principle they must obey.

---

## 8. Relationship to the rest of the constitution

| Document | Relationship |
|----------|--------------|
| `CLAUDE.md` | Governs *how* we decide (reasoning depth, cost, communication). This policy governs *what we decide about growth*. §1.5 and §4 inherit `CLAUDE.md` §6 (reasoning ∝ decision cost). |
| `security-boundaries.md` | Bounds all growth. New capabilities inherit every boundary; §7 implements the "clients tighten, never loosen" rule. No extension may weaken a boundary. |
| `runtime-environment.md` | The executable rungs of §6's ladder trigger its Docker decision. This policy decides *what* to build; `runtime-environment.md` decides *whether it needs a container*. |

---

## Summary

Grow only when a capability earns its place. Extend before you duplicate, generalize before you specialize, compose before you invent, write policy before implementation, and make it correct before you make it clever. Abstractions must pay rent today. Boundaries that protect safety or tenants are the one exception — build them early. Delete and merge rather than accumulate. The repository's job is to stay clear at scale; this policy is how it does that.
