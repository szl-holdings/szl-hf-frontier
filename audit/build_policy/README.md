# audit/build_policy

Fail-closed F5/A7 build policy checker for the SZL estate.

- check_build_policy.py: stdlib only, offline.
  - check_image_ref: admits only name@sha256:<64 lowercase hex>.
  - scan_text_for_secrets: flags HF_TOKEN mentions, hf_ and ghp_
    token values.
  - check_build_context: any secret hit in any file fails closed.
  - require_f5_rotation_receipt: remediation needs an
    f5_rotation_attestation receipt (revoked=true + receipt sha256).
- test_check_build_policy.py: offline fixtures, delenv ambient
  credentials, no network, no sleeps.

Out of scope (by design): rotation execution, builds, pulls,
publication, credential contents, Salad activity, five-organ 503,
hf-sync freeze.
