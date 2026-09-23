# Live Estate Audit

## Purpose

The live audit is a local, read-only Ouroboros loop. It captures GitHub and Hugging Face metadata, builds the draft registry, validates duplicate/canonical rules, and writes the unresolved-gap report.

## Prerequisites

- Python 3.10+
- Network access to GitHub and Hugging Face
- Optional `GITHUB_TOKEN` and `HF_TOKEN` environment variables for private metadata visibility

Tokens are read from the environment only. The collector never prints or writes credential values.

## Run

```powershell
$env:GITHUB_TOKEN = "<read-only GitHub token>"
$env:HF_TOKEN = "<read-only Hugging Face token>"
python .\tools\run_estate_audit.py
```

## Outputs

```text
data/snapshots/github_repositories.json
data/snapshots/huggingface_models.json
data/snapshots/huggingface_datasets.json
data/snapshots/huggingface_spaces.json
data/estate_registry.json
reports/unresolved_gaps.json
```

## Safety boundary

- Read-only network calls only.
- No Hub/GitHub mutations.
- No releases, deployments, tags, or branch changes.
- No credential logging.
- Generated registry remains `UNREVIEWED` until source-level classification is completed.
