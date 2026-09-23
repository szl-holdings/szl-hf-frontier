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

**Meaning:** product origin and GitHub source agreed on revision for the dated 2026-09-19 session. That historical equality is not inference-readiness, Hub runtime SHA, or is-live paint honesty, and it must not be carried forward as a current equality claim.

### Proof registry — a11oy.net

- Static proof surface. Not runtime.
- `estate.json` captured_at **2026-08-31T18:59:11Z** — **19 days stale at the 2026-09-19 session**.
- Atlas / inventory snapshots late August. Do not treat as current org inventory.

### Hugging Face org card (do not mix scopes)

- Session-observed counts: models 47 · datasets 35 · spaces 22 · collections 21
- kernels API cardinality **14** (list only, not v1-pin proof)
- These are dated session observations, not current organization counts.

### Kernel compatibility deadline

- Cutoff **2026-09-13** has **PASSED**.
- Four compiled candidates still missing a `v1` branch (REPORTED via a11oy-net#195, draft).
- Disposition: **HOLD**. Do not delete assets to force a count.

### Open queue (dated 2026-09-19 session, truncated)

- ~43 open PRs, ~27 draft. Do not merge drafts.
- a11oy-net#195 DRAFT — kernel-kind HOLD overdue
- szl-hf-frontier#36 was OPEN at the session capture — revision-bound evidence completeness kernel + public estate adapter
  - head `365520fa39105908dfcf3df42730089020217239`
  - historical snapshot cited in PR: 220 public assets, **zero** complete promotion bundles
  - even complete inputs return `EVIDENCE_COMPLETE_UNTRUSTED`, `authorized: false`

---

## Capability graph (the actual frontier at the dated session)

A capability is **complete** only if every required edge is present and current.
Missing any required edge → PARTIAL or UNAVAILABLE. This graph **never authorizes**.

| Cell | Meet | Notes |
|---|---|---|
| C1 Receipted governed action | PARTIAL | strongest cell; still missing v1 kernel pins + calibrated eval |
| C2 Evidence estate twin | HOLD | stale proof snapshots; #36 was unmerged at capture |
| C3 Kernel Hub compatibility | HOLD | deadline overdue |
| C4 Production ledger | HOLD | SQLite ≠ Postgres |
| C5 Memory / frontier plane | HOLD | watcher gap after #91 |
| C6 Physical defense effector | SIMULATED | public synthetic only |
| C7 AGI | UNAVAILABLE | not a product, not a kernel, not a conjecture upgrade |

**Estate meet for the 2026-09-19 session: PARTIAL.**

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

---

## Second-writer authority recheck — 2026-09-23

This section does **not** rewrite the 2026-09-19 observation. It records what can be established now through the source/proof authority chain and marks everything else unavailable rather than carrying old observations forward.

- GitHub source owner `szl-holdings/a11oy` is now at exact `main@fe46a6da0dd14a158f56a86a3e1b24cc319ac02b`. The session product/source SHA `a2244bde2a79fb9a831b537d8d2d096400516a7f` is therefore historical and cannot be used as a current source-equality witness.
- A fresh exact live product/build revision was **not qualified in this recheck**. Current GitHub→product revision equality is therefore `UNAVAILABLE`, not inferred from the 2026-09-19 result.
- Current proof-source owner `szl-holdings/a11oy-net` is GitHub-verified at `main@15cc13e061f99fcb07dd7b315517c709575d3527`. Its admitted source record explicitly documents a product/source SHA lag at its own capture and says **do not claim MATCH / not LIVE**. That proof-source boundary remains authoritative until a newer admitted proof record supersedes it.
- The proof-origin `estate.json` still declares its own capture time as `2026-08-31T18:59:11Z` and explicitly says it is a dated static inventory snapshot, not a live dashboard. It remains `HISTORICAL` for current-estate decisions.
- Evidence-completeness precursor PR #36 is no longer open: it was admitted as merge commit `6489229be3852446b1664352392f17f57660678c`; current `szl-hf-frontier/main@d63138cd75dabf2f70d524adbdb928ea9d9b1940` contains that admission plus the later Apache-2.0 license commit. This advances source evidence tooling only; it does not establish current Hub inventory, provider runtime, model evaluation, or product readiness.
- Current whole-organization Hugging Face inventory is `UNAVAILABLE` in this recheck. Dated session counts above remain historical observations and are not promoted to current truth.

**Revalidation disposition: PARTIAL / HOLD · authorized=false.**  
The record may be retained as a dated evaluation artifact. It must not be used as current runtime, Hub, model, or AGI qualification.