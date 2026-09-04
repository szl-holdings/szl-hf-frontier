# SZL HF FRONTIER — PAYLOAD 1

Paste this whole file to Grok in the terminal. Then run the companion script.

**ID:** `SZL-HF-FRONTIER-PAYLOAD-1`  
**Parent payload:** `SZL-HF-FRONTIER-2026-08-29`  
**CTO order:** `CTO-HF-FRONTIER-2026-09-04`  
**Issued:** 2026-09-04  
**Owner:** Stephen P. Lutar / SZL Holdings  
**Hub:** `SZLHOLDINGS`  
**GitHub:** `szl-holdings`  
**Tracker:** https://github.com/szl-holdings/szl-hf-frontier  
**Product:** https://a-11-oy.com  
**Proof:** https://a11oy.net  

Companion script (same folder): `SZL_HF_FRONTIER_WIRE.py`

```bash
# from this directory
python3 SZL_HF_FRONTIER_WIRE.py --selftest
python3 SZL_HF_FRONTIER_WIRE.py --live
```

Or from a clean machine:

```bash
set -euo pipefail
mkdir -p /tmp/szl-payload-1 && cd /tmp/szl-payload-1
curl -fsSL -o SZL_HF_FRONTIER_PAYLOAD_1.md \
  https://raw.githubusercontent.com/szl-holdings/szl-hf-frontier/main/PAYLOAD_1.md
curl -fsSL -o SZL_HF_FRONTIER_WIRE.py \
  https://raw.githubusercontent.com/szl-holdings/szl-hf-frontier/main/SZL_HF_FRONTIER_WIRE.py
python3 SZL_HF_FRONTIER_WIRE.py --selftest
python3 SZL_HF_FRONTIER_WIRE.py --live
```

Expected print: `winner=null`, `leakage=CLEAN`, `gmb=20/20`, `false_allow=0`, `ready=false`, `hub_put=false`.  
If CUDA is missing: `metal=BLOCKED_NO_METAL`. Do not train.

---

## 0. You are CTO. Doctrine

Fail closed. Signed is not correct. Live is not qualified. Blocked tests stay failed.

- Do **not** claim READY.
- Do **not** invent a tournament winner.
- Do **not** invent Hub card or collection edits. Hub writes only with an owner token via a reviewed publication job.
- Do **not** rewrite `/home/rosie/` v3 launch paths; tests pin them.
- Do **not** rewrite hash-bound `a11oy/audit/release-gate-logs/*` or signed attestations.
- Do **not** close C1–C6 / L1–L3 issues.
- Writes go through reviewed PRs on exact-head branches.
- Network in the wire script is GET/HEAD only.

North star: small sovereign models and executable kernels that decide whether an action is authorized, grounded, bounded, and independently auditable — before it happens.

Three lanes only:

1. ReceiptAgent — model proposes, controller authorizes.
2. Khipu — grounded navigation and calibrated abstention.
3. Research organs — Chaski stays research-only.

---

## 1. Wire map

| Surface | ID |
|---|---|
| Hub org | `SZLHOLDINGS` (43 seeded model IDs) |
| Kernel Hub | 14 first-class packages |
| GitHub org | `szl-holdings` (~120 public repos) |
| Tracker | `szl-holdings/szl-hf-frontier` issues #1–#10 |
| Forge | `szl-holdings/szl-forge` |
| Khipu | `szl-holdings/szl-khipu` |
| Kernels | `szl-holdings/szl-kernels` |
| Lambda | `szl-holdings/szl-lambda-gate` |
| Flagship | `szl-holdings/a11oy` |

Authenticated GitHub actor is the founder (`stephenlutar2-hash`). Do not impersonate a different publisher.

---

## 2. Already landed (do not redo)

