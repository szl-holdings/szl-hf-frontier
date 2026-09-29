> **SZL Holdings** · Doctrine v11 · Λ = Conjecture 1 (advisory, never "green"/theorem) · canonical [a-11-oy.com](https://a-11-oy.com)

# developers

> ⚠️ **DEPRECATED — migrated to [`szl-holdings/docs-site`](https://github.com/szl-holdings/docs-site/tree/main/docs/developers) (published at `docs.szlholdings.com`).**
> These pages now live under `docs/developers/` in the unified docs site. The
> **[Holographic Estate](https://szlholdings-a11oy.hf.space/holographic)** link is preserved there.
> This repo is **deprecated but NOT archived** — archival is a later founder step. See [`DEPRECATED.md`](./DEPRECATED.md).

**SZL Holdings developer hub** · Doctrine v11 LOCKED (749 / 14 / 163) · Apache-2.0

[![Doctrine v11](https://img.shields.io/badge/Doctrine-v11_LOCKED-3b82f6?style=flat-square)](https://github.com/szl-holdings/.github/tree/main/doctrine) [![SLSA](https://img.shields.io/badge/SLSA-Build_L1_honest_%C2%B7_L2_roadmap-22c55e?style=flat-square)](https://slsa.dev/spec/v1.0/levels) [![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg?style=flat-square)](LICENSE)

> Every action signed. Every decision gated. Every receipt verifiable.

API reference, 5-minute quickstart, MCP integration guide, substrate packages, and runnable
examples for the two SZL products — **a11oy** (command platform) and **killinchu** (drones &
vessels) — each a full left-nav application. Λ uniqueness is **Conjecture 1 (not a theorem)**;
the service images are **SLSA Build L1 (honest)** — cosign keyless-signed and Rekor-anchored,
verifiable via `cosign verify`. **SLSA L2 verified build-provenance (isolated builders) is on
the roadmap**; L3 / FedRAMP / Iron Bank / CMMC are **not claimed**.

> **Note (2026-06-03):** Contents are mirrored into
> [`docs-site/developers/`](https://github.com/szl-holdings/docs-site/tree/main/developers).
> This repo is the canonical developer-facing entry point; bookmark either location.

## Two products, one substrate

| Product | Role | Live base URL |
|-------|------|---------------|
| **a11oy** | Command platform — Λ-gate router, policy + receipt substrate, with built-in **reasoning / policy / operator** capabilities | `https://szlholdings-a11oy.hf.space` |
| **killinchu** | Drones &amp; vessels field tool — counter-UAS + maritime picture (12 endpoints) | `https://szlholdings-killinchu.hf.space` |

Both endpoints return Doctrine v11 from `/healthz`: 749 declarations / 14 axioms / 163 sorries,
locked at `c7c0ba17`. **Λ = Conjecture 1, NOT a theorem.** Service images are SLSA Build L1 honest (cosign keyless-signed, Rekor-anchored); L2 verified-provenance on the roadmap (L3 not claimed).

### ◇ Featured: the Holographic Estate

See the frontier tier rendered as one live 3D holographic lattice — 56 governed surfaces
(frontier organs, energy, counter-UAS, governance, PINN, anatomy), each lit by a live a11oy
endpoint. Vendored WebGL2 with optional WebGPU; **0 runtime CDN**. Every value carries its
honesty label. Mobile-friendly.

**[Open the Holographic Estate →](https://szlholdings-a11oy.hf.space/holographic)**

## Docs

| File | Purpose |
|------|---------|
| [QUICKSTART.md](./QUICKSTART.md) | 5-min end-to-end: list MCP tools, sign a payload, verify |
| [API_REFERENCE.md](./API_REFERENCE.md) | Every public endpoint across both products |
| [MCP_INTEGRATION.md](./MCP_INTEGRATION.md) | Wire Hatun-MCP into Claude Desktop / Cursor |
| [GRAPHQL.md](./GRAPHQL.md) | Unified GraphQL surface |
| [SUBSTRATE_PACKAGES.md](./SUBSTRATE_PACKAGES.md) | Build your own organ on the substrate |
| [SDK_DROP_IN.md](./SDK_DROP_IN.md) | 3-line SDK wrap for any existing app |
| [EXAMPLES/](./EXAMPLES/) | Runnable Python + config examples |

## Honesty boundary

- The **service images are SLSA Build L1 (honest)** — cosign keyless-signed (Fulcio + Rekor),
  verifiable via `cosign verify`. **SLSA L2 verified build-provenance (isolated builders +
  verified provenance attestation) is on the roadmap.** **L3 is NOT claimed.** The mesh **bundle
  artifact** is signed but **not yet provenance-attested** (owner-only GHCR grant pending).
- **Locked-proven PURIQ formulas = exactly 8** — {F1, F4, F7, F11, F12, F18, F19, F22} @ `c7c0ba17` (Lean 4, kernel-clean; F4/F7/F22 landed 2026-06-10); rest Roadmap.
- Λ-uniqueness = **Conjecture 1** (open bounty, `CAUCHY_ND` sorry open) — **not a theorem**.
- cosign DSSE signatures are real ECDSA-P256-SHA256; receipts are real-DSSE-or-honestly-UNSIGNED.
- No FedRAMP / Iron Bank / CMMC claims — see [docs-site compliance](https://szl-holdings.github.io/docs-site/compliance).
- Section 889 = exactly **5 vendors**.

*Doctrine v11 LOCKED · 749/14/163 · c7c0ba17 · Apache-2.0*

Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>

