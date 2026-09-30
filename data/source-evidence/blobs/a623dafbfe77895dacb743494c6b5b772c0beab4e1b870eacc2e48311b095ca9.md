---
title: SZL Sovereign OS
emoji: 🧠
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
short_description: Folded operator-kernel source. Standalone Space retired.
tags:
  - governance
  - receipts
  - honest-by-design
  - szl-holdings
---

# SZL Sovereign OS

> Control before action. Evidence after.

Retained source for the SZL operator-kernel hologram. One Python process. Five organs. Five verticals. Eleven category captures.

**Not a rehost.** vLLM, LangGraph, Llama Guard, Mosaic, Lattice, Guidewire, QuantConnect, Zillow, Sigstore, Electricity Maps, and UDS are *cited leaders of a job*. SZL takes the job, not the code.

## What it contains

| Surface | Honesty |
|---|---|
| Five-organ kernel (YACHAY / YUYAY / YAWAR / OTel / Khipu) | SOURCE-IMPLEMENTED, fail-closed |
| Λ uniqueness | Conjecture 1 OPEN |
| Energy | UNAVAILABLE (never a fabricated joule) |
| Signing | STRUCTURAL-ONLY hash, not a signature |
| killinchu actuation | SIMULATED |
| Real estate occupancy | UNAVAILABLE |
| Standalone Hugging Face Space publication | RETIRED — publisher removed; do not recreate from this repository |

GitHub retains this source for provenance and historical reproducibility. Canonical product/runtime authority is [a11oy](https://github.com/szl-holdings/a11oy) and [platform](https://github.com/szl-holdings/platform). The historical Space identity `SZLHOLDINGS/szl-sovereign-os` is retired as a standalone publication target; this repository does not claim that Space is RUNNING or eligible for recreation.

## Verticals represented in this source

- [a11oy](https://github.com/szl-holdings/a11oy) — inference
- [killinchu](https://github.com/szl-holdings/killinchu) — defense (SIMULATED actuation)
- [david-leads](https://github.com/szl-holdings/david-leads) — insurance, public data
- [szl-quant](https://github.com/szl-holdings/szl-quant) — paper-only
- [szl-real-estate](https://github.com/szl-holdings/szl-real-estate) — public PLUTO/ACS, not an MLS

## Local API

The retained source can still be exercised locally for tests and reproducibility; that does not establish a hosted runtime.

```
GET  /healthz
GET  /api/selftest
GET  /api/verticals
GET  /api/captures
POST /api/organs/integrity
POST /api/verticals/run     {"id":"a11oy","signal":"..."}
POST /api/captures/run      {"id":"vllm","signal":"..."}
```

```bash
python -m unittest discover -s tests -v
python app.py
```

See [FOLD.md](FOLD.md) for the archive-bound authority boundary.

Doctrine v11 LOCKED · 749/14/163 · kernel `c7c0ba17` · locked-proven 8 · Λ = Conjecture 1 · Apache-2.0
