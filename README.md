# SZL Hugging Face Frontier

Payload `SZL-HF-FRONTIER-2026-08-29`.  
CTO order `CTO-HF-FRONTIER-2026-09-04`.

This repository is the **execution tracker** for the model and kernel estate on Hugging Face `SZLHOLDINGS` and GitHub `szl-holdings`.
It holds the CTO work orders and lane ledgers together with standard-library Python tools that audit the
estate fail-closed: an offline wave-contract runner (`payload.py`), an evidence-completeness kernel
(`compose/`), and a census → source-review → draft-registry pipeline (`tools/`, `validators/`) whose committed
outputs CI rebuilds from retained bytes. Nothing here trains, publishes to the Hub, or authorizes a release.

It is not a flagship product. It does not make the forty-three model repositories counted by the 2026-08-29
payload (`SEED_MODELS` in `SZL_HF_FRONTIER_WIRE.py`) frontier by adding larger cards.

<!-- szl:header v1 -->
<!-- Native identity: szl-brand@4309f6fce89179331b0b3ed8c99494e76c5be256; Orbit v2 icon. -->
<p>
  <a href="https://github.com/szl-holdings">
    <img src="https://raw.githubusercontent.com/szl-holdings/szl-brand/4309f6fce89179331b0b3ed8c99494e76c5be256/kit/logos/orbit-v2/suite/szl-icon-32.svg" alt="SZL Holdings — Orbit v2" width="32" height="32" />
  </a>
</p>

**Control before action. Evidence after.**

