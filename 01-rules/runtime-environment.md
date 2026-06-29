# Runtime Environment — Docker as the Portable Runtime Layer

This document defines how Ogami systems are made **runnable and reproducible** across machines. It is a runtime standard inherited by workflows, services, and client deployments. Like every `01-rules/` document, client overlays may tighten it, never loosen it.

> The *layer* defined here is permanent. **Docker is the current tool** that implements it. If the container technology ever changes, this document's purpose survives; its specifics are updated.

---

## The layer model

Ogami is composed of distinct layers, each with one job:

| Layer | Role |
|-------|------|
| **Repository** | Source of truth — rules, agents, workflows, prompts, curated memory |
| **Git** | Versioned history — what changed, when, and why |
| **Claude Code / OpenClaw** | Execution and reasoning workers — they read definitions and do the work |
| **Docker** | The reproducible environment that makes the system runnable across machines |

Docker is not where policy lives and not where reasoning happens. It is the **portable boundary** inside which workers run consistently — on Michael's laptop, on a server, or in a client environment.

---

## Principle: Docker is the portable runtime layer.

Use Docker when we need:

- consistent local development environments
- isolated services
- databases or queues
- agent runtimes
- client-specific deployable systems
- safe experimentation without polluting the host machine
- future handoff to servers or client environments

Do **not** add Docker prematurely to simple documentation-only work.

---

## The decision rule

- If a feature only changes **docs, prompts, policies, or architecture files**, Docker is usually **unnecessary**.
- If a feature introduces **executable services, databases, APIs, background workers, queues, local tools, or multi-component systems**, Docker should be **considered early** — designed in from the start, not bolted on later.

When in doubt, ask: *does this produce something that runs, or something that is read?* Things that run trend toward a Docker boundary; things that are read do not.

---

## Tie-in to architectural decisions

When deciding what a capability becomes — an **agent**, **workflow**, **memory system**, **service**, or **client deployment** — also decide **whether it needs a Dockerized runtime boundary**. This question is part of the standard design checklist (see `CLAUDE.md` §4 and `01-rules/extension-policy.md`).

A Dockerized boundary is most likely when the capability:

- holds state (a database, queue, or cache),
- exposes or calls a network service (an API or worker),
- must run identically for more than one client, or
- runs untrusted or experimental code that should not touch the host.

---

## Relationship to security

Docker maps to the **Runtime** trust zone in `01-rules/security-boundaries.md`: it *executes* policy, it does not *define* it. Containers improve isolation but do not replace the security boundaries — secrets are still injected at runtime (never baked into images), client isolation is still enforced, and side-effecting actions still require an active workflow run and audit events.

---

## Current status

The repository is presently documentation-only, so **no Dockerfiles or `docker-compose` files exist yet, by design.** They become justified the moment we build the first executable service, database, queue, API, or background worker. At that point, the Docker artifacts for it are designed alongside the feature, not retrofitted.
