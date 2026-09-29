---
title: Governed Norms - WILLAY classifiers
emoji: "🛡️"
colorFrom: green
colorTo: gray
sdk: static
app_file: index.html
pinned: false
license: apache-2.0
short_description: Inspectable holographic view of a11oy WILLAY classifiers
tags:
  - governance
  - safety
  - refusal-classifiers
  - honest-by-design
  - holographic
---

# governed-norm-holo

Holographic, **inspectable** rendering of the a11oy **WILLAY** refusal classifiers — the
governed-refusal norms. The inverse of a hidden classifier: every rule discloses its
**category, what it fires on, its rationale, and its lineage**.

**Status:** ROADMAP → **LIVE**. Shipped as a static Hugging Face Space:
**[SZLHOLDINGS/governed-norm-holo](https://huggingface.co/spaces/SZLHOLDINGS/governed-norm-holo)**
→ <https://szlholdings-governed-norm-holo.static.hf.space>

## What it does

- Fetches the full classifier list **keyless** from
  `https://szlholdings-a11oy.hf.space/api/a11oy/v1/willay/classifiers`.
- Renders each classifier (category · fires-on · rationale · lineage) plus the doctrine block:
  locked-proven theorems, kernel commit, **trust ceiling 0.97 (never 100%)**, Λ = **Conjecture 1**
  (never green), Khipu = Conjecture 2.

## Honesty labels

- **REPORTED** — relays a11oy's own self-report verbatim; nothing is independently measured here.
- **UNAVAILABLE** — if the source endpoint is unreachable, the page shows an honest blank; it
  never renders a cached or fabricated value.

## Build

`index.html` is a self-contained static page — **0 runtime CDN**, system fonts only, data
fetched client-side at view time. No build step.

## License

Apache-2.0 (see [LICENSE](LICENSE)) — matching the SZL Holdings estate.

---

Part of the SZL Holdings estate · [a-11-oy.com](https://a-11-oy.com) ·
[🤗 SZLHOLDINGS](https://huggingface.co/SZLHOLDINGS) · governed AI you can prove.
