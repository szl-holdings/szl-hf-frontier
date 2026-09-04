# Kernel and model audit — 2026-09-04

Observed from the public Hugging Face model API (`author=SZLHOLDINGS`) and GitHub `szl-formulas` source. This is a ledger, not a promotion.

Hub write is still blocked in this connector. GitHub is canonical.

## Kernels (15 Hub IDs with `kernel` tag)

| Hub ID | Downloads | Likes | Hub lastModified | GitHub source | Verdict |
|---|---:|---:|---|---|---|
| `szl-governed-norm` | 216 | 1 | 2026-06-23 | `szl-lambda-gate` family / suite | C3 — published CI failures; tag includes `deprecated` |
| `szl-kernels` | 145 | 0 | 2026-06-24 | `szl-holdings/szl-kernels` | Suite + MiniEmbed companion. Keep. Do not claim GPU |
| `szl-lambda-gate` | 111 | 0 | 2026-06-23 | `szl-holdings/szl-lambda-gate` | C3 — published test failures |
| `szl-block-kv` | 49 | 0 | 2026-08-28 | check `szl-khipu` / kernel trio | Attention-lane code; 0 likes; not Flash/Sage |
| `szl-maskmod` | 34 | 0 | 2026-08-28 | check suite | Thin kernel card |
| `szl-receipt-attn` | 26 | 0 | 2026-08-28 | `YARQA` family | Receipt-aware attention silhouette |
| `szl-invariants` | 0 | 2 | 2026-07-12 | `szl-holdings/szl-invariants` | Software replay. Highest likes, zero downloads |
| `szl-blocked` | 0 | 1 | 2026-06-24 | `szl-holdings/szl-blocked` | C4 + C6 — public BLOCKED state |
| `governed-inference-meter` | 0 | 0 | 2026-06-23 | archived GitHub successor `szl-energy-attest` | DEPRECATED / SUPERSEDED. Do not upgrade |
| `szl-govsign` | 0 | 0 | 2026-06-24 | `szl-holdings` series | Keep as signer. No product claim |
| `szl-provctl` | 0 | 0 | 2026-06-24 | `szl-holdings/szl-provctl` | C4 + C6 |
| `szl-ouroboros` | 0 | 0 | 2026-07-12 | `szl-holdings/szl-ouroboros` | Loop-tax. C4 pickle risk |
| `szl-formulas` | 0 | 0 | 2026-07-12 | `szl-holdings/szl-formulas` | 21 formulas. Locked-proven is not 21 |
| `YARQA-ATTN` | 0 | 0 | 2026-08-28 | `szl-holdings/YARQA-ATTN` | Original canal attention. Not a clone |
| `szl-khipu-kernels` | 0 | 0 | 2026-08-29 | `szl-holdings/szl-khipu` | Companion kernels. Empty traction |

Org page count was 14; API `filter=kernel` plus `szl-khipu-kernels` / `szl-maskmod` lands at **15 tagged kernel IDs**. Treat 14 vs 15 as a Hub listing lag, not a missing product.

### Upgrade rule

Do **not** ship a new CUDA attention kernel to “push the frontier.” The Hub already has Flash/Sage/Flex. SZL’s unused surface is **proof-status gated composition**: only PROVEN formulas may drive ALLOW; CONJECTURE and SORRY stay advisory or blocked.

Retired in place: `governed-inference-meter` → `szl-energy-attest` (GitHub). Hub card rewrite still needs an owner HF token.

C3/C4/C6 stay open. A green card on a failing test is a lie.

## Math already in GitHub (do not reinvent)

Source: [`szl-formulas/torch-ext/szl_formulas/_formulas.py`](https://github.com/szl-holdings/szl-formulas/blob/main/torch-ext/szl_formulas/_formulas.py).

21 formulas. Proof labels from that file:

| Status class | Formulas |
|---|---|
| PROVEN (structure or inequality) | `lambda_bounded`, `bekenstein_cascade` (DPI helper), `khipu_merkle_root`, `dsse_envelope` (structure only), `hoeffding_tail`, `fisher_rao_distance`, `bohr_complementarity_floor`, `shor_codeword_distance`, `css_ingress_verify`, `reed_solomon_singleton`, `madhava_series`, 2-axis Schur |
| AXIOM | `lambda_homogeneous`, Reidemeister, Gleason, Pinsker, KS-18 scaffold, Kitaev surface |
| SORRY | `pac_bayes_mcallester`, `two_witness_ks18_soundness` |
| CONJECTURE | Λ uniqueness (Conjecture 1) on `lambda_aggregate` — A1–A4 proven, uniqueness open |

The estate already says locked-proven = **exactly 8**. This audit does not re-count Lean. Python labels above are software mirrors, not a new proof.

Dataset already published: [`SZLHOLDINGS/canonical-formulas-v1`](https://huggingface.co/datasets/SZLHOLDINGS/canonical-formulas-v1).

## Models with traction (MEASURED downloads)

| Hub ID | Downloads | Role | Order |
|---|---:|---|---|
| `chaski` | 2851 | Research organ. Failed qualification | C5 + L3 — quarantine from flagship |
| `SZL-Khipu-1.5B` | 1684 | Trained QLoRA on Qwen2.5-1.5B | L2 — keep, add abstention bench |
| `SZL-Forge-1.5B-ReceiptAgent` | 1513 | Trained ReceiptAgent | L1 — tournament vs nano/v2 |
| `SZL-Khipu-1.5B-GGUF` | 630 | Quant of Khipu | Needs its own post-quant eval |
| `szl-receiptagent-qwen35-0.8b-v2` | 124 | Smaller RA | L1 candidate |
| `chaski-r2` | 94 | Research cut | Research-only |
| `KHIPU-R2` | 80 | Research | L2, not promote on train-finished |
| `chaski-5050` | 71 | Leaks local paths | C5 |
| `WILLAY` | 69 | Identity SFT 0.5B | Research |
| `brain-navigator-r2` | 54 | Khipu family | L2 |
| `A11OY-MINI` | 32 | GGUF of failed parent | C5 |
| `szl-receiptagent-qwen35-0.8b-v3` | (listed, placeholder card) | C1 — quarantine |
| `SZL-Khipu-1.5B-abstain` | empty adapter risk | C2 |

Traction ≠ qualification. Chaski has the most downloads and is the one the CTO order already failed.

## What this connector will not do

- Publish or rebuild Hub kernels (no HF token).
- Train or quantize weights (no GPU, no Unsloth metal).
- Invent a bench number for Khipu, ReceiptAgent, or energy.
- Clone FlashAttention and stamp SZL on it.

## Next GitHub-side moves

1. Close C3 on `szl-lambda-gate` / `szl-governed-norm` tests or mark BLOCKED on the card.
2. Strip pickle/joblib from C4 artifacts in source.
3. Relabel C1/C2/C5 cards when HF write exists.
4. Keep compose prototype in this repo (`compose/`) until C3 is green — then it may become a kernel package.
