# Estate Registry Pipeline

## Role

`tools/build_estate_registry.py` deterministically converts connector inventory snapshots into a draft registry and unresolved-gap report. It makes no network calls and does not modify any external artifact.

## Required input snapshots

```text
data/snapshots/github_repositories.json
data/snapshots/huggingface_models.json
data/snapshots/huggingface_datasets.json
data/snapshots/huggingface_spaces.json
```

## Run

```bash
python tools/build_estate_registry.py \
  --input data/snapshots \
  --registry data/estate_registry.json \
  --gaps reports/unresolved_gaps.json
python validators/validate_estate_registry.py data/estate_registry.json
python -m unittest tests/test_build_estate_registry.py
```

## Boundaries

- The generated registry is a **draft classification**; `UNREVIEWED` does not mean approved.
- Hub kernel classification is heuristic until source mapping establishes its exact canonical GitHub relation.
- Archive successor links are extracted only where explicitly present in source description text.
- Unknown licenses, absent canonical mappings, and unreviewed relationships remain visible in the gap report.
- No generated file authorizes a public mutation.
