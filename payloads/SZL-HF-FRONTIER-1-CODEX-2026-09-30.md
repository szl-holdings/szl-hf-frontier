# SZL-HF-FRONTIER-1 - offline executor contract

**Payload ID:** SZL-HF-FRONTIER-1-CODEX-2026-09-30

**Parent:** [reconciled findings](SZL-HF-FRONTIER-1-2026-09-30.md)

**Runtime:** Python 3.10+ standard library only. No installation or credentials.

Implementation: [tools/frontier1.py](../tools/frontier1.py). The original embedded
Python remains in Git history at `1071a3fe96a010f011274d2f820ca5351d0b4eff`;
it is not an approved execution path.

## Safe default and local recording

```sh
# No network, credentials, compute, hardware probing or filesystem writes.
python -I -B tools/frontier1.py

# Replay dated public metadata; no writes or live validation.
python -I -B tools/frontier1.py --observations payloads/evidence/frontier1-public-20260930.json

# Explicit LOCAL receipt recording; never remote execution.
python -I -B tools/frontier1.py --observations payloads/evidence/frontier1-public-20260930.json --record --output-root .frontier1-runs --run-id public-observation-20260930

# Synthetic fixtures; independent of historical executor/pipeline.
python -B -m unittest -v tests.test_frontier1
```

The default does not read environment credentials or marker files. Frontier-1
has no provider/compute clients, subprocess launcher, training, issue, publication,
visibility, deletion or merge operations. WO3 is UNAVAILABLE because compute is
outside this runner; CUDA is NOT_PROBED, not alleged absent.

## Truth and input contract

- Typed keys include repository type and case-sensitive ID. Model and dataset
  `SZLHOLDINGS/SZLHOLDINGS` remain distinct, as do subdirectory merges and legacy
  model/first-class kernel artifacts.
- Only the explicit public observation schema is accepted. `private` must be
  exactly false. Private/unknown visibility fails closed. Private WO5 evidence
  and owner-security material are not accepted input fields.
- Full 40-character revisions are compared with a separate expected-head map.
  These are offline comparisons, not live provider CAS, freshness proof,
  signature verification or publication authority.
- Items have independent outcomes. An error cannot erase other declared items
  or turn staged metadata into DONE. All seven WO statuses are terminal:
  DONE, UNAVAILABLE, FAIL-CLOSED, OWNER-PENDING. STAGED is only a note under
  OWNER-PENDING.
- WO6 is forced to OWNER-PENDING and publish_gate=CLOSED regardless of handler
  output. No confirmation parameter, prefix/date check or marker-file reader
  exists. Digests establish bytes, not authentic human authority.
- Exception text, private paths and arbitrary input fields are not echoed.
  Invalid documents fail closed while retaining all seven status entries.
- The supplied fixture is dated public metadata replay, not a current estate
  census or model qualification. It binds eight model heads, three informational
  profiles, 22 archived sources/23 targets and one exact deprecation README.
  Weight/profile content bodies were not downloaded or hashed; their
  content_hash_status remains NOT_READ. Public README bytes have a full SHA-256.
- WO4 DONE means only the dated target-existence/unarchived observation. WO7 DONE
  means only the existing exact-card banner observation. Neither means remote
  mutation, full original work-order completion, promotion or release.

Observation cutoff: 2026-09-30T13:36:24Z. Immutable README bytes were retrieved
again for exact UTF-8 hashing during source preparation. Archived descriptions
were rechecked against the same 22-source inventory. No private source metadata
or security-event details are included.

## Immutable run receipts

Recording requires an explicit root and restricted run ID. Seven `woN.json`
receipts are written in a new same-filesystem pending directory. Files are flushed
and fsynced. The master inventories full SHA-256 values for exactly these seven
files; it excludes itself and has a detached `master.sha256`. Bytes and status
bindings are re-read before atomic directory rename to the final run path.

Existing runs are immutable. Identical requests verify and return existing bytes;
changed requests or expected-master mismatches fail closed.
`--expected-master-sha256` compares a LOCAL receipt, never provider authority.
Previous runs, unrelated files, owner markers and old masters cannot enter the
inventory. Extra files or changed bytes invalidate readback. Input and executor
bytes have separate full hashes in the master.

The actual local observation run is retained in
[master.json](evidence/frontier1-runs/public-observation-20260930/master.json)
with seven WO receipts and its detached digest. This is an offline replay receipt,
not an owner confirmation or evidence of remote execution.

That immutable run was emitted by `tools/frontier1.py` retained at
`a060b82bc63ac99d4048a2a9e5da0535a3d54e84`, using Python 3.12.14 on Windows.
The dated public input snapshot was assembled from read-only observations;
the master and WO receipts were written by the recorder, not manually assembled.
The producing arguments, from the repository root, were:

```sh
python -I -B tools/frontier1.py --observations payloads/evidence/frontier1-public-20260930.json --record --output-root payloads/evidence/frontier1-runs --run-id public-observation-20260930
```

Its executor SHA-256 is
`d4b9826b2d4f6c20517896168661ebd9866c973605621acd4668f93a0941520f` and its
master SHA-256 is
`de53c9f4f5ae07f133f6fe51d9256c14103e6b9a513b13382156c85bcb7005a5`.
Later source repairs do not rewrite or rebind this historical run. These hashes
bind bytes; the receipt is not an independent execution attestation.

Symlinks and Windows reparse points in existing ancestors are rejected. Run IDs
reject traversal, separators, ADS and reserved device names. An exclusive per-run
directory lock prevents cooperating writers sharing a run ID. Use a locally
controlled output root, not one concurrently writable by an untrusted actor.
These guards do not replace OS isolation.

A write/fsync/rename failure does not return a successful recording. Pending
directories remain for owner inspection; there is no recursive cleanup/deletion.
CLI failures return seven computed statuses and a fixed finalization error.
Ordinary handler exceptions and explicit `SystemExit` requests are isolated into
terminal outcomes. `KeyboardInterrupt` and `GeneratorExit` propagate immediately;
interrupted planning does not claim a complete run.
Process termination, power loss, permission loss or exhausted storage can prevent
any receipt; no finalization is claimed in that case. Abandoned locks require
owner inspection, not automatic stale-lock removal.

## CI effect boundary

The existing `payload` job name, triggers, pinned actions, permissions and all
offline regression/evidence/selftest checks remain. Added steps run Frontier-1
fixtures and planning, followed by `payload.py --offline`. Default `payload.py`
is offline too: no credential inspection, legacy helper launch or CUDA probe.
Its local contract checks remain. The legacy helper CLI refuses CI/GITHUB_ACTIONS
before credential lookup or provider import.

The historical helper contains banner-upload/deletion-proposal functions. They
were not executed or authorized. Removing implicit CI invocation grants no new
publication path. Future owner publication requires separate review, authentic
evidence and concurrency controls. No security setting or protection was changed.

The unchanged CodeQL workflow invokes the pinned organization workflow. CI
success validates tested source only, not WO6 confirmation, GPU availability,
training/evaluation, HF writes, runtime health or release eligibility. The central
queue remains sole merge owner.
