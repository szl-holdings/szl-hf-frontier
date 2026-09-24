# Source classification and retained evidence

`tools/classify_estate_sources.py` reads every explicitly public row in a complete
four-file inventory and produces conservative source review candidates. It makes
read-only provider requests. Output is automated extraction, never human review,
`ALIGNED_*` approval, evidence of model training, or release authorization.

```powershell
python tools/classify_estate_sources.py --input data/snapshots --output data/source_reviews.json --evidence-dir data/source-evidence --workers 4
python tools/classify_estate_sources.py --input data/snapshots --output data/source_reviews.json --evidence-dir data/source-evidence --offline
python -m unittest tests.test_classify_estate_sources -v
```

The existing authenticated session can supply `GITHUB_TOKEN` or `GH_TOKEN`, and
`HF_TOKEN` or `HUGGING_FACE_HUB_TOKEN`. Tokens are used only as authorization
headers, never written to output or included in exceptions. The summary records
only whether credentials were supplied. Public unauthenticated operation is also
supported; authentication or rate-limit errors remain visible as safe error codes.
Requests permit only HTTPS on the credential's intended provider origin, without
URL credentials or custom ports. Redirects can remain on the same origin only;
cross-origin redirects cannot forward a bearer token. HF resolve-cache redirects
on `huggingface.co` remain supported.

All four snapshots are required. Rows need the literal boolean `private: false`;
missing, unknown, string, and private markers never authorize source capture.
GitHub uses the collector's `source_revision` where available; otherwise it reads
the current default-branch commit. New captures first recheck the exact GitHub
repository identity and public visibility, then fetch its README at the immutable
SHA. Earlier retained observations must not be presented as having performed this
later-added visibility recheck.
Hugging Face uses each observed `sha`, requests the exact revision's metadata and
file inventory, confirms public visibility, then reads that revision's README.
Each source body and normalized file inventory is retained with SHA-256, byte
count, immutable source URL, and revision. No weight files are downloaded. A file
inventory is the provider's revision metadata, not an independent LFS-byte audit.
GitHub descriptions and arbitrary file contents are not a source-code audit.

There are at most eight concurrent workers (four by default), a bounded card size,
and request timeouts. A normal GitHub row needs one metadata request and one README
request if its revision is already in the inventory; a normal HF row needs two requests. Missing revisions
need one additional metadata request. No scans of commit history or weight bytes
are performed. Failed or absent cards retain `UNAVAILABLE_WITH_REASON` and do not
silently become evidence of a source-backed artifact.

Each output row is keyed by the same stable `id` as the estate registry and contains
`artifact_class`, `status`, `canonical`, `links`, `audit`, `classification`,
`observed_revision`, `evidence`, `source_claims`, `production_claims`, and
`candidate_recommendations`. `review_method` is `automated_source_extraction`.
Every evidence entry contains `kind`, `url`, `revision`, `sha256`, `path`,
`source_path`, `bytes`, and `status`. An unavailable card may have no evidence or
only a file inventory; this is an unresolved row, not a completed source review.
Observations preserve their original observation time on offline reclassification.
Offline mode verifies each retained file hash, revision, and card text before use.
Stored evidence paths are repository-relative and resolve against the evidence
directory's repository root, independently of the current working directory.
Absolute paths, traversal, and paths resolving outside the evidence directory are
rejected. Observation and blob bytes are unchanged during offline reclassification.

| Classification | Meaning and boundary |
| --- | --- |
| `canonical_source` | Inspected public GitHub source identity; no assertion that its implementation is correct or running. |
| `mirror_distribution` | Card explicitly points to one source repository present in the public GitHub census. The mapping still requires review. |
| `successor_deprecated` | Explicit lifecycle declaration says deprecated or superseded. No replacement is inferred from a name. |
| `archived_provenance` | Provider marks the GitHub repository archived. Its own URL remains the provenance record. |
| `experimental_blocked` | Explicit source status declares research, experimental, quarantined, or blocked. |
| `operational_runtime_surface` | A Space's target role. This does not assert a healthy endpoint or working inference. |
| `support_artifact` | Dataset or explicitly described tracker, reference, fixture, or documentation source. |
| `unresolved` | Evidence does not justify a more specific source role. |

Source mapping uses explicit source/canonical/upstream/implementation or successor
context around GitHub links. Linked repositories must exist in the same public
GitHub inventory. Mere links, repository-name similarity, private identities,
missing routes, or conflicting mappings cannot establish a canonical route.
The exact linked subpath is retained as a claim, but the classifier verifies only
repository membership; it does not assert that a linked branch or subdirectory
exists. `NEEDS_CANONICAL_MAPPING` remains for absent, ambiguous, or unverified
mapping. The artifact's own URL remains its canonical ownership identity; a shared
implementation repository belongs in `links.github`, avoiding false duplicate
ownership among distributions. Archives point to `links.successor` only for an
explicit, census-verified replacement and keep their own provenance URL.

HF model rows remain `EXPERIMENTAL` unless explicit software or blocked metadata
supports a narrower status. Finding `model.safetensors`, a signed card, an SDK,
or `RUNNING` metadata cannot prove trained weights, evaluation, safe deployment,
or qualification. The Khipu family routing in
[`families/KHIPU_FAMILY_ROUTING.md`](families/KHIPU_FAMILY_ROUTING.md) must remain
separate: the research baseline, quantized derivative, CPU demonstration, and
unpromoted candidates are distinct artifacts with distinct evidence boundaries.

Affirmative production/live claim candidates are extracted from bounded prose
clauses while ignoring fenced code and nearby negations. This is a triage aid,
not an exhaustive semantic judgment. Claims require separate source-bound runtime
evidence; no probe is fabricated. Candidate recommendations include an owner and
reason. Unresolved source classifications remain unresolved in the registry.
