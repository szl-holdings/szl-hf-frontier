# SZL-HF-FRONTIER-1 — Python Payload for Codex

**Payload ID:** SZL-HF-FRONTIER-1-2026-09-30
**Auditor:** Perplexity agent session, 2026-09-30
**Executor:** Codex
**Doctrine:** v11 LOCKED — fail closed, receipts or it did not happen, train metrics are not evals, publication_eligible stays false until a held-out generate receipt exists.

---

## 0. Scope of audit evidence

- GitHub org `szl-holdings`: 130 repos enumerated (search, org scope, 2026-09-30).
- HF org `SZLHOLDINGS`: 49 models, 44 datasets, 36 Spaces enumerated via `hf_fs ls` (2026-09-30).
- Thread audit (2026-09-12 session): merge/publish wave, token exposure events, DPO lane status.

Every work order below is EVIDENCE-BOUND to these enumerations. Codex must re-verify before acting (estate may have moved since 2026-09-30). Fail closed on any drift.

## 1. Findings

| ID | Finding | Severity | Evidence |
|---|---|---|---|
| F1 | Two HF access tokens pasted in plain text (prefixes `hf_nGHC…`, `hf_rpzm…`) during the 2026-09-12 session; revocation never confirmed | CRITICAL | thread log 2026-09-12 14:0x–14:4x |
| F2 | 8 merged Tier-3 model repos still tagged `peft` / `base_model:adapter:` on the Hub despite holding merged full-precision checkpoints | HIGH | HF tags on szl-receiptagent-qwen35-0.8b-v2/v3, khipu-r3, chaski-r2, chaski-5050, brain-navigator-r2, KHIPU-R2, WILLAY |
| F3 | DPO khipu-abstain lane (the 0/6 abstain port fix) has no output repo and no dpo_receipt.json anywhere in the estate | HIGH | absent from models enumeration |
| F4 | Placeholder repos with no artifact purpose: model `SZLHOLDINGS/SZLHOLDINGS`, dataset `SZLHOLDINGS/SZLHOLDINGS`, Space `SZLHOLDINGS/README` | MEDIUM | HF enumeration |
| F5 | 25+ archived hologram/duplicate GitHub repos whose descriptions claim canonical redirects — pointers not machine-verified | MEDIUM | GitHub enumeration |
| F6 | 9 private datasets + 6 private Spaces with no documented access intent | MEDIUM | HF enumeration |
| F7 | `governed-inference-meter` model public but deprecated; canonical source archived | LOW | HF enumeration + repo description |
| F8 | Open-issue concentration: szl-forge 66, a11oy 43, szl-frontier 37, .github 33 | LOW | GitHub enumeration |
| F9 | Forge PRs #254/#243 remain draft under explicit do-not-merge holds — correctly untouched; do NOT merge as part of this payload | GATE | PR bodies |

## 2. Work orders (Python, receipted)

### WO-1 — Merged-model card reconciliation (fixes F2)
For each of the 8 merged repos, fetch README.md, rewrite YAML frontmatter: `library_name: transformers`, `base_model_relation: merged`, remove stale `peft`/`lora`/`qlora` tags via the Hub API, keep license + base_model tags. Commit each card change with message `card: reconcile merged checkpoint metadata (audit F2)`. Emit `frontier1/wo1_card_receipt.json` per repo: repo id, before/after tag sets, commit hash. FAIL CLOSED if any repo lacks a full safetensors checkpoint (verify param count > adapter-only size before touching the card).

### WO-2 — Placeholder repo disposition (fixes F4)
For model `SZLHOLDINGS/SZLHOLDINGS`, dataset `SZLHOLDINGS/SZLHOLDINGS`, Space `SZLHOLDINGS/README`: list files, hash contents, produce `frontier1/wo2_inventory.json`. DO NOT delete — owner decision. Append a README note `DISPOSITION: under audit SZL-HF-FRONTIER-1-2026-09-30` to each. Fail closed on any unexpected large files (>50 MB) — escalate instead.

### WO-3 — DPO khipu-abstain lane (fixes F3)
Execute the `dpo` subcommand of `tools/szl_omen_pipeline.py` (szl-forge, huggingface branch) on the GPU host against `SZLHOLDINGS/SZL-Khipu-1.5B-abstain` (train.abstain.jsonl + adversarial.jsonl), policy adapter `SZLHOLDINGS/khipu-r3`. Requirements: r16/a32 LoRA (QLoRA forbidden on Qwen3.5), bf16 on CUDA, seed 11, max_prompt_length 512, max_length 1024, beta 0.1. Emit `dpo_receipt.json` with: data digest sha256, pairs_used, train_loss (labeled TRAIN METRIC NOT AN EVAL), hardware, seed, publication_eligible=false, next gate = held-out abstain generate on adversarial.jsonl. If no CUDA host available, record UNAVAILABLE and stop — never run degraded and claim a number.

### WO-4 — Hologram pointer verification (fixes F5)
For every archived repo whose description contains `Canonical:`, extract the target repo, verify it exists and is unarchived, write `frontier1/wo4_pointer_receipt.json` (list of source→target→status OK/BROKEN). BROKEN pointers become GitHub issues in the source repo, one each, titled `canonical pointer broken: <target>`.

### WO-5 — Private estate access manifest (fixes F6)
For the private datasets (szl-evidence, david-leads-data, thesis-formula-index, szl-org-infra, anatomy-alive-harness, vault-artifacts, szl-training-receipts, yuyay-v3-axis-labels-v1, legacy-archive) and private Spaces (szl-constellation-staging, szl-safe-stack, a11oy-factory, counsel-assurance, puriq-markets, terra-assurance): emit `frontier1/wo5_private_manifest.json` with last-modified dates and sizes. Flag any not touched in 30+ days as `STALE-REVIEW`. No visibility changes.

### WO-6 — Token hygiene gate (fixes F1 — OWNER ACTION)
Codex CANNOT fix this. Emit `frontier1/wo6_owner_action.md` instructing the owner to confirm revocation of the two exposed token prefixes at https://huggingface.co/settings/tokens. Payload does not proceed to WO-3 publish steps until owner marks this DONE in the file (append `OWNER CONFIRMED <date>`).

### WO-7 — Deprecated model sweep (fixes F7)
Verify `governed-inference-meter` README carries the deprecated banner pointing at szl-energy-attest. If missing, add it. Receipt `frontier1/wo7_receipt.json`.

## 3. Order and gates

1. WO-6 first (owner gate for any publish)
2. WO-1, WO-2, WO-4, WO-5, WO-7 — read-mostly, may run in any order
3. WO-3 last — GPU host required, publish gated on WO-6 owner confirmation
4. PR #254 and #243: DO NOT MERGE (F9). Not in scope.

## 4. Master receipt

Emit `frontier1/SZL-HF-FRONTIER-1-2026-09-30-master.json`: every WO status ∈ {DONE, UNAVAILABLE, FAIL-CLOSED, OWNER-PENDING}, timestamp, machine, sha256 of every artifact produced. A FAIL-CLOSED anywhere is a valid outcome — never paper over it.

— Signed off for audit by the Perplexity agent session, 2026-09-30. Nothing glows that didn't earn it.
