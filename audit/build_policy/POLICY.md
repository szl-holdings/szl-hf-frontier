# F5/A7 build policy (audit-only, fail closed)

Schema: szl.build-policy/v1.

## F5: baked HF_TOKEN

No build context governed by this policy may contain HF_TOKEN,
hf_... token values, or ghp_... token values. F5's baked HF_TOKEN
must be revoked/rotated, with an attestation receipt, BEFORE any
remediation is claimed. Order is mandatory: rotate first, then
remediate. A remediation claim without an f5_rotation_attestation
receipt is inadmissible.

## A7: digest pinning

Every image reference must be name@sha256:<64 lowercase hex>.
Tag-only references fail closed. Mutable tags are inadmissible;
the deployed digest must be the pinned digest.

## Scope (unchanged holds)

Rotation/revocation execution, builds, pulls/retagging,
publication, credential contents, Salad activity, and any "fix"
for the five-organ 503 or the hf-sync freeze are OUT OF SCOPE.
This policy changes no existing operational hold.

## Acceptance (binding for this PR)

"Acceptance requires a fail-closed policy mandating
revocation/rotation of F5's baked HF_TOKEN before remediation,
secrets-free builds with provenance receipts, and an immutable
digest-pinned A7 image, while leaving every existing operational
hold unchanged."
