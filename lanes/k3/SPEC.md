# K3 non-publishing canary spec (DISABLED BY DEFAULT)

Schema: szl.k3-canary/v1. Read STATUS.json first: the canary is
DISABLED BY DEFAULT and is executed only after (a) an explicit owner
consent binding to a merged PR commit, (b) an F5
rotation/removal attestation receipt for the baked HF_TOKEN, and
(c) A7 digest evidence for the image actually deployed. Kimi
rulings K9/K10: canary-r4 DONE=MEASURED is unsigned and cannot
substitute for K3; 9b launch stays gated.

## Markers (ordered, all mandatory)

1. ENTRY_STARTED
2. ENTRY_BOOT
3. ENV_VERIFIED
4. DATASET_BOUND
5. KERNELS_READY
6. TRAIN_LOOP_ENTERED
7. CHECKPOINT_WRITTEN
8. CHECKPOINT_VERIFIED

Terminal: DONE.json (complete schema: run_id, image_digest_sha256,
config_hash, metrics_hash, marker_log_hash) or FAILED.json with a
valid failure phase. No other terminal state is admissible.

## Heartbeats

Heartbeat records gap <= 70 seconds. A gap above the bound fails
the evidence set.

## Zero public writes

Canary writes go only to a private scratch repo via a scoped,
throwaway write-only token. Evidence must include before/after
sha256 snapshots proving public estate and provider inventory
unchanged, plus the token denial test (out-of-scope write refused).

## Evidence placement

Evidence lands in the private canary branch/repo only. The
checker performs zero public HF writes and zero Salad mutations.

## Acceptance (binding for this PR)

"Acceptance: the non-publishing canary evidence validator admits
only ordered complete marker sets with heartbeat cadence <= 70s
and a terminal DONE (complete schema) or FAILED.json (valid failure
phase), and rejects every partial, out-of-order, unknown-marker or
cadence-violating fixture; the canary itself remains disabled by
default with execution_authorized=false."
