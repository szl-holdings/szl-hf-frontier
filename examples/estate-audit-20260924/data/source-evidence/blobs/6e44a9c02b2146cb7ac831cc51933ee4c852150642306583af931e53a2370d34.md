---
title: SZL Sovereign OS
emoji: 🧠
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
short_description: Fail-closed operator kernel. Five verticals.
tags:
  - governance
  - receipts
  - honest-by-design
  - szl-holdings
---

# SZL Sovereign OS

> Control before action. Evidence after.

The missing operator kernel for [szl-holdings](https://github.com/szl-holdings). One Python process. Five organs. Five verticals. Eleven category captures.

**Not a rehost.** vLLM, LangGraph, Llama Guard, Mosaic, Lattice, Guidewire, QuantConnect, Zillow, Sigstore, Electricity Maps, and UDS are *cited leaders of a job*. SZL takes the job, not the code.

## What it runs

| Surface | Honesty |
|---|---|
| Five-organ kernel (YACHAY / YUYAY / YAWAR / OTel / Khipu) | LIVE, fail-closed |
| Λ uniqueness | Conjecture 1 OPEN |
| Energy | UNAVAILABLE (never a fabricated joule) |
| Signing | STRUCTURAL-ONLY hash, not a signature |
| killinchu actuation | SIMULATED |
| Real estate occupancy | UNAVAILABLE |
| Hugging Face live push from this sandbox | ROADMAP until `HF_TOKEN` is in org secrets |

GitHub is canonical. A Hugging Face Space named `SZLHOLDINGS/szl-sovereign-os` is the intended runtime mirror (`sdk: docker`, port 7860). This README does not claim that Space is RUNNING until Hub readback says so.

## Verticals

- [a11oy](https://github.com/szl-holdings/a11oy) — inference
- [killinchu](https://github.com/szl-holdings/killinchu) — defense (SIMULATED actuation)
- [david-leads](https://github.com/szl-holdings/david-leads) — insurance, public data
- [szl-quant](https://github.com/szl-holdings/szl-quant) — paper-only
- [szl-real-estate](https://github.com/szl-holdings/szl-real-estate) — public PLUTO/ACS, not an MLS

## API

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

Doctrine v11 LOCKED · 749/14/163 · kernel `c7c0ba17` · locked-proven 8 · Λ = Conjecture 1 · Apache-2.0
