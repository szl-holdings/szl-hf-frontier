# L1 — ReceiptAgent tournament

Lane: ReceiptAgent.
Tracker: `szl-holdings/szl-hf-frontier` #8.
Depends on: C1 (quarantine v3).

## Contract

One hidden Governed Model Bench. Compare nano, v2, 1.5B, and base.
Select one winner only at a declared false-ALLOW budget.
Merge and quantize only after full-precision qualification.

## Current measured state

- `winner`: null
- `operating_point`: null
- `szl-receiptagent-qwen35-0.8b-v3`: NON_RELEASE_PLACEHOLDER / `publication_eligible=false`
- Do not invent a winner. `payload.py` refuses if anyone does.

## Done when

A single promoted ReceiptAgent ID exists with sample-level logs,
controller-bound vs naked decode, and a published risk point.

Not done. Not a SKU. Not LIVE.

## Local research harness

[`local_evidence_lab/`](local_evidence_lab/README.md) contains the frozen Python
capability-admission and selective-calibration prototype and a replayable local
observation. The forty observed model responses use authored development cases
and synthetic in-memory actions. They do not select a tournament winner, supply
held-out calibration, or qualify a ReceiptAgent for promotion.

Ordinary CI checks exact source and receipt bytes, runs the 64 offline tests, and
replays the retained observation. It does not start Ollama or perform GPU/model
inference. The lane's winner and operating point remain unset.
