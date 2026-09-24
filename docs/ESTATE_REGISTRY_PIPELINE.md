# Estate Registry Pipeline

## Role

`tools/build_estate_registry.py` deterministically converts connector inventory snapshots into a draft registry and unresolved-gap report. It makes no network calls and does not modify any external artifact.

## Required input snapshots

```text
data/snapshots/github_repositories.json
data/snapshots/huggingface_models.json
data/snapshots/huggingface_datasets.json
data/snapshots/huggingface_spaces.json
data/snapshots/snapshot_receipt.json
```

## Run

```bash
python tools/build_estate_registry.py \
  --input data/snapshots \
  --registry data/estate_registry.json \
  --gaps reports/unresolved_gaps.json \
  --reviews data/source_reviews.json
python validators/validate_estate_registry.py data/estate_registry.json --structure-only
python validators/validate_estate_registry.py data/estate_registry.json
python -m unittest tests/test_build_estate_registry.py
```

## Boundaries

- The generated registry is a **draft classification**; `UNREVIEWED` does not mean approved.
- Hub kernel classification is heuristic until source mapping establishes its exact canonical GitHub relation.
- Archive successor links are extracted only where explicitly present in source description text.
- Unknown licenses, absent canonical mappings, and unreviewed relationships remain visible in the gap report.
- No generated file authorizes a public mutation.

## Evidence and exit status

The compiler requires all four inventories and a complete receipt whose file
hashes and counts match the bytes on disk. Identical inputs produce identical
output; the census completion timestamp and source-card observation timestamps
are retained instead of replacing them with compilation time. Measured licenses,
revisions, and provider runtime stages remain observations. A model listing starts
as `EXPERIMENTAL`, not as evidence of training or operational readiness.

Source review records must match the census revision and retained evidence bytes.
Automated source extraction may classify relationships, but cannot assign
`ALIGNED_*`, `MEASURED`, or `REPRODUCIBLE`. Every unresolved canonical route,
source review, lifecycle successor, and provider runtime error remains in the gap
report with an owner. Archived artifacts retain their own canonical identity;
successor links reference another artifact without claiming its ownership.

`--structure-only` checks registry shape and duplicate identity integrity. The
default validator also checks admission gates and exits nonzero while source,
card, or runtime review is incomplete. An audit that writes valid draft artifacts
and then exits blocked is an expected, retained result. It is not a release pass.
The JSON schema is the structural contract; neither it nor a SHA-256 digest
establishes signer identity, model quality, or release authorization.
