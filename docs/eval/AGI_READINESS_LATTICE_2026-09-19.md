# AGI-readiness lattice — evaluation record

**schema:** `szl.capability-graph/v1`  
**class:** EVALUATION · not admission · not a product SKU  
**session:** 2026-09-19T23:55Z  
**result:** PARTIAL  
**doctrine:** v11 LOCKED · Λ = Conjecture 1 (OPEN, not a theorem)  
**trust ceiling:** 0.97 — never 1.00

This record answers “keep pushing the frontier / make it AGI / things no one dreamed of”
without painting a mind that is not here.

The undreamed-of move is not another chatbot. It is a typed capability graph:
every claimed capability is a bundle of `source + model + kernel + data + policy + eval + runtime + proof`.
A missing edge is PARTIAL or UNAVAILABLE. The graph never authorizes action.

---

## Honesty labels used here

| Label | Meaning |
|---|---|
| MEASURED | Observed this session from a named live endpoint or authenticated API |
| REPORTED | Named source this session; not independently re-proven |
| CONJECTURE | Advisory bound; not a theorem |
| HOLD | Deadline passed or required edge missing |
| PARTIAL | Some edges present, not a complete promotion bundle |
| HISTORICAL | True as of a dated snapshot; not current inventory |
| SIMULATED | Rehearsal / public synthetic; not a physical effector |
| UNAVAILABLE | Not present. Not inferred. Not painted green. |

---

## What was measured this session

### Product origin — a-11-oy.com

- Site reachable (no 503 this session).
- `GET /api/a11oy/v1/honest` HTTP 200:
  - doctrine v11 LOCKED
  - declarations 749 · axioms 14 · sorries 163
  - Lean commit `c7c0ba17`
  - locked formulas: **8** — F1, F4, F7, F11, F12, F18, F19, F22
  - lambda: **Conjecture 1** (explicitly not a theorem)
  - `source_sha` / `git_sha`: `a2244bde2a79fb9a831b537d8d2d096400516a7f`
  - persistence note: backend=sqlite, durable=True
  - no `is_live` field in the raw body
- `GET /api/build-info`: same revision from `env:SZL_GIT_SHA`; version UNKNOWN; receipt_minted false
- GitHub `szl-holdings/a11oy` main tip this session: same SHA  
  (`fix(killinchu): expire stale runtime observations on open pages #2201`)

**Meaning:** product origin and GitHub source agree on revision. That is live SHA equality. It is not inference-readiness, Hub runtime SHA, or is-live paint honesty.

### Proof registry — a11oy.net

- Static proof surface. Not runtime.
- `estate.json` captured_at **2026-08-31T18:59:11Z** — **19 days stale**.
- Atlas / inventory snapshots late August. Do not treat as current org inventory.

### Hugging Face org card (do not mix scopes)

- models 47 · datasets 35 · spaces 22 · collections 21
- kernels API cardinality **14** (list only, not v1-pin proof)

### Kernel compatibility deadline

- Cutoff **2026-09-13** has **PASSED**.
- Four compiled candidates still missing a `v1` branch (REPORTED via a11oy-net#195, draft).
- Disposition: **HOLD**. Do not delete assets to force a count.

### Open queue (this session, truncated)

- ~43 open PRs, ~27 draft. Do not merge drafts.
- a11oy-net#195 DRAFT — kernel-kind HOLD overdue
- szl-hf-frontier#36 OPEN (not draft) — revision-bound evidence completeness kernel + public estate adapter
  - head `365520fa39105908dfcf3df42730089020217239`
  - historical snapshot cited in PR: 220 public assets, **zero** complete promotion bundles
  - even complete inputs return `EVIDENCE_COMPLETE_UNTRUSTED`, `authorized: false`

---

## Capability graph (the actual frontier)

A capability is **complete** only if every required edge is present and current.
Missing any required edge → PARTIAL or UNAVAILABLE. This graph **never authorizes**.

| Cell | Meet | Notes |
|---|---|---|
| C1 Receipted governed action | PARTIAL | strongest cell; still missing v1 kernel pins + calibrated eval |
| C2 Evidence estate twin | HOLD | stale proof snapshots; #36 unmerged |
| C3 Kernel Hub compatibility | HOLD | deadline overdue |
| C4 Production ledger | HOLD | SQLite ≠ Postgres |
| C5 Memory / frontier plane | HOLD | watcher gap after #91 |
| C6 Physical defense effector | SIMULATED | public synthetic only |
| C7 AGI | UNAVAILABLE | not a product, not a kernel, not a conjecture upgrade |

**Estate meet this session: PARTIAL.**

## Non-claims (locked)

- AGI is not shipped.
- Eight locked formulas are not live general inference.
- Merge is not deploy.
- Reachable is not ready.
- Spaces Running is not inference-ready.
- Λ is not a theorem.
- Killinchu public tracks are not physical effectors.
- This lattice does not authorize.

**RESULT: PARTIAL**
