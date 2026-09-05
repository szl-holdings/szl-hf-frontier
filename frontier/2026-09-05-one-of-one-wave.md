# Frontier — 2026-09-05 one-of-one wave

Receipt-style record. Nothing asserted that a commit or signature does not prove.

## Landed tonight (commit-pinned)

- Holographic flagship model card → canonical source `szl-holdings/szl-forge@95b54d38`
  (`receiptagent/card/README.md`, 10,720 bytes; fixes markdown-inside-HTML badge defect;
  every receipt-bound number byte-exact: loss 0.1038, 5/5, 6/6, 15/15, 8/8,
  keyId e7f01810aaa97394). HF publication via `tools/publish_receiptagent_v3.py` readback.
- CITATION.cff (Zenodo DOI prep) on main:
  - `szl-holdings/szl-forge@4dbd6996` — SZL-Forge / ReceiptAgent family
  - `szl-holdings/szl-khipu@ea9a5000` — Khipu models + kernels
  - `szl-holdings/immune@105c4ce0` — IMMUNE + hosted NEXUS runtime
- DOI audit: 44 public Hub models; 9 carry concept DOI 10.5281/zenodo.19944926;
  24 real artifacts without DOI (7,482 combined downloads); 11 stubs/fixtures intentionally DOI-less.
- NEXUS×IMMUNE consolidation record + nexus CITATION.cff (szl-holdings/nexus PR,
  branch docs/nexus-immune-consolidation-20260905).
- killinchu effector-guard choke point merged (`szl-holdings/killinchu#411` → `94616fb`).

## Still open

- HF OAuth token lacks write-repos: Hub-side card push requires the publish pipeline or reconnect with write scope.
- Zenodo mint step: enable GitHub–Zenodo integration per canonical repo; one concept DOI per family.
- a11oy #1941 / a11oy-net #148 were closed by the estate lane during the session; watch for successor PRs.

Λ = Conjecture 1 OPEN. Trust ceiling 0.97. Energy UNAVAILABLE.