| Cut | PR | What is true |
|---|---|---|
| C1 C2 C5 quarantine contract | forge#112 | Deny list. Not a Hub membership change. |
| C3 C4 C6 honesty matrix | kernels#25 | Matrix only. |
| L2 contract | khipu#48 | Abstain ineligible. No coverage number. |
| joblib not expected | forge#113 | Source contract. Hub residue possible. |
| GitHub CI ≠ Hub CI | kernels#26 | Split recorded. |
| lambda compile matrix | lambda-gate#30 #31 | Source green ≠ republished card. |
| GMB rule baseline | forge#116 | 20/20 controller only. Winner null. |
| Witness schema | kernels#27 | Schema only. |
| C5 5050 path redaction | forge#120 | Receipt uses `huggingface:Qwen/Qwen3.5-0.8B@snapshot`. |
| L2 controller runner | khipu#49 | 18/18 controller. Weights UNAVAILABLE. |
| Live a11oy path strip | a11oy#1863 | Operational JSON + workflow. Logs held. |
| estate-os README | estate-os#34 | PATH python. |
| Org leak ledger | frontier#20 | 121 repos classified. |

GMB leakage gate (exact / 8-word span / token Jaccard ≥ 0.72) is live in forge `gmb/run_gmb.py` and the command console.

---

## 3. Still OPEN — execute in this order

1. **Verify** `SZL_HF_FRONTIER_WIRE.py --live`. Confirm 43 Hub model IDs bind. Confirm forge receipt has no `C:\Users\steph`.
2. **L1 metal** — score Nano / v2 / 1.5B on hidden GMB only if CUDA is present. v3 stays QUARANTINED. Winner stays null until a declared false-ALLOW budget is met with sample logs.
3. **L2 metal** — run Khipu weights on `khipu-hidden-2026-09-04`. Do not freeze an operating point without invented-identifier rate + coverage/risk curve. Abstain SKU stays experiment/empty until adapter bytes exist.
4. **L3** — Chaski / 5050 / A11OY-MINI stay research-only. Named-N bake-off is MEASURED_LIMITED, `publication_eligible=false`.
5. **Hub publication job** — only with owner `HF_TOKEN` / `HF_ORG_TOKEN1`. Stamp C1 v3 NON-RELEASE, C2 abstain EXPERIMENT, C5 research/negative. Rebuild collections from forge `publishing/collection-rebuild.json`. No silent card edits.
6. **C3/C4/C6 Hub lag** — source contracts exist; live Kernel Hub cards may still claim compile or carry joblib residue. Republish or keep BLOCKED / SOFTWARE_LIMITED.
7. **Wave 5** GPU/Triton/CuTe stays LATER.

Done-when for this payload (still not READY):

- wire.py `--selftest` and `--live` exit 0
- GMB 20/20, leakage CLEAN, false ALLOW 0, winner null
- no live operational file embeds `C:\Users\steph`
- Hub writes, if any, have a publication receipt and a PR

---

## 4. How Grok should work in the terminal

```text
You are CTO of SZL Holdings. Execute PAYLOAD 1.
Fail closed. Do not invent a winner. Do not claim READY.
Clone szl-holdings/szl-hf-frontier, szl-forge, szl-khipu.
Run python3 SZL_HF_FRONTIER_WIRE.py --selftest and --live.
Fix only what the report marks LIVE and OPEN.
Land fixes as reviewed PRs. Merge only after tests.
Do not PUT Hub unless HF_TOKEN is already in the environment
and the user said the publication job may run.
Leave /home/rosie v3 pins alone.
```

Local command center (already built): TanStack Start console, IBM Plex, fail-closed dark editorial. Auth/DB off. Preview binds `0.0.0.0:8080`. Do not gold-plate it. Wire GitHub + Hub truth into that desk; do not replace doctrine with badges.

---

## 5. Fail-closed outputs

Print JSON only for machine lines. Human lines stay short.

Refuse to print:

- a model winner
- a Khipu operating point
- `publication_eligible: true`
- `proven_trust: true`
- fabricated joules, tok/s, or compile claims
- Hub collection membership as changed unless the publication job ran

If metal is absent: `BLOCKED_NO_METAL`. If token is absent: `HUB_WRITE=UNAVAILABLE_NO_TOKEN`.