[Product](https://a-11-oy.com) · [Proof](https://a11oy.net) · [GitHub organization](https://github.com/szl-holdings)
<!-- /szl:header -->

## Doctrine

- Fail closed.
- Signed is not correct.
- Live is not qualified.
- Published failing tests stay failed.
- A roadmap card is not a model SKU.
- Software is not a checkpoint.

## Public lanes

1. **ReceiptAgent** — governed action admission. The model proposes; the controller authorizes.
2. **Khipu** — grounded navigation and calibrated abstention.
3. **Research organs** — Chaski and future cuts. Research-only until they beat disclosed baselines.

## Evidence lattice

`compose/evidence_lattice.py` is the machine-checkable evidence-completeness check for
the entire estate. It refuses to infer trained weights from a Hub listing,
deployment from CI, qualification from HTTP health, or signer identity from a
digest. It checks revision and time binding, returns untrusted completeness,
and always leaves release authorization to an external trusted controller. See
[`docs/EVIDENCE_LATTICE_KERNEL.md`](docs/EVIDENCE_LATTICE_KERNEL.md).

## Critical clusters

| ID | Order | Hub artifacts (`SZLHOLDINGS/…`) | Tracking issue |
|---|---|---|---|
| C1 | Quarantine ReceiptAgent v3 | `szl-receiptagent-qwen35-0.8b-v3` | [#2](https://github.com/szl-holdings/szl-hf-frontier/issues/2) |
| C2 | Repair or relabel Khipu-abstain | `SZL-Khipu-1.5B-abstain` | [#3](https://github.com/szl-holdings/szl-hf-frontier/issues/3) |
| C3 | Fix published kernel CI | `szl-lambda-gate`, `szl-governed-norm` | [#4](https://github.com/szl-holdings/szl-hf-frontier/issues/4) |
| C4 | Remove unsafe serialization | `szl-blocked`, `szl-provctl`, `szl-formulas`, `szl-ouroboros`, `szl-nemo` | [#5](https://github.com/szl-holdings/szl-hf-frontier/issues/5) |
| C5 | Quarantine failed Chaski line | `chaski`, `chaski-5050`, `A11OY-MINI` | [#6](https://github.com/szl-holdings/szl-hf-frontier/issues/6) |
| C6 | Unblock admission and provenance surfaces | `szl-blocked`, `szl-provctl` | [#7](https://github.com/szl-holdings/szl-hf-frontier/issues/7) |

The machine-readable orders are in [`data/cto-orders.json`](data/cto-orders.json); the order itself is
[`docs/CTO_ORDER.md`](docs/CTO_ORDER.md). Issue state is the live status; this table is not.

## Lane push

| ID | Order | Ledger | Tracking issue |
|---|---|---|---|
| L1 | ReceiptAgent tournament on one hidden Governed Model Bench | [`data/l1_candidates.json`](data/l1_candidates.json) | [#8](https://github.com/szl-holdings/szl-hf-frontier/issues/8) |
| L2 | Khipu abstention bench with coverage-risk and invented-identifier rate | [`data/l2_khipu.json`](data/l2_khipu.json) | [#9](https://github.com/szl-holdings/szl-hf-frontier/issues/9) |
| L3 | Chaski stays research-only until a held-out JSON/refusal gate exists | [`data/l3_chaski.json`](data/l3_chaski.json) | [#10](https://github.com/szl-holdings/szl-hf-frontier/issues/10) |

`compose/lanes.py` and `compose/waves.py` read these ledgers and refuse (exit non-zero) if any of them names a
winner, a frozen operating point, a selected L3 candidate, or a ready estate.

## Requirements

- Python 3.10 or later, standard library only. No install step. The suite and every CI step were run on
  CPython 3.10, 3.11, 3.12 and 3.13; CI pins 3.12 (`.github/workflows/payload.yml`).
- [`requirements.txt`](requirements.txt) lists optional packages that tests and CI do not use:
  `huggingface-hub` (credential-cache lookup in `tools/capture_estate_snapshots.py`; required by the owner-run
  legacy Hub writer `tools/cto_hub_honesty_payload.py`, which refuses to run in CI) and `torch` (CUDA presence
  probe in `szl_estate_operational.py` and `SZL_HF_FRONTIER_WIRE.py`).
- The repository is private. Clone with Git credentials that can read `szl-holdings`
  (for example `gh auth login`, then `gh auth setup-git`):
  `git clone https://github.com/szl-holdings/szl-hf-frontier.git`.

## Run it (offline, read-only)

```bash
python3 payload.py --offline                 # wave contract; "winner": null, "estate": "NOT READY"
python3 -m compose.waves                     # all-wave closer; never claims ready
python3 szl_estate_operational.py --selftest # GMB rule baseline, invented-id refusal; no network
python3 SZL_HF_FRONTIER_INVESTOR.py --selftest
python3 tools/verify_estate_evidence.py      # rebuild reviews, registry, gaps and model report from the retained census
```

`payload.py` always reports `"hub": "DISABLED_OFFLINE_NO_OWNER_AUTHORIZATION"` and `"metal": "NOT_PROBED_OFFLINE"`.
`verify_estate_evidence.py` prints `reproducible: true`, `publication_authorized: false`,
`signature_status: UNSIGNED` and the artifact and unresolved-gap counts of the committed census.
The evidence lattice CLI is documented in [`docs/EVIDENCE_LATTICE_KERNEL.md`](docs/EVIDENCE_LATTICE_KERNEL.md),
the census and registry pipeline in [`docs/LIVE_ESTATE_AUDIT.md`](docs/LIVE_ESTATE_AUDIT.md),
[`docs/SOURCE_CLASSIFICATION.md`](docs/SOURCE_CLASSIFICATION.md) and
[`docs/ESTATE_REGISTRY_PIPELINE.md`](docs/ESTATE_REGISTRY_PIPELINE.md). The `--live` modes of the top-level
scripts and the census collector make GET requests to GitHub, Hugging Face and the product/proof origins; CI
never runs them.

## Verify

The required status check on `main` is the `payload` job of `.github/workflows/payload.yml`; CodeQL also
runs on every pull request. The job's core steps:

```bash
python3 -m unittest discover -v
sha256sum --check lanes/l1/local_evidence_lab/SHA256SUMS
(cd lanes/l1/local_evidence_lab && python3 -B -m unittest -v test_evidence_lab test_selective_calibration test_source_alignment)
python3 tools/verify_estate_evidence.py
python3 tools/reconcile_estate.py --root examples/estate-audit-20260924 --check
python3 tools/verify_model_reconciliation.py --root examples/estate-audit-20260924
```

## Proof boundary

A green run proves that the committed census, source reviews, draft registry, gap report and model-evidence
report are internally consistent and reproducible offline from retained bytes; that the frozen local evidence
lab matches `SHA256SUMS`; and that the gates refuse to name a winner, an operating point, READY, or a Hub write.

It does **not** prove model quality or training (a file listing is not trained weights), deployment or runtime
health of any Space or site, signer identity (every receipt here is `UNSIGNED`; SHA-256 shows byte consistency
only), or present estate state: the committed census is dated 2026-09-29 and the bundled lattice snapshot holds
2026-09-12 observations. `publication_authorized` is always `false`; release authorization belongs to a separate
trusted controller.

## Surfaces

- Product: https://a-11-oy.com
- Proof: https://a11oy.net
- Hub: https://huggingface.co/SZLHOLDINGS
- Org: https://github.com/szl-holdings
- Flagship: https://github.com/szl-holdings/a11oy
- Forge: https://github.com/szl-holdings/szl-forge
- Kernels: https://github.com/szl-holdings/szl-kernels
- Khipu: https://github.com/szl-holdings/szl-khipu

Related open work already on Forge: #101 estate audit, #102 execution queue E1–E5. This tracker is the HF-frontier slice of that work, not a second doctrine.
