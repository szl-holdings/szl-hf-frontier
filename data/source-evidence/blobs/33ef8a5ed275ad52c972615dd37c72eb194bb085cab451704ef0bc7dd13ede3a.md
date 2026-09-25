> ARCHIVED 2026-08-26. Canonical: https://github.com/szl-holdings/szl-forge (per repo description); former docs-site content consolidated into https://github.com/szl-holdings/a11oy-net. Statements below are historical, kept for provenance.

> **SZL Holdings** · Doctrine v11 · Λ = Conjecture 1 (advisory, never "green"/theorem) · canonical [a-11-oy.com](https://a-11-oy.com)

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Doctrine v11 LOCKED](https://img.shields.io/badge/Doctrine-v11_LOCKED-d4a444.svg)](https://github.com/szl-holdings/lutar-lean)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19944926.svg)](https://doi.org/10.5281/zenodo.19944926)
[![CI](https://github.com/szl-holdings/szl-cookbook/actions/workflows/ci.yml/badge.svg)](https://github.com/szl-holdings/szl-cookbook/actions)
[![Security Policy](https://img.shields.io/badge/Security-Policy-red.svg)](SECURITY.md)

<div align="center">

# SZL Cookbook

> **DEPRECATED — recipe pages migrated to [`szl-holdings/docs-site`](https://github.com/szl-holdings/docs-site/tree/main/docs/cookbook/recipes) (published through [GitHub Pages](https://szl-holdings.github.io/docs-site/cookbook/)).** This repo remains active only as the source of record for runnable code trees; it is not archived. See [`DEPRECATED.md`](./DEPRECATED.md).

**The first-touch resource for using the SZL platform.**
Worked recipes with explicit evidence states and runnable code where the repository includes it.

[**Recipes**](#-recipes) · [**Quickstart**](#-quickstart-60-seconds) · [**Products**](#-the-two-products) · [**Honesty**](#-honesty-policy) · [**Cite**](#-cite-the-cookbook)

[![Doctrine v11 LOCKED](https://img.shields.io/badge/Doctrine-v11_LOCKED_749%2F14%2F163-0B1F3A?style=flat-square)](https://github.com/szl-holdings/lutar-lean/commit/c7c0ba17)
[![Λ = Conjecture 1](https://img.shields.io/badge/%CE%9B-Conjecture_1-d4a444?style=flat-square)](https://github.com/szl-holdings/lambda-bounty)
[![SLSA L1](https://img.shields.io/badge/SLSA-L1_honest-2C5F2D?style=flat-square)](https://slsa.dev/spec/v1.0/levels)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue?style=flat-square)](LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20434308.svg)](https://doi.org/10.5281/zenodo.20434308)

[Hugging Face](https://huggingface.co/SZLHOLDINGS) · [GitHub Org](https://github.com/szl-holdings) · [Canonical Cookbook](https://szl-holdings.github.io/docs-site/cookbook/)

`receipts.in ≡ receipts.out`

</div>

---

## What this is

The SZL Cookbook is to the SZL platform what the
[Anthropic Cookbook](https://github.com/anthropics/anthropic-cookbook),
[OpenAI Cookbook](https://github.com/openai/openai-cookbook), and
[Hugging Face Cookbook](https://github.com/huggingface/cookbook) are to theirs: a library of
copy-paste-able recipes that show, concretely, **how to use the products**. Here the products are
the two SZL platforms — **a11oy** (the governed command platform) and **killinchu** (drones &
vessels). Each recipe owns its evidence state; the catalog does not make a blanket live claim.

## Choose your route

| Audience | Start here | Ownership |
|----------|------------|-----------|
| **Developer** | [Recipes](#-recipes) and the checked-in code trees | Run code from this repository; read the maintained narrative in the canonical docs site |
| **Evaluator** | [Verify a receipt end-to-end](recipes/01-verify-a-receipt-end-to-end.md) | Check the named artifact and command; do not infer results for other recipes |
| **Investor** | [Canonical Cookbook](https://szl-holdings.github.io/docs-site/cookbook/) and [SZL evidence](https://szl-holdings.github.io/docs-site/evidence/) | Use the published route for product context and evidence boundaries |

## Recipe state contract

- **LIVE**: an observed runtime-backed result with a named source and observation time.
- **SAMPLE**: example input, configuration, or expected-output shape; safe to inspect, not runtime evidence.
- **SIMULATED**: mocked or synthetic execution, including deterministic demonstrations.
- **UNAVAILABLE**: the required endpoint, artifact, or dependency did not produce a usable result.

A runnable command is not proof that it was run. Historical transcripts remain historical until
their source and timestamp are refreshed.

The signature first recipe — **[Verify a receipt end-to-end](recipes/01-verify-a-receipt-end-to-end.md)**
— cryptographically validates a real ECDSA-P256 DSSE signature from the public
[`szl-lake`](https://huggingface.co/datasets/SZLHOLDINGS/szl-lake) dataset in under a minute, with
zero credentials. That is the whole promise of the platform, made runnable.

---

## ⚡ Quickstart (60 seconds)

```python
import base64, json, urllib.request
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
from cryptography.hazmat.primitives import hashes, serialization

LAKE = "https://huggingface.co/datasets/SZLHOLDINGS/szl-lake/resolve/main"
r = json.loads(urllib.request.urlopen(f"{LAKE}/khipu/a11oy_receipts.ndjson").readline())
pub = serialization.load_pem_public_key(
    urllib.request.urlopen("https://raw.githubusercontent.com/szl-holdings/.github/main/cosign.pub").read())

pub.verify(base64.b64decode(r["dsse_sig"]), bytes.fromhex(r["dsse_pae_sha256"]),
           ec.ECDSA(Prehashed(hashes.SHA256())))        # raises if invalid
print("VALID:", r["receipt_id"][:16], "signed by", r["dsse_keyid"])
# => VALID: 4c9c3f2b8d6452d9 signed by szlholdings-cosign
```

Full recipe: **[01 — Verify a receipt end-to-end](recipes/01-verify-a-receipt-end-to-end.md)**.

---

## 📖 Recipes

Each recipe has a hero hook + headline number, quickstart code, a full walkthrough, a BibTeX block,
and "see also" links. Recipes marked **live** run against the deployed Spaces today.

| # | Recipe | Product | Status |
|---|--------|---------|--------|
| 01 | [Verify a receipt end-to-end](recipes/01-verify-a-receipt-end-to-end.md) | a11oy | **live, sig verifies** ✅ |
| 02 | [Deploy the SZL mesh UDS bundle](recipes/02-deploy-5-flagship-uds-bundle.md) | a11oy · killinchu | needs GHCR token |
| 03 | [Fine-tune a customer compliance regime](recipes/03-fine-tune-compliance-regime.md) | a11oy | **live** |
| 04 | [Drone counter-UAS verdict](recipes/04-drone-counter-uas-verdict.md) | killinchu | **live** ✅ |
| 05 | [Memory-attested reasoning](recipes/05-memory-attested-reasoning.md) | a11oy | **live** ✅ |
| 06 | [Verify cosign + Rekor for SLSA L1](recipes/06-cosign-rekor-slsa-l1.md) | a11oy · killinchu | **public Rekor** ✅ |
| 07 | [Build your own domain pack](recipes/07-build-your-own-organ.md) | a11oy | runnable template |
| 08 | [Receipt knot algebra (Reidemeister R1/R2/R3)](recipes/08-receipt-knot-algebra.md) | a11oy | **runnable (this repo)** ✅ |
| 09 | [PAC-Bayes confidence margin](recipes/09-pac-bayes-confidence-margin.md) | a11oy | **runnable (this repo)** ✅ |
| 10 | [Cardano-anchored DSSE blood ledger](recipes/10-cardano-dsse-blood-ledger.md) | a11oy | demo path live; mainnet needs founder creds |
| 11 | [Kitaev surface drift detection](recipes/11-kitaev-surface-drift-detection.md) | killinchu · a11oy | **live** |
| 12 | [Doctrine ledger query (749/14/163)](recipes/12-doctrine-ledger-query.md) | a11oy · killinchu | **live** ✅ |
| 13 | [Build a UDS bundle from scratch](recipes/13-build-uds-bundle-from-scratch.md) | a11oy · killinchu | needs cluster |
| 14 | [Replicate the Walrus α-gap measurement](recipes/14-replicate-walrus-alpha-gap.md) | killinchu | **live decoders** |
| 15 | [Air-gapped install](recipes/15-air-gapped-install.md) | a11oy · killinchu | needs cluster |
| 16 | [CALPHAD inverse-discovery](recipes/16-calphad-inverse-discovery.md) | a11oy | **live** ✅ |
| 17 | [E8 lattice receipt verification](recipes/17-e8-lattice-receipt-verification.md) | a11oy | **live** ✅ |
| 18 | [Governed materials prediction](recipes/18-governed-materials-prediction.md) | a11oy | **live** ✅ |
| 19 | [Inverse-PINN physics discovery](recipes/19-inverse-pinn-physics-discovery.md) | a11oy | **live** ✅ |
| 20 | [Evidence pack for auditors](recipes/20-evidence-pack-for-auditors.md) | a11oy | **live** ✅ |

**Bonus engineering recipes** (TypeScript + Lean, shipped in-repo):
[`knot-calculus-v1`](recipes/knot-calculus-v1/) · [`anatomy-evolved-v1`](recipes/anatomy-evolved-v1/) ·
plus 9 [`claude-code` skills](skills/).

---

## 🧩 The two products

SZL ships **two products on one governed substrate**. Each platform is composed of internal
capabilities — a **reasoning** core (memory-attested inference), a **policy** gate (deny-by-default
governance), and an **operator** console (the nervous system that drives them) — all emitting the
same locked-doctrine receipts.

| Product | Role | Space | Cookbook recipes |
|---|---|---|---|
| **a11oy** 🔬 | Governed command platform — reasoning + policy + operator on one receipt substrate | [Space](https://szlholdings-a11oy.hf.space) | 01, 02, 03, 05, 06, 07, 08, 09, 10, 12 |
| **killinchu** 🦅 | Drones & vessels — counter-UAS Λ-gate (Remote-ID/ADS-B/MAVLink) | [Space](https://szlholdings-killinchu.hf.space) | 04, 06, 11, 12, 13, 14 |

Each product exposes `/v1/honest` reporting the same locked doctrine.

---

## 🤝 Used by

The cookbook recipes are the customer first-touch path into the SZL platform. They are referenced
from:

- The [SZL Holdings org profile](https://github.com/szl-holdings) (landing page).
- The [SZL docs site](https://szl-holdings.github.io/docs-site) cookbook section.
- Each product README's "Try the cookbook recipe" callout.
- Each [Hugging Face Space](https://huggingface.co/SZLHOLDINGS) card's "Cookbook recipes for this Space" section.

> Adopting the cookbook in your own evaluation? Open a PR adding your project here.

---

## 🔍 Honesty policy

Every recipe shows only what **actually works end-to-end** against the live products. Where a step
needs founder credentials or a private resource, it says so plainly:

- **Λ is Conjecture 1**, not a theorem (open `CAUCHY_ND` sorry + missing symmetry axiom). No recipe
  claims otherwise.
- **Doctrine 749/14/163 is LOCKED** at kernel `c7c0ba17`. The cookbook *references* these artifacts;
  it never changes them.
- **SLSA L1 (honest)** — image signing is keyless cosign + public Rekor (recipe 06). Live-Space
  *runtime* receipt signatures are still `PLACEHOLDER` (Sigstore CI pending); the lake receipt used
  in recipe 01 carries a *real* signature that verifies.
- **Cardano** anchoring is demo-seeded, not on-chain mainnet; testnet/mainnet submission needs
  founder credentials (recipe 10).
- **Telemetry** (Remote-ID/ADS-B/MAVLink) is unauthenticated — decoded fields are *claims*, never
  ground truth (recipe 04).

---

## 🧪 Run the in-repo demos

```bash
# Knot calculus + PAC-Bayes (recipes 08, 09)
cd recipes/knot-calculus-v1/code && npm install && npx tsx tests/demo.ts

# Anatomy-evolved smoke tests
cd recipes/anatomy-evolved-v1/code && npm install && npm run test:smoke
```

---

## 📚 Cite the cookbook

```bibtex
@misc{szl_cookbook_2026,
  title        = {SZL Cookbook: Worked recipes for the SZL governed platform},
  author       = {{SZL Holdings}},
  year         = {2026},
  howpublished = {\url{https://github.com/szl-holdings/szl-cookbook}},
  doi          = {10.5281/zenodo.20434308},
  note         = {Doctrine v11 LOCKED 749/14/163, kernel c7c0ba17, Λ = Conjecture 1, SLSA L1 (honest).}
}
```

See [`CITATION.cff`](CITATION.cff) for the machine-readable citation.

---

<div align="center">

**Apache-2.0** · Doctrine v11 LOCKED — 749/14/163 — kernel `c7c0ba17` · Λ = Conjecture 1 · SLSA L1 (honest)

</div>
