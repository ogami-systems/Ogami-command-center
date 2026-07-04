# Gmail Architecture — Decided and Implemented (2026-07-04)

**Status: decided.** Michael approved `gmail.modify` with a stricter mandate
than this document's original §6 recommendation: every Gmail write operation
is gated by default (not just drafts/send), and the service-level send-block
in §3's Layer 2 is now built (`saint/accounts/gmail_safety.py`), not merely
proposed. §1's classification table and §6 below are updated to record the
actual decision, not the original open recommendation — see
`02-agents/saint.md`'s Tool allowlist and Trust Model sections for the
canonical summary; this document remains the detailed rationale, referenced
from there rather than duplicated.

No code was written or modified to produce this document. Every scope claim
below marked "confirmed" was checked directly against Google's own API
reference during this review, not recalled from training or inferred by
pattern-matching — the same rigor failure that caused yesterday's `gmail.modify`
surprise is exactly what this document is trying not to repeat.

---

## 0. The one fact that reshapes this whole design

Yesterday's finding was framed as "drafts and send are bundled together." That
undersells it. The real fact, confirmed method-by-method below: **every Gmail
write operation — not just send and drafts, but archiving, labeling, marking
read/unread, and trashing — requires a scope that also grants send.** The only
scope that does *not* include send is `gmail.readonly`, which permits no
writes of any kind.

There is no OAuth configuration that gives Saint "manage my inbox but never
send" as a Google-enforced guarantee. The choice is binary at the OAuth layer:
**pure read-only**, or **read+write-including-send**. Everything past that
point has to be enforced by Saint itself, not by Google. That is the design
problem this document solves.

---

## 1. Every Gmail capability, with confirmed scope requirements

| # | Capability | Gmail API method | Scope(s) accepted | Verification |
|---|---|---|---|---|
| 1 | Read | `users.messages.get` | `gmail.readonly` (or any broader scope) | Standard Gmail API pattern — not re-fetched this session, consistent with `gmail.readonly`'s documented purpose |
| 2 | Search | `users.messages.list` (with `q=`) | `gmail.readonly` (or broader) | Same as above |
| 3 | Summarize | *(not a Gmail API call)* | none beyond whatever fetched the content | N/A — this is Saint's own reasoning over already-read data |
| 4 | Classify (describe only) | *(not a Gmail API call)* | none beyond read | N/A — same as summarize, if it means "tell Michael what kind of email this is." If it means "apply a category label," see #6. |
| 5 | Archive | `users.messages.modify` (remove `INBOX` label) | `gmail.modify`, `gmail.modify.restricted`, `mail.google.com` | **Confirmed today** via Google's REST reference for `users.messages.modify` |
| 6 | Label (apply/remove) | `users.messages.modify` | same as Archive | Same endpoint as #5 — archive *is* a label operation, not a separate capability at the API level |
| 7 | Draft (new) | `users.drafts.create` | `gmail.modify`, `gmail.compose`, `mail.google.com` | **Confirmed today** |
| 8 | Reply draft | `users.drafts.create` (with `threadId`) | same as #7 | Same endpoint, same scopes |
| 9 | Send | `users.messages.send` / `users.drafts.send` | `gmail.modify`, `gmail.compose`, `gmail.send`, `mail.google.com` | **Confirmed today**, both methods independently |
| 10 | Delete (permanent) | `users.messages.delete` | `mail.google.com` **only** | **Confirmed today** — this is the one capability Google gates behind a single, maximally broad scope, separate from everything else |
| 11 | Trash | `users.messages.trash` | `gmail.modify`, `mail.google.com` | **Confirmed today** — notably does *not* accept the narrower `gmail.labels` |
| 12 | Restore (untrash) | `users.messages.untrash` | `gmail.modify` (inferred — same family as trash; not independently re-fetched this session) | Inferred, not fetched — flagged honestly |
| 13 | Mark read/unread | `users.messages.modify` (toggle `UNREAD` label) | same as Archive/Label | Same endpoint as #5/#6 |
| 14 | Future capabilities | *(unknown)* | *(unknown)* | Must be added to this table, classified below, before being built — see §6 |

**A scope not in this table, deliberately: `gmail.labels`.** Its description
("see and edit your email labels") only covers *label definitions*
(`users.labels.create/update/delete` — e.g. creating a label called "Receipts"),
not applying a label to a message. `users.messages.modify` — the endpoint
every mutation in this table actually uses — does not accept `gmail.labels` as
a valid scope. It is not a usable substitute for anything above.

### Classification table (updated to reflect the decision — every write gated)

