# Retained local evidence-admission observation

`local-inference-receipt.json` is the byte-exact September 29, 2026 observation
from the [local evidence lab](../../lanes/l1/local_evidence_lab/README.md).
Its file SHA-256 is
`9b3a3dccda2a8f9a67a538176b7fadc894466530e2c95f2b5039a6665b563190`.

The receipt contains forty real local Ollama responses from two observed model
digests. Actions were synthetic in-memory reads. All twenty authored development
cases per model remain visible, including both models' zero correct explicit
abstentions across their four denial cases. The deterministic fixture gate
rejected nine proposals and admitted 31 useful simulated reads with no
unauthorized simulated reads.

The original measured source is the exact retained predecessor
`9bd505ecf0cc7dead5fea7234b41de4a71521c0a3a79569e5bf9304ed00ad210`.
The compatible verifier additionally checks the original local/synthetic scope;
the observation was not regenerated or resealed under that verifier.

Replay from the repository root:

```sh
sha256sum --check lanes/l1/local_evidence_lab/SHA256SUMS
python -I -B lanes/l1/local_evidence_lab/evidence_lab.py --verify examples/local-evidence-admission-20260929/local-inference-receipt.json
```

This verifies retained bytes and deterministic replay. The receipt is unsigned,
does not authenticate its observer, and supplies no held-out calibration,
production authorization, promotion, provider publication, or domain-readiness
claim. It deliberately retains its original evidence and publication labels.
