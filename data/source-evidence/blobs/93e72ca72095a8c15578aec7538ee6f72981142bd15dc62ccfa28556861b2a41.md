# szl-otel-mesh

> **SUPERSEDED (archived repo — read this first).** This repository is
> **GitHub-archived (read-only)**. The canonical-home declaration below —
> "single canonical home of the UDS mesh per ADR-0001" — is **historical**: it
> was accurate when written (2026-06-03/06-28), before this repo's scope
> narrowed to Layer-5 OTel observability and the CRDT mesh-coordination work
> moved to the active successor, **[`szl-mesh`](https://github.com/szl-holdings/szl-mesh)**.
> `szl-mesh` is the active repo for ongoing mesh work; this repo remains the
> archived, read-only home of the OTel span-schema history described below.
> See the amendment note in [`CANONICAL.md`](CANONICAL.md).

> **Renamed 2026-06-28:** This repository was renamed from `uds-mesh` to `szl-otel-mesh` for naming clarity — OTel observability scope vs. CRDT mesh coordination in [`szl-mesh`](https://github.com/szl-holdings/szl-mesh). GitHub redirects old URLs automatically; update any bookmarks.


> **CANONICAL HOME.** This repository is the single canonical home of the UDS mesh
> per **[ADR-0001](CANONICAL.md)** (ACCEPTED 2026-06-03). A non-canonical fold-copy at
> `szl-holdings/uds-bundles/mesh/` has been demoted to a thin pointer back here; the
> prior "absorbed into szl-fleet-overlay / ARCHIVED" claim was inaccurate and is corrected.
> See [`CANONICAL.md`](CANONICAL.md).


> **Trademark / non-affiliation notice.** SZL Holdings' use of "UDS" references Defense Unicorns' Unified Defense Stack (USPTO Serial 99831122). SZL Holdings is **not affiliated with Defense Unicorns**. SZL contributions to the UDS ecosystem are made through upstream PRs. Upstream **UDS Core** (AGPL-3.0) is used as a **deployment pattern / dependency only — it is not vendored or adopted into this repository**. See https://defenseunicorns.com/uds

**Layer 5 (Observability) of the SZL 7-layer architecture.**
UDS cross-component span schemas + DSSE governance receipts onto the Khipu Merkle DAG.

[![tests](https://github.com/szl-holdings/szl-otel-mesh/actions/workflows/tests.yml/badge.svg)](https://github.com/szl-holdings/szl-otel-mesh/actions/workflows/tests.yml)
[![scorecard](https://github.com/szl-holdings/szl-otel-mesh/actions/workflows/scorecard.yml/badge.svg)](https://github.com/szl-holdings/szl-otel-mesh/actions/workflows/scorecard.yml)
&nbsp;Doctrine **v11 LOCKED** · 749 / 14 / 163 · SLSA L1 honest · L2 verified-provenance on roadmap · DOI [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276)

**Deployment story:** this repo is the **observability spine (Layer 5)**. The UDS Operator entry point is [szl-fleet-overlay](https://github.com/szl-holdings/szl-fleet-overlay); Zarf bundle manifests live in [uds-bundles](https://github.com/szl-holdings/uds-bundles); CRDT coordination is [szl-mesh](https://github.com/szl-holdings/szl-mesh); the live reference deployment is [szl-uds-deployment](https://github.com/szl-holdings/szl-uds-deployment).

---

`uds-mesh` is the observability spine that lets a single governed decision be
followed as it crosses the five SZL backend services. Every service emits OpenTelemetry
spans that share **one identical cross-service envelope** (`szl.mesh.*`), so the mesh can
reconstruct the inter-service call graph from spans alone and bind each span to a
DSSE governance receipt on the Khipu Merkle DAG.

## The five span schemas

The two products — **a11oy** and **killinchu** — are composed from capability services
(policy/gate, memory, operator). Each emits one span schema (schema filenames retain the
original internal service identifiers — immutable infra coordinates kept verbatim; their
user-facing roles are **CHAPAQ** egress immune-inspector, **YACHAY** reasoning cortex, and the
operator console):

| Schema | Service | Span names | Role |
|---|---|---|---|
| [`a11oy.graph`](schemas/spans/a11oy.graph.yaml) | a11oy command | `.lambda` · `.automorphism` · `.position` | graph-Λ tool-call spans |
| [`sentra.gate`](schemas/spans/sentra.gate.yaml) | a11oy — **CHAPAQ** egress immune-inspector (policy/gate) | `.evaluate` · `.attest` · `.fail_closed` | fail-closed safety-gate spans |
| [`amaru.sync`](schemas/spans/amaru.sync.yaml) | a11oy — **YACHAY** read-only reasoning cortex (memory) | `.merge` · `.receipt` · `.drift_alert` | convergent data-sync spans |
| [`killinchu.courier`](schemas/spans/killinchu.courier.yaml) | killinchu | `.dispatch` · `.deliver` · `.verify` | receipt-courier / transport spans |
| [`rosie.decision`](schemas/spans/rosie.decision.yaml) | a11oy — operator console | `.evaluate` · `.witness` · `.replay` | governed-decision witness spans |
| [`sda.detection`](schemas/spans/sda.detection.yaml) | killinchu SDA (`khipu-sda-core`) | `.dtid` · `.characterize` · `.twa` · `.fuse` | clean-room anomaly / Threat-Warning spans (advisory Λ, Conjecture 1) |

The sixth schema, **`sda.detection`** (v18.0), was added with the clean-room anomaly/SDA
capability (`szl-sda` / killinchu SDA — inspired by True Anomaly's Mosaic, capability only,
no proprietary code). Each anomaly/threat detection emits one signed span — through the
Mosaic-derived stages DTID → CHARACTERIZE → TWA → FUSE — bound to the Khipu Merkle DAG.
The anomaly score feeds the killinchu 13-axis Λ-gate as the advisory `anomaly_twa` axis
(Λ = Conjecture 1, never a theorem); confidence is a bounded conformal **ESTIMATE**.

All six carry the same `szl.mesh.*` attributes (`organ`, `receipt_hash`,
`dsse_payload_type`, `lambda_value`, `governance_drift`, optional `image_digest` /
`upstream_organ`). As of **v17.2.1** (this strike) `a11oy.graph` was brought to full
cross-service parity — it had been the last schema on the legacy `szl.graph.*`-only
block (and carried a YAML defect); it now also carries the unified envelope, with
its graph-specific fields retained additively.

## Make it real — what landed

- **`mesh/sdk/`** — first-class Python + TypeScript SDKs that emit Λ-signed spans:
  - W3C Trace Context (`traceparent`) propagation per the
    [W3C REC](https://www.w3.org/TR/trace-context/).
  - DSSE PAE v1 receipt per span (same scheme as `formula_receipts.py`).
  - **BLS aggregate verification** of a batch of receipt signatures — one
    aggregate check instead of N.
- **`mesh/conformance/`** — 33-test executable conformance suite (schemas ↔ SDK ↔
  cross-organ envelope ↔ BLS round-trip ↔ W3C). Runs in CI on every push.

```bash
pip install pyyaml pytest
pytest mesh/conformance/ -v        # 33 passed
```

## Architecture in context (7 layers)

```
L1 Substrate (lutar-lean formal proofs)   L5 Observability  →  uds-mesh  ← you are here
L2 Formula runtime                          L6 MCP / agents  →  hatun-mcp
L3 Backend services (a11oy / killinchu)     L7 Operator consoles
L4 Λ-gate exporters  →  vsp-otel
```

`uds-mesh` (L5) defines the schemas; `vsp-otel` (L4) is the Λ-gate exporter that
signs and forwards spans matching these schemas; `hatun-mcp` (L6) emits and
validates the receipts these spans bind to.

## Formal references (lutar-lean — all in OPEN PRs, cite honestly)

| Used for | Lean reference | Status |
|---|---|---|
| BLS batch receipt verify | [`Lutar.Round11.BLS.aggregate_verify`](https://github.com/szl-holdings/lutar-lean/pull/180) (`FrontierBLSAggregation.lean`) | **theorem** (sorry-free), PR #180 |
| Byzantine quorum n≥3f+1 (mesh consensus) | [`Lutar.Round10.ByzantineQuorum.szl_satisfies_bft`, `quorum_intersection_ge`](https://github.com/szl-holdings/lutar-lean/pull/178) | **theorem** for §1–§3; optimality lower-bound is an honest tagged `sorry` (Conjecture 1), PR #178 |
| Receipt-chain knot algebra | [`Lutar.Knot` R1/R2/R3](https://github.com/szl-holdings/lutar-lean/pull/166) (`ReidemeisterConjecture.lean`) | R3 **theorem** (proved); R1/R2 are stated **axioms** (zero sorry, two axioms), PR #166 |
| DSSE governance receipts | [`Lutar.Round10.CryptoDSSE.dsse_classical_euf_cma`](https://github.com/szl-holdings/lutar-lean/pull/179) (`CryptoDSSEClassical.lean`) | conditional EUF-CMA **theorem** (0 real sorry), PR #179 |
| Rekor Merkle inclusion | [`Lutar.Round10.CryptoRekor.rekor_inclusion_completeness`](https://github.com/szl-holdings/lutar-lean/pull/179) | completeness **theorem**; soundness is an honest tagged `sorry` (Conjecture 1), PR #179 |

> **Λ is Conjecture 1 — never a theorem.** Cited PRs are open on `lutar-lean`, not yet
> merged to `main`. Where a formula carries a tagged honest `sorry`, the proved part
> is cited as a theorem and the open part as Conjecture 1. HONESTY OVER CHECKLIST.

## Honest crypto boundary

The SDK's BLS aggregation runs over a prime-field additive homomorphism that
exercises the **same algebraic identity** proved in `aggregate_verify`
(`Σ σ_i = (Σ sk_i)·h`). Production swaps the backend for `blst`/`py_ecc` BLS12-381;
the verify contract is identical. Runtime coordinate: `szl-holdings/a11oy/szl_bls_aggregate.py`.

## Layout

```
schemas/spans/        the 5 organ span schemas (v17.2.x)
mesh/sdk/             mesh.py · mesh.ts · package.json · README — Λ-signed emitters
mesh/conformance/     pytest conformance suite (33 tests)
formula_receipts.py   DSSE PAE v1 + HMAC receipt layer for the 5 anchor formulas
extended-attestations.jsonl   hash-chained SLSA provenance
pepr/                 PQC governance policy (Pepr)
```

---

*License: Apache-2.0 · © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173*

Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>

---

*Canonical-home declaration — see [`CANONICAL.md`](CANONICAL.md) and ADR-0001.*

Doctrine v11 — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (never a theorem) · SLSA L1 honest · L2 verified-provenance on roadmap · HONESTY OVER CHECKLIST