| # | Capability | Google structurally allows | Saint structurally allows | Approval required | Reversible | Consequential | Destructive |
|---|---|---|---|---|---|---|---|
| 1 | Read | Yes, readonly-safe | Yes (`gmail_read_messages`) | No | N/A | No | No |
| 2 | Search | Yes, readonly-safe | Yes (`gmail_search`) | No | N/A | No | No |
| 3 | Summarize | N/A | Yes (implicit, model behavior) | No | N/A | No | No |
| 4 | Classify (describe) | N/A | Yes (implicit) | No | N/A | No | No |
| 5 | Archive | Only via a send-capable scope | Yes (`gmail_archive_message`) | **Yes** | Yes | **Yes** | No |
| 6 | Label | Only via a send-capable scope | Yes (`gmail_modify_labels`) | **Yes** | Yes | **Yes** | No |
| 7 | Draft (new) | Only via a send-capable scope | Yes (`gmail_create_draft`) | **Yes** | Yes (delete the draft) | **Yes** | No |
| 8 | Reply draft | Only via a send-capable scope | Yes (`gmail_create_reply_draft`) | **Yes** | Yes | **Yes** | No |
| 9 | Send | Yes, if `gmail.modify`/`compose`/`send` present (it is) | **No — no function exists; also unconditionally blocked at the service layer even if one existed (§3 Layer 2, built)** | N/A — never executes | **No** | Would be the most consequential capability on this list if it existed | Not "destructive" in the delete sense, but irreversible + externally visible — stricter than Destructive |
| 10 | Delete (permanent) | Only via `mail.google.com` | **No, and will never be built** | N/A | **No** | N/A — permanently excluded at the OAuth layer | Maximally destructive |
| 11 | Trash | Only via a send-capable scope | Yes (`gmail_trash_message`) | **Yes** | Yes (~30 days) | **Yes** | No |
| 12 | Restore | Only via a send-capable scope | Yes (`gmail_untrash_message`) | **Yes** | Yes (trivially — it's a reversal) | **Yes** | No |
| 13 | Mark read/unread | Only via a send-capable scope | Yes (`gmail_mark_read_status`) | **Yes** | Yes | **Yes** | No |
| 14 | Future | Unknown | Unknown | Classify before building, add to this table — see §6 | — | — | — |

Every write capability is gated, per Michael's explicit decision (2026-07-04)
to prioritize maximal defense-in-depth over the narrower "leave low-risk
mutations ungated" recommendation this document originally made.

---

## 2. Why "gate everything" alone doesn't fully solve the problem

Michael chose to gate every write operation (§6) — the maximally conservative
option this section originally flagged as legitimate but not the default
recommendation. Worth being precise about what that does and doesn't fix on
its own: gating archive/label/trash protects against an *unwanted mutation*,
but it does nothing about *send specifically* by itself, because send was
never implemented as a gated tool — it isn't implemented at all, and approval
gates only apply to tools that exist. That's why the decision combines gating
*and* Layer 2 (§3): gating handles every mutation that does exist; Layer 2
handles the one capability that must never exist, independent of whether any
future approval flow would have caught it.

---

## 3. Proposed permanent Gmail security model

Four layers, each covering what the layer above it can't:

**Layer 1 — OAuth scope minimization (real, but incomplete on its own).**
Request `gmail.modify` — the narrowest scope that supports Saint's actual
inbox-management needs (archive, label, trash, drafts once built). Never
request `gmail.compose`, `gmail.send`, or `mail.google.com` — each is either a
strict superset of risk with no capability Saint needs beyond what `modify`
already grants, or (for `mail.google.com`) the single scope that also unlocks
permanent deletion. This is a real, absolute boundary for everything *outside*
what `gmail.modify` grants — permanent delete becomes genuinely impossible,
not just unimplemented, because the token itself cannot do it. It is not a
complete boundary for send, because send lives inside the scope Saint needs
for everything else.

**Layer 2 — a service-level send-block, independent of any tool existing
(built: `saint/accounts/gmail_safety.py`, `SafeGmailService`).**
`GoogleAccount.get_gmail_service()` returns the raw Gmail client wrapped in a
proxy that unconditionally raises `SendBlockedError` if `.users().messages().send(...)`
or `.users().drafts().send(...)` is ever called through it — regardless of
caller, regardless of reason. The block is liftable only via a hardcoded
`allow_send=True` at construction time in source code — never `.env`,
config, or any runtime input — so no prompt, agent, or bug can flip it, only
a deliberate, reviewable code change. This converts "no send tool exists" (a
fact about today's code, which a future edit could silently undo) into
"Saint's Gmail client cannot send, structurally, at the object level" (a fact
a future edit would have to deliberately tear down, not accidentally bypass).
Tested in `saint/tests/test_gmail_safety.py` against the real `googleapiclient`
library (offline, no credentials), not a hand-rolled approximation of it.

**Layer 3 — no send-capable tool is ever registered (existing invariant,
reframed honestly).** `tools.TOOLS`/`HANDLERS` contains no send/compose/reply
function today, enforced by `test_no_send_capable_tool_exists`, extended to
also assert `get_gmail_service()` returns a `SafeGmailService` instance —
tying the "no tool" guarantee to the "even if there were one" guarantee.

**Layer 4 — every Gmail write operation is Communicate-class consequential,
gated through the existing Telegram approval queue (built: all ten write
tools in `gmail_tools.py`'s `CONSEQUENTIAL` table).** No new mechanism —
reuses the `CONSEQUENTIAL` table and approval flow already proven for
calendar/sheets. This is broader than this document's original
recommendation (which would have left archive/label/trash/mark-read
ungated) — Michael's decision (§6) was to gate everything, accepting the
extra approval-tap overhead for a maximally conservative posture. If literal
send is ever approved as a deliberate future feature (not something this
document recommends, and not something Layer 2 currently permits), it should
be treated with at least the ceremony of the Trust Model's 8-step onboarding
gate, even though it's a new *capability* rather than a new *command source*
— the stakes are comparable, and the process should be too.

---

## 4. Where the real security boundary actually lives

| Layer | What it guarantees | What it does *not* guarantee |
|---|---|---|
| **OAuth** | Permanent delete and full-account (`mail.google.com`) access are impossible — Saint's token literally cannot do them, no matter what code runs or what the model is told. | Does *not* prevent send — `gmail.modify` grants it, and there is no narrower alternative that keeps archive/label/draft. |
| **Application logic (Layer 2 proxy)** | Send is blocked at the Python-object level, independent of which tool functions exist. | Does not defend against arbitrary code execution on the host — a fully compromised machine could re-import the raw Google client directly with the stolen token, bypassing Saint's code entirely. That is a host-security problem, outside this document's scope. |
| **Approval system** | Every Gmail write (archive/label/trash/restore/mark-read/draft/reply) never executes without Michael's Telegram tap. | Does not, by itself, stop send — send isn't in this queue at all; it's blocked upstream at Layer 2/3, structurally absent as a tool. |
| **Trusted command sources** (`02-agents/saint.md`'s Trust Model) | A manipulated model reading adversarial email content still can't cause any Gmail mutation without Michael's tap. | Doesn't change what's true regardless of manipulation — the guarantees above hold even for a *fully* manipulated model, which is the point. |
| **Tests** | Prove the above holds today, and catch regressions. | Can't prove the model will never be *influenced* — only that influence can't reach an unapproved side effect. |

---

## 5. Guarantees, stated honestly

**Can honestly guarantee, now that Layer 2 is built and tested:**
- Saint's code contains no function that calls Gmail's send endpoint (tested).
- Even a future coding mistake that tried to call send directly on the raw
  Gmail service object is blocked, unconditionally (tested against the real
  `googleapiclient` library, not a fake).
- Saint's OAuth token can never perform permanent deletion or full-account
  access, regardless of any bug, prompt injection, or model manipulation —
  because the scope for that doesn't exist in what Saint requests.
- No Gmail write operation of any kind — archive, label, trash, restore, mark
  read/unread, draft create/update, reply draft — executes without a real
  Telegram tap from Michael's owner ID.

**Cannot honestly guarantee, ever, under this or any design:**
- That the OAuth token is *incapable* of sending email at the Google API
  level. It is capable, for as long as `gmail.modify` is the scope in use —
  because Google's own scope model does not offer a narrower alternative that
  retains archive/label/draft capability. The guarantee is about Saint's own
  code and object-level enforcement, not about revoking Google's grant.
- Protection against a host-level compromise (arbitrary code execution on the
  machine running Saint). Layer 2 defends against Saint's own code paths, not
  against an attacker who has already broken out of them.
- That the model's summaries or judgment are immune to influence by
  adversarial content — the existing Trust Model's honest-scope statement
  already covers this; nothing about Gmail specifically changes it. The
  guarantee is about *consequence*, not about the model being unmanipulable.

---

## 6. Decision (2026-07-04)

**Michael approved `gmail.modify` over `gmail.readonly`-only, with Layer 2
(the service-level send-block) built as a hard requirement, plus a stricter
mandate than this document's original recommendation: every Gmail write
operation is gated by default, not just drafts/send.** Original reasoning for
`gmail.modify` over readonly-only still holds: Michael's original
requirements explicitly wanted archive/label/trash/draft capability, and
there is no OAuth configuration that gets that *and* a Google-enforced
no-send guarantee — the only way to get a stricter OAuth-level guarantee is
to give up all of it and go read-only. Given that the real boundary has to be
application-layer either way, accepting `gmail.modify` plus Layer 2 costs
nothing in actual safety compared to `gmail.readonly` alone.

**Beyond that, Michael chose the maximally conservative posture on gating**
— this document's original default (leave archive/label/trash/mark-read
ungated, since they're reversible and have no external visibility) was
superseded by an explicit "assume future code, agents, or prompts contain
mistakes; multiple independent layers should prevent unintended email
sending" mandate. All ten Gmail write capabilities are now consequential;
only search and read remain ungated.

**Permanently excluded, no exceptions:** `gmail.compose`, `gmail.send`,
`mail.google.com`, and the `users.messages.delete` (permanent delete)
capability — none add anything Saint needs, and each only adds risk. Delete
in particular needs no approval gate because it needs no gate to fail to
reach — the OAuth scope required for it is simply never requested.

**Implemented:** `saint/accounts/gmail_safety.py` (Layer 2), `saint/tools/gmail_tools.py`
(Layer 4, ten gated write tools + two ungated read tools), `saint/tests/test_gmail_safety.py`
(6 tests) and extensions to `saint/tests/test_trust_boundaries.py`, `02-agents/saint.md`'s
Tool allowlist and Trust Model sections.
