"""Fail-closed F5/A7 build policy checker (audit only).

Schema szl.build-policy/v1. Digest pins or nothing: tag-only image
refs fail closed. Any secret-bearing build context fails closed.
A remediation claim requires an f5_rotation_attestation receipt.
No network, no sleeps, stdlib only.
"""

import re

SCHEMA = "szl.build-policy/v1"

IMAGE_REF = re.compile(r"^[^@]+@sha256:[0-9a-f]{64}$")

SECRET_PATTERNS = (
    ("hf_token_mention", re.compile(r"HF_TOKEN", re.IGNORECASE)),
    ("hf_token_value", re.compile(r"hf_[A-Za-z0-9]{20,}")),
    ("ghp_token_value", re.compile(r"ghp_[A-Za-z0-9]{36,}")),
)

RECEIPT_KIND = "f5_rotation_attestation"


class ValidationError(Exception):
    """Fail-closed policy rejection."""


def _require(condition, message):
    if not condition:
        raise ValidationError(message)


def check_image_ref(ref):
    """Admit only name@sha256:<64 lowercase hex>; tags fail."""
    _require(isinstance(ref, str) and ref, "image ref must be nonempty")
    if not IMAGE_REF.match(ref):
        raise ValidationError(
            "image ref must be digest-pinned, tag-only inadmissible:"
            " %r" % ref)
    return True


def scan_text_for_secrets(text):
    """Return [(pattern_name, start_index)] secret hits."""
    _require(isinstance(text, str), "text must be a string")
    hits = []
    for name, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            hits.append((name, match.start()))
    return hits


def check_build_context(files):
    """files: {path: content}. Any secret hit fails closed."""
    _require(isinstance(files, dict), "build context must be a dict")
    _require(len(files) > 0, "empty build context rejected")
    for path, content in files.items():
        _require(isinstance(path, str) and path, "path must be nonempty")
        _require(isinstance(content, str), "content must be a string")
        hits = scan_text_for_secrets(content)
        if hits:
            raise ValidationError(
                "secret pattern %r found in %r" % (hits[0][0], path))
    return True


def check_manifest_pins(manifest):
    """manifest: {service: image_ref}. Every ref must be pinned."""
    _require(isinstance(manifest, dict), "manifest must be a dict")
    _require(len(manifest) > 0, "empty manifest rejected")
    for service, ref in manifest.items():
        _require(isinstance(service, str) and service,
                 "service name must be nonempty")
        try:
            check_image_ref(ref)
        except ValidationError as exc:
            raise ValidationError("service %r: %s" % (service, exc))
    return True


def require_f5_rotation_receipt(receipt):
    """Remediation needs rotation attestation with receipt sha256."""
    _require(isinstance(receipt, dict), "receipt must be an object")
    _require(receipt.get("kind") == RECEIPT_KIND,
             "receipt kind must be %r" % RECEIPT_KIND)
    _require(receipt.get("revoked") is True,
             "baked token must be revoked/rotated first")
    sha = receipt.get("receipt_sha256")
    _require(isinstance(sha, str), "receipt sha256 must be a string")
    _require(len(sha) == 64, "receipt sha256 must be 64 hex chars")
    _require(all(c in "0123456789abcdef" for c in sha),
             "receipt sha256 must be lowercase hex")
    return True
