<!--
  szl-papers README — investor-readable rewrite · 2026-06-30
  Honesty doctrine LOCKED. Sign-off: Stephen Lutar <stephenlutar2@gmail.com>
  DCO + Conventional Commits.
-->

# SZL Papers

**The published research behind SZL's governance math** — preprints, thesis lineage, open bounty problems, and prior-art disclosures.

[![Doctrine v11 LOCKED](https://img.shields.io/badge/Doctrine-v11_LOCKED-d4a444.svg)](https://github.com/szl-holdings/lutar-lean)
[![Concept DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.19944926-01696F.svg)](https://doi.org/10.5281/zenodo.19944926)
[![Λ uniqueness](https://img.shields.io/badge/%CE%9B-Conjecture_1_disproved_%C2%B7_Theorem_U_conditional-B79BD6.svg)](https://github.com/szl-holdings/lutar-lean/blob/main/BOUNTY.md)
[![SLSA L1](https://img.shields.io/badge/SLSA-L1_honest-green.svg)](https://slsa.dev)
[![DCO](https://img.shields.io/badge/DCO-required-orange.svg)](https://developercertificate.org)

---

## What this is

Every claim SZL makes about AI governance traces to a versioned, machine-checked source. This repository is that paper trail: the preprints, thesis versions, and open problems that underpin the proof backbone.

The repository preserves 26 thesis source versions (v1 through v26). The public Zenodo concept DOI **[10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926)** currently resolves to the published v21 record ([10.5281/zenodo.20490218](https://doi.org/10.5281/zenodo.20490218)); v22–v26 are repository source versions and must not be described as separately DOI-published until matching Zenodo records exist.

---

## Contents

| Directory | What it is |
|---|---|
| [`preprints/puriq/`](preprints/puriq/) | PURIQ preprint — formal specification of the Λ trust aggregator |
| [`thesis/ouroboros/`](thesis/ouroboros/) | Ouroboros thesis — the full governance substrate, 26 versions |
| [`bounty/`](bounty/) | Open mathematical challenges — characterize uniqueness under weaker conditions |
| [`prior-art/`](prior-art/) | Prior-art disclosures for IP protection |

---

## The thesis in brief

SZL's core thesis: AI governance should produce **cryptographic receipts** — not dashboards — and the trust math behind those receipts should be **machine-checked in a proof kernel**, not claimed in marketing copy.

**Latest version:** v26 — *Governed Post-Determinism (GPD), Locked-Eight Edition*

Key milestones:
- **8 formulas in the locked-proven registry** at proof snapshot `5cfaf9a3b55fd75e8a2a1197502a93dd8ca68be3`: receipt replay, DAG acyclicity, FIFO ordering, ledger conservation, bounded coupling, Reed–Solomon recovery, entropy budget, append-only monotonicity. The distinct frozen Doctrine-v11 count baseline is `c7c0ba17` (749/14/163).
- **~185 theorems** machine-checked across Waves 11–23 (CI-green, not in the locked 8).
- **Λ uniqueness:** Conditional uniqueness is proven axiom-free (Theorem U). **Conjecture 1 is machine-checked false and disproved as stated**; its counterexample is published.
- **Open bounty:** Characterize or prove uniqueness under weaker conditions. See [`bounty/`](bounty/).

Full proof library and commit history: **[szl-holdings/lutar-lean](https://github.com/szl-holdings/lutar-lean)**

---

## Honest proof status

| Tier | Count | What it means |
|---|---|---|
| **Published locked registry** | **8** — F1, F4, F7, F11, F12, F18, F19, F22 | Proof terms checked at snapshot `5cfaf9a3…`; registry count is exact. Release audit must capture per-declaration `#print axioms` output. |
| **Machine-checked (experimental)** | ~185 | CI-green across Waves 11–23. Real work, honest stage. Not in the locked count. |
| **Open questions** | 2 | Weaker-condition Λ uniqueness and Khipu BFT safety (Conjecture 2). Conjecture 1 itself is disproved as stated. |

---

## Cite this work

```bibtex
@misc{szl2026governed,
  title  = {Governed Post-Determinism: A Proof-Backed Substrate for Consequential AI},
  author = {Lutar, Stephen P.},
  year   = {2026},
  doi    = {10.5281/zenodo.19944926},
  url    = {https://doi.org/10.5281/zenodo.19944926}
}
```

---

**[SZL Holdings](https://a-11-oy.com)** · Apache-2.0 code · CC BY 4.0 papers · Concept DOI [10.5281/zenodo.19944926](https://doi.org/10.5281/zenodo.19944926)

<sub>No production ATO claimed · repository-scoped SLSA L1 · Λ = Conjecture 1 (advisory, not a theorem) — the original unconditional uniqueness statement is disproved as stated (machine-checked counterexample published; conditional Theorem U holds) · Not affiliated with Defense Unicorns</sub>
