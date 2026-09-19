# Evidence Lattice Kernel

This dependency-free Python kernel checks whether a declared evidence bundle
is complete for a publication, operation, or promotion goal. It emits
`EVIDENCE_COMPLETE_UNTRUSTED` or `BLOCK`, always with `authorized: false`.
Observation labels, observer names, and receipt hashes do not authenticate a
witness. Release authorization belongs to a separate trusted verifier/controller.

## Evidence contract

Each required layer must pass, bind the asset's immutable revision, and contain
a qualifying evidence row bound to the same revision. Every row records its
capture time and observer. Evidence must be within the snapshot's declared age
limit. The snapshot's `generated_at` is conversion time; it never replaces
evidence capture time.

| Axis | Evidence represented |
|---|---|
| metadata | Provider listing |
| source | Immutable source revision |
| ci | Checks reported for that revision |
| artifact | Identified bytes or a digest-bearing manifest |
| evaluation | Evaluation observations for that revision |
| deployment | Provider deployment and its deployed revision |
| runtime | Application response bound to its deployed revision |
| provenance | Provenance verification for that revision |
| controller | Separate controller decision evidence |

`CALLER_DECLARED` and `DERIVED` rows cannot satisfy required layers.
Provider observations can describe metadata, source, CI, artifacts, or deployment.
Evaluation, runtime, provenance, and controller axes require declared direct
observation or an independent witness. These labels are validated for consistency
but their authenticity is **not** verified by this module.

Root HTTP 200 remains unbound reachability evidence unless the response itself
attests the revision. A provider's deployed SHA is checked separately from its
repository head. Weight filenames remain `artifact: UNKNOWN` until byte identity
or a digest-bearing manifest has been checked.

Research-only, quarantined, deprecated, placeholder, and historical dispositions
remain blocked. No field is inferred from another layer.

## Run and verify

Run from the repository root:

The bundled September 12 snapshot is historical audit evidence, not current
estate status. Its receipt can still be verified; its freshness gate will expire.

```powershell
python -B -m compose.evidence_lattice data/estate-evidence-2026-09-12.json --goal promote --receipt-out evidence-receipt.json
python -B -m compose.evidence_lattice data/estate-evidence-2026-09-12.json --verify-receipt evidence-receipt.json
```

The default command returns an audit regardless of completeness.
`--require-complete` exits 2 if evidence is incomplete or the snapshot is stale
relative to the current clock. It rechecks underlying observation ages, not just
the snapshot age, and emits an explicit `current_check` beside the historical
receipt. It is a completeness check, never sufficient
release authorization. Historical receipt verification is deterministic and does
not assert present readiness. The CLI rejects combining `--verify-receipt` with
`--require-complete`, receipt output, or a new chain pointer.

Identity is `(kind, namespace/name)`. Use
`--select model:SZLHOLDINGS/example-model` for typed selection; an untyped name is
accepted only when unique. Receipts record their typed selection.

Receipt files use atomic, no-overwrite publication on filesystems supporting
hard links. Unsupported filesystems fail with an error. SHA-256 binds canonical
JSON, assessment, selected assets, and an optional previous receipt digest.
`HASH_ONLY_UNSIGNED` establishes content consistency; it supplies no witness
identity, authenticity, freshness authority, or clinical approval.

## Inventory adapter

`tools/estate_to_lattice.py` accepts the dated enriched inventories and direct
HTTP witness file. Only assets explicitly marked `private: false` are exported;
unknown visibility is excluded. Public HTTP references retain only the origin.
Each evidence digest identifies its canonical source record, not model weights.
Capture timestamps must come from the inventory collector.

```powershell
python -I -B tools/estate_to_lattice.py --models models.json --datasets datasets.json --spaces spaces.json --github github.json --space-witness http-witness.json --hf-observed-at 2026-09-12T12:00:00Z --out snapshot.json
```

Use the collector's real capture timestamp in that command. Conversion cannot
refresh old evidence. The GitHub input must include `captured_at_utc`; each
HTTP witness must include its own `observed_at`.

The schema is `szl.evidence-lattice-snapshot/v2`. Minimum snapshot fields:
`schema`, `generated_at`, `observer`, `max_evidence_age_seconds` (1..604800),
and `assets`. Each asset has `id`, `kind`, `revision`, `disposition`,
and `layers`. An evidence row has `uri`, `observation`, `subject_revision`,
`observed_at`, `observer`, and optional `sha256` and `note`.
Malformed timestamps, future observations, duplicate JSON keys, ambiguous
selectors, conflicting chain pointers, and likely credential material fail closed.

## Verification

```powershell
python -B -m unittest discover -v
python -I -B payload.py
```

The suite covers evidence separation, revision and time binding, unknown
visibility, credential redaction, typed identities, receipt tampering, malformed
input, and explicit absence of release authorization.
