# Live Estate Audit

The collector makes read-only GitHub and Hugging Face API requests, binds four
inventory snapshots to an unsigned SHA-256 receipt, and supplies an offline
registry compiler. Completion means the observed API pagination finished within
the declared credential scope. It does not prove every private repository is
visible, checkpoint quality, deployment readiness, or authorization to publish.

## Prerequisites and credentials

Use Python 3.10 or later. Authentication is required by default. GitHub credentials
come from `GH_TOKEN`, `GITHUB_TOKEN`, or the existing `gh auth token` cache. Hugging
Face credentials come from `HF_TOKEN`, supported Hub environment aliases, or
`huggingface_hub.get_token()` when that optional package is installed. Values are
never printed, saved in receipts, or passed on a command line. The collector does
not write to credential caches or request a replacement token.

The collector checks the GitHub user identity and active membership in
`szl-holdings`, and the Hugging Face identity and membership in `SZLHOLDINGS`.
Missing credentials or failed identity/membership checks stop collection. A
fine-grained token may expose fewer private resources than its owner's account;
membership alone does not prove organization-wide private visibility. The receipt
therefore records `TOKEN_VISIBLE_NOT_ORG_TOTAL` and
`all_private_resources_visible: false`.

`--public-only` explicitly requests anonymous collection and never loads cached
credentials. This mode has lower rate limits and cannot produce an authenticated
public projection. Both CLIs support `--help` without credential or network access.

## Authenticated capture and public projection

Keep raw authenticated snapshots in a local directory outside a public checkout.
Only the explicit public projection should be considered for public review:

```powershell
python .\tools\capture_estate_snapshots.py ..\estate-private\snapshots --public-output data\snapshots
python .\tools\run_estate_audit.py --skip-capture --snapshots data\snapshots
```

The positional collector output remains compatible with the original CLI. Its
default is `data/snapshots`; when using authentication, supply an explicit private
output as above. `--public-output` exports only rows whose observed `private`
value is exactly `false`. It omits authenticated account names, private names and
private counts, recalculates hashes, and records
`PUBLIC_PROJECTION_OF_AUTHENTICATED_CENSUS` plus the parent receipt's hash. The raw
receipt and authenticated metadata remain local. The projection helper is also
available as `export_public_snapshot(raw_root, public_root)` for offline export.

Each inventory follows provider `Link` pagination. Limits (`--max-pages`, default
1000; `--workers`, default 4, maximum 8) are explicit safety bounds, never silent
truncation. Duplicate identifiers, unknown visibility, another organization,
malformed links, cursor cycles, filter drift, missing pagination evidence on a
full page, and HTTP failures make the result incomplete. All requests require the
expected HTTPS origin and reject redirects before forwarding credentials.

GitHub rows include the observed default-branch `source_revision`. A provider 409
on an empty repository is recorded with `EMPTY_REPOSITORY` and no revision.
Hugging Face rows preserve `sha`, observed license metadata and Space `runtime`.
Missing license or runtime metadata remains null. Space `RUNNING` is an API
observation and does not establish a successful application probe. Source and
metadata observations span the receipt's collection interval, not one atomic
provider transaction.

## Receipt and pipeline outcomes

The four compatible JSON arrays are:

```text
github_repositories.json
huggingface_models.json
huggingface_datasets.json
huggingface_spaces.json
snapshot_receipt.json
```

`snapshot_receipt.json` records collection times, local Git SHA and dirty state,
exact collector and pagination-module hashes, credential presence/validation,
per-kind observed counts, pagination completion, file counts and file hashes.
It explicitly records `signature_status: UNSIGNED`: hashes establish byte
consistency, not trusted signer identity. Collection first replaces any old
success receipt with `IN_PROGRESS`. A failed run preserves a failure receipt and
does not publish partial arrays as a completed snapshot set. Old arrays may
remain on disk but cannot pass receipt verification after a failed collection.

The runner verifies every snapshot hash/count before compiling. `--skip-capture`
is entirely offline. `--reviews PATH` passes revision-bound source reviews to the
compiler. `--registry`, `--gaps`, and `--receipt` choose explicit local outputs.
Build and validation logs are retained beside the audit receipt; logs for raw
authenticated input can contain private names and must remain local.

The audit process uses distinct exit statuses:

| Exit | Meaning |
|---|---|
| 0 | Pipeline finished and registry review/gap gates passed; no publication authorized |
| 1 | Capture, integrity, or build failed; inspect the retained receipt and logs |
| 2 | Artifacts were built, but validation, unresolved gaps, or unreviewed entries block audit closure |

`complete: true` in an audit receipt means its stages finished; check `status`,
stage outcomes and gap counts before interpreting the result. The runner never
reports blanket PASS while gaps remain and always sets
`publication_authorized: false`. It performs no Hub/GitHub mutation, release,
deployment, tag, or branch change.

## Regression checks

```powershell
python -m unittest tests.test_capture_estate_snapshots tests.test_run_estate_audit tests.test_build_estate_registry
python -m unittest tests.test_estate_pagination tests.test_inventory_privacy
```

The fixtures cover provider pagination, credentials and origin confinement,
metadata preservation, public projection privacy, receipt tampering, partial
failure, offline replay and blocked validation. Live receipts are a separate
evidence layer from these synthetic tests.
