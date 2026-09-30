# Retained archival source-alignment comparison

Both JSON files are preserved byte for byte from the local research handoff.
`domain-readback.json` contains retained September 29, 2026 public observations;
`source-alignment-final.json` is the unchanged offline comparison made at
`2026-09-30T02:52:37.348521+00:00` with an explicit 21,600-second age window.
The input's SHA-256 matches the output's `input_receipt_sha256`.

This archive records a matching environment-reported A11oy GitHub revision and
the separately reported HF content/runtime revision. It made zero new network
requests and leaves every proof boundary false: author authentication, release
authorization, signed attestation, immutable file parity, exact-head CI,
functional readiness, and custom-domain product identity. The broader archival
window does not change the observer's 3,600-second default or any canonical
release collector. It is not a live release check.

Replay the retained comparison at its original archival evaluation time from
`lanes/l1/local_evidence_lab/` without creating or rewriting evidence:

```python
from datetime import datetime
import json
from pathlib import Path
from source_alignment import analyze_receipt

archive = Path("../../../examples/source-alignment-20260929")
original = json.loads((archive / "source-alignment-final.json").read_bytes())
replayed = analyze_receipt(
    (archive / "domain-readback.json").read_bytes(),
    original["expected_github_sha"],
    now=datetime.fromisoformat(original["created_at_utc"]),
    max_age_seconds=original["max_observation_age_seconds"],
)
assert replayed == original
```

Use `SHA256SUMS` in the [research subtree](../../lanes/l1/local_evidence_lab/README.md)
to check the frozen sources, tests, predecessor, and both observation archives.
Hash matches and deterministic replay establish retained integrity only.
