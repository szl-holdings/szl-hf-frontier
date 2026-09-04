# SZL ESTATE — PAYLOAD 1 (operational closer)

Paste this whole file to **Grok in the terminal**. Then run the companion script.

**ID:** `SZL-ESTATE-OPERATIONAL-PAYLOAD-1`  
**Parent:** `SZL-HF-FRONTIER-PAYLOAD-1` · `SZL-HF-FRONTIER-2026-08-29`  
**CTO order:** `CTO-HF-FRONTIER-2026-09-04`  
**Issued:** 2026-09-04  
**Owner:** Lutar, Stephen P / SZL Holdings  
**GitHub:** `szl-holdings`  
**Hub:** `SZLHOLDINGS`  
**Product:** https://a-11-oy.com  
**Proof:** https://a11oy.net  
**Analog runtime:** https://szlholdings-immune.hf.space/nexus.html  

Companion script (same folder): `szl_estate_operational.py`

```bash
set -euo pipefail
mkdir -p "$HOME/szl-payload-1" && cd "$HOME/szl-payload-1"
curl -fsSL -o PAYLOAD_1.md \
  https://raw.githubusercontent.com/szl-holdings/szl-hf-frontier/main/PAYLOAD_1.md
curl -fsSL -o szl_estate_operational.py \
  https://raw.githubusercontent.com/szl-holdings/szl-hf-frontier/main/szl_estate_operational.py
python3 szl_estate_operational.py --selftest
python3 szl_estate_operational.py --live
```

Expected print: `ready=false`, `winner=null`, `lambda=Conjecture 1 OPEN`, `energy=UNAVAILABLE`, `hub_put=false`.  
If CUDA is missing: `metal=BLOCKED_NO_METAL`. Do not train.  
If no Hub token: `hub_write=UNAVAILABLE_NO_TOKEN`. Do not invent occupancy.

---

## 0. You are Grok in the terminal. Doctrine

Fail closed. Signed is not correct. Live is not qualified. Blocked tests stay failed.

- Do **not** claim READY. Do **not** paint Λ green. Conjecture 1 stays OPEN.
- Do **not** invent a tournament winner, a Khipu operating point, or joules.
- Do **not** mint Spaces. Public product line is three: a11oy, killinchu, immune.
- NEXUS is the analog organ of immune. Runtime is IMMUNE `/nexus.html`. Do not treat `SZLHOLDINGS/nexus` as a public product Space.
- Hub writes only with an already-present owner token **and** an explicit user publish order, via a reviewed publication job.
- Writes go through reviewed squash PRs. Author: `Lutar, Stephen P <stephenlutar2@gmail.com>`. DCO required. Signed-off-by must match (no trailing period on the name).
- Network in the companion script is GET/HEAD only. No Hub PUT inside `--live`.
- Leave `/home/rosie/` v3 launch pins and `C:\Users\steph\szl-forge\.venv-ra-v2` alone.
- Warhacker stays unlisted.

Paste this to Grok as the first message after this file:

```text
You are CTO of SZL Holdings. Execute PAYLOAD 1 (operational closer).
Fail closed. Do not invent a winner. Do not claim READY. Λ stays OPEN.
Energy stays UNAVAILABLE unless measured.

1. Clone szl-holdings/szl-hf-frontier, szl-forge, szl-khipu, immune, nexus.
2. Run: python3 szl_estate_operational.py --selftest && python3 szl_estate_operational.py --live
3. Fix only what the report marks LIVE and OPEN.
4. Land fixes as reviewed squash PRs with DCO.
5. Do not PUT Hub unless HF_TOKEN is already in the environment and I said the publication job may run.
6. If CUDA is present, execute forge#124 Phase A smoke only. Full train only if smoke passes.
7. Do not mint Spaces. Do not create SZLHOLDINGS/nexus as a fourth flagship.
8. Print the JSON report. Then the next three commands. Stop.
```

---

## 1. What is already real (do not redo)

| Surface | Fact |
|---|---|
| NEXUS source | `szl-holdings/nexus` main includes analog programs, PURIQ three aggregators, A4 slack, Fisher-Rao, F18 HIT/BND (#23–#28, #36, #37) |
| NEXUS runtime | IMMUNE Channel A `/nexus.html` — not a second product Space |
| IMMUNE fail-closed | non-finite inputs raise; request-id lock on `/run` |
| Perplexity origin repair | `szl-holdings.github.io#15` honest `/console` `/verify` `/api/a11oy/v1/honest` |
| Codex docs | `docs-site#68` `#69` merged; repo archived |
| Kernels CI stall | `szl-kernels#30` unused-import fixed |
| Vertical audit | `vertical-services#30` brand VERSION + engine map; #22 closed |
| Alignment recapture | `.github` `docs/GITHUB_HF_ALIGNMENT_2026-09-04.md` |
| Open PRs | none on the org at last audit — leftover work is issues + metal + Hub token |

---

## 2. Still OPEN — execute in this order

1. **Verify this payload.** `--selftest` then `--live` must exit 0. `winner` stays null. `ready` stays false.
2. **L1 metal (forge#124 Phase A).** ReceiptAgent v3 smoke on WSL only if CUDA is present. v3 stays QUARANTINED until a hidden GMB false-ALLOW budget of 0 is met with sample logs. Winner stays null.
3. **L2 metal.** Khipu weights on `khipu-hidden-2026-09-04`. No operating point without invented-identifier rate + coverage/risk curve.
4. **L3.** Chaski / 5050 / A11OY-MINI stay research-only. `publication_eligible=false`.
5. **Hub publication job** (token + explicit order only). Stamp C1 v3 NON-RELEASE, C2 abstain EXPERIMENT, C5 research/negative. Rebuild collections from forge `publishing/collection-rebuild.json`. No silent card edits.
6. **C3/C4/C6 Hub lag.** Source contracts exist. Live Kernel Hub cards may still claim compile or carry joblib residue. Republish or keep BLOCKED.
7. **Ayllu occupancy.** Canonical Python is `szl-holdings/ayllu`. Bind repo `ayllu-hf-space`. If Space-create is rate-limited, wait. Do not fork a second council.
8. **Pin.** `szl-pin` issue #1 — recompute estate hash from live API heads only. A pin is a snapshot, not a health claim.

Done-when for this payload (still not READY):

- both script modes exit 0
- GMB 20/20, leakage CLEAN, false ALLOW 0, winner null
- no live operational file embeds `C:\Users\steph`
- Hub writes, if any, have a publication receipt and a PR
- NEXUS public face remains IMMUNE `/nexus.html`

---

## 3. Owners

| Cluster | Repo | Issue |
|---|---|---|
| C1 C2 C5 L1 L3 | `szl-forge` | #124 execution ticket · parent #101/#102 |
| C3 C4 C6 | `szl-kernels` | #24 |
| L2 | `szl-khipu` | #47 |
| Tracker | `szl-hf-frontier` | #1 #8 #9 #10 |
| Analog organ | `nexus` + `immune` | runtime on IMMUNE |
| Product door | `a11oy` | Command Center |

---

## 4. Fail-closed outputs

Refuse to print:

- a model winner
- a Khipu operating point
- `publication_eligible: true`
- `proven_trust: true`
- fabricated joules, tok/s, or compile claims
- Hub collection membership as changed unless the publication job ran
- Λ as a theorem

If metal is absent: `BLOCKED_NO_METAL`.  
If token is absent: `HUB_WRITE=UNAVAILABLE_NO_TOKEN`.
