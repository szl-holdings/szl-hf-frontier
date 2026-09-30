"""Fail-closed, unsigned comparison of one retained A11oy domain readback.

This is an offline observer, not a publisher, attestor, CI gate or author verifier.
The caller's pinned GitHub revision is a comparison value only. In particular,
an environment-reported build revision is not proof of deployed file bytes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


SPACE_ID = "SZLHOLDINGS/a11oy"
HF_ORIGIN = "https://szlholdings-a11oy.hf.space"
SPACE_API = "https://huggingface.co/api/spaces/" + SPACE_ID
BUILD_INFO = HF_ORIGIN + "/api/build-info"
MAX_RECEIPT_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_AGE_SECONDS = 3600
FUTURE_TOLERANCE_SECONDS = 60
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")
BOOL_FIELDS = frozenset({
    "remote_mutations", "automatic_redirect_following", "browser_observation",
    "credentials_read", "arbitrary_response_links_followed", "follow_redirects",
    "body_exceeded_cap", "private", "disabled", "devMode", "readOnly",
    "receipt_minted", "promotion_eligible",
    "hf_content_revision_is_github_source_revision",
    "runtime_revision_matches_independent_github_main",
})


class VerificationError(ValueError):
    """A stable failure code with no promotion or partial-success fallback."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def require(condition: bool, code: str) -> None:
    if not condition:
        raise VerificationError(code)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in obj, "DUPLICATE_JSON_KEY")
        obj[key] = value
    return obj


def _reject_constant(_value: str) -> None:
    raise VerificationError("NON_FINITE_JSON_NUMBER")


def _finite_float(value: str) -> float:
    result = float(value)
    require(math.isfinite(result), "NON_FINITE_JSON_NUMBER")
    return result


def strict_json(raw: str | bytes) -> Any:
    """Reject duplicate keys recursively, invalid UTF-8, and NaN/Infinity."""
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="strict")
        require(type(raw) is str, "JSON_INPUT_TYPE_INVALID")
        return json.loads(raw, object_pairs_hook=_unique_object,
                          parse_constant=_reject_constant, parse_float=_finite_float)
    except VerificationError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        raise VerificationError("MALFORMED_JSON") from error


def _object(value: Any, code: str) -> dict[str, Any]:
    require(type(value) is dict, code)
    return value


def _sha(value: Any, code: str) -> str:
    require(type(value) is str and SHA_RE.fullmatch(value) is not None, code)
    return value


def _int(value: Any, code: str, minimum: int = 0) -> int:
    require(type(value) is int and value >= minimum, code)
    return value


def _flags(value: Any, depth: int = 0) -> None:
    require(depth <= 64, "JSON_NESTING_EXCESSIVE")
    if type(value) is dict:
        for key, nested in value.items():
            if key in BOOL_FIELDS:
                require(type(nested) is bool, "BOOLEAN_FLAG_TYPE_INVALID")
            _flags(nested, depth + 1)
    elif type(value) is list:
        for nested in value:
            _flags(nested, depth + 1)


def _timestamp(value: Any) -> dt.datetime:
    require(type(value) is str and "T" in value, "TIMESTAMP_INVALID")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise VerificationError("TIMESTAMP_INVALID") from error
    require(parsed.tzinfo is not None and parsed.utcoffset() == dt.timedelta(0),
            "TIMESTAMP_NOT_UTC")
    return parsed.astimezone(dt.timezone.utc)


def _fresh(timestamp: dt.datetime, now: dt.datetime, max_age: int) -> None:
    age = (now - timestamp).total_seconds()
    require(age >= -FUTURE_TOLERANCE_SECONDS, "FUTURE_OBSERVATION")
    require(age <= max_age, "STALE_OBSERVATION")


def _media_type(row: dict[str, Any]) -> str:
    headers = _object(row.get("headers"), "HEADERS_MISSING_OR_INVALID")
    lowered = [key.lower() for key in headers]
    require(len(lowered) == len(set(lowered)), "AMBIGUOUS_HEADER_KEYS")
    content_type = headers.get("content-type")
    require(type(content_type) is str, "CONTENT_TYPE_MISSING")
    return content_type.split(";", 1)[0].strip().lower()


def _exact_response(row: dict[str, Any], endpoint: str) -> None:
    require(row.get("requested_url") == endpoint, "REQUEST_ENDPOINT_MISMATCH")
    require(row.get("response_url") == endpoint, "FINAL_ENDPOINT_MISMATCH")
    require(type(row.get("status")) is int and row["status"] == 200,
            "SUCCESSFUL_RESPONSE_REQUIRED")
    require(row.get("method") == "GET" and row.get("follow_redirects") is False,
            "READ_ONLY_EXACT_RESPONSE_REQUIRED")
    require(row.get("body_exceeded_cap") is False,
            "COMPLETE_RESPONSE_REQUIRED")
    require(row.get("digest_scope") == "complete_response_body",
            "COMPLETE_RESPONSE_DIGEST_REQUIRED")
    require(_media_type(row) == "application/json", "JSON_CONTENT_TYPE_REQUIRED")
    _int(row.get("observed_body_bytes"), "BODY_BYTE_COUNT_INVALID", 1)
    digest = row.get("observed_body_sha256")
    require(type(digest) is str and DIGEST_RE.fullmatch(digest) is not None,
            "BODY_DIGEST_INVALID")
    require(not row.get("error"), "RESPONSE_HAS_ERROR")


def _single(rows: list[dict[str, Any]], endpoint: str) -> dict[str, Any]:
    matches = [row for row in rows if row.get("requested_url") == endpoint]
    require(len(matches) == 1, "MISSING_OR_AMBIGUOUS_ENDPOINT")
    return matches[0]


def _typed_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return (left.keys() == right.keys()
                and all(_typed_equal(left[key], right[key]) for key in left))
    if type(left) is list:
        return (len(left) == len(right)
                and all(_typed_equal(a, b) for a, b in zip(left, right)))
    return left == right


def _runtime_identity(row: dict[str, Any], expected: str) -> dict[str, Any]:
    _exact_response(row, BUILD_INFO)
    require(row.get("raw_retention") == "complete", "COMPLETE_RAW_JSON_REQUIRED")
    raw = row.get("raw_body_retained")
    require(type(raw) is str, "RAW_JSON_MISSING")
    try:
        raw_bytes = raw.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise VerificationError("RAW_JSON_ENCODING_INVALID") from error
    cap = _int(row.get("byte_cap"), "BYTE_CAP_INVALID", 1)
    require(cap <= 262144, "BYTE_CAP_EXCESSIVE")
    require(len(raw_bytes) == row["observed_body_bytes"] and len(raw_bytes) <= cap,
            "RAW_JSON_BYTE_COUNT_MISMATCH")
    require(hashlib.sha256(raw_bytes).hexdigest() == row["observed_body_sha256"],
            "RAW_JSON_DIGEST_MISMATCH")
    payload = _object(strict_json(raw), "BUILD_INFO_OBJECT_REQUIRED")
    _flags(payload)
    require(_typed_equal(payload, row.get("json")), "RETAINED_JSON_PAYLOAD_MISMATCH")
    require(payload.get("status") == "OBSERVED" and payload.get("service") == "a11oy",
            "A11OY_OBSERVED_CONTRACT_REQUIRED")
    require(payload.get("receipt_minted") is False, "READ_PATH_RECEIPT_MINTED_OR_UNKNOWN")
    build = _object(payload.get("build"), "BUILD_CONTRACT_MISSING")
    require(build.get("state") == "OBSERVED", "BUILD_STATE_NOT_OBSERVED")
    require(build.get("revision_source") == "env:SZL_GIT_SHA",
            "GITHUB_REVISION_SOURCE_NOT_OBSERVED")
    evidence = _object(build.get("field_evidence"), "BUILD_FIELD_EVIDENCE_MISSING")
    require(evidence.get("revision") == "OBSERVED", "REVISION_EVIDENCE_NOT_OBSERVED")
    revision = _sha(build.get("revision"), "RUNTIME_GITHUB_SHA_INVALID")
    require(revision == expected, "RUNTIME_GITHUB_SOURCE_MISMATCH")
    return {
        "endpoint": BUILD_INFO, "observed_at_utc": row["observed_at_utc"],
        "github_revision_observed": revision,
        "revision_source": build["revision_source"], "build_state": build["state"],
        "field_evidence": evidence, "working_tree_reported": build.get("working_tree"),
        "runtime_reported": payload.get("runtime"),
        "raw_body_sha256_verified": row["observed_body_sha256"],
        "raw_body_bytes_verified": len(raw_bytes),
        "identity_evidence": "OBSERVED_ENVIRONMENT_REPORTED_GITHUB_REVISION",
        "immutable_byte_parity_proven": False, "functional_readiness_proven": False,
    }


def _provider_identity(row: dict[str, Any]) -> dict[str, Any]:
    _exact_response(row, SPACE_API)
    provider = _object(row.get("public_api_identity"), "PROVIDER_IDENTITY_MISSING")
    require(provider.get("id") == SPACE_ID, "CANONICAL_SPACE_ID_MISMATCH")
    require(provider.get("host") == HF_ORIGIN
            and provider.get("subdomain") == "szlholdings-a11oy",
            "CANONICAL_SPACE_HOST_MISMATCH")
    require(provider.get("private") is False and provider.get("disabled") is False,
            "PUBLIC_ENABLED_SPACE_REQUIRED")
    content_sha = _sha(provider.get("sha"), "HF_CONTENT_SHA_INVALID")
    runtime = _object(provider.get("runtime"), "HF_RUNTIME_METADATA_MISSING")
    runtime_sha = _sha(runtime.get("sha"), "HF_RUNTIME_SHA_INVALID")
    require(runtime_sha == content_sha, "HF_CONTENT_RUNTIME_REVISION_MISMATCH")
    domains = runtime.get("domains")
    require(type(domains) is list, "PROVIDER_DOMAIN_MAPPING_MISSING")
    domains = [_object(domain, "PROVIDER_DOMAIN_MAPPING_INVALID") for domain in domains]
    names = [domain.get("domain") for domain in domains]
    require(all(type(name) is str for name in names), "PROVIDER_DOMAIN_MAPPING_INVALID")
    require(len(names) == len(set(names)), "PROVIDER_DOMAIN_MAPPING_AMBIGUOUS")
    for domain_name in ("szlholdings-a11oy.hf.space", "a-11-oy.com"):
        matches = [domain for domain in domains if domain["domain"] == domain_name]
        require(len(matches) == 1 and matches[0].get("stage") == "READY",
                "CUSTOM_DOMAIN_MAPPING_NOT_REPORTED_READY")
    require(type(runtime.get("stage")) is str, "HF_STAGE_INVALID")
    return {
        "space_id": SPACE_ID, "host": HF_ORIGIN,
        "hf_content_revision": content_sha, "hf_runtime_revision_reported": runtime_sha,
        "runtime_stage_reported": runtime["stage"], "domains_reported": domains,
        "observed_at_utc": row["observed_at_utc"],
        "public_api_response_sha256_retained": row["observed_body_sha256"],
        "full_public_api_body_digest_verified_locally": False,
        "metadata_evidence": "RETAINED_PUBLIC_API_EXTRACT_NOT_AUTHENTICATED_BY_THIS_TOOL",
        "warning": "RUNNING/READY and the HF SHA do not prove product routes or GitHub file parity.",
    }


def _surface_observations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    surfaces: list[dict[str, Any]] = []
    static_scope_paths = {"https://a11oy.net/api/build-info/", "https://a11oy.net/readyz/"}
    for row in rows:
        url = row["requested_url"]
        if not (url.startswith("https://a11oy.net/") or url.startswith("https://a-11-oy.com/")):
            continue
        observed = {"requested_url": url, "response_url": row.get("response_url"),
                    "observed_at_utc": row["observed_at_utc"], "http_status": row.get("status"),
                    "functional_readiness_proven": False}
        if row.get("error"):
            observed.update({"label": "UNAVAILABLE", "error": row["error"],
                             "evidence_scope": "THIS_OBSERVER_NETWORK_ONLY"})
        elif row.get("status") == 301:
            observed.update({"label": "OBSERVED_REDIRECT_ONLY",
                             "redirect_location": row.get("headers", {}).get("location")})
        elif row.get("status") == 200 and _media_type(row) == "text/html":
            observed["label"] = ("STATIC_ROUTE_HTML_REACHABILITY_ONLY"
                                 if url in static_scope_paths else "HTML_REACHABILITY_ONLY")
            if url in static_scope_paths:
                observed["route_role"] = "CONFIGURED_REGISTRY_ROUTE_NOT_PRODUCT_API"
                observed["explanatory_content_verified"] = False
        elif row.get("status") == 404 and url.startswith("https://a11oy.net/"):
            observed["label"] = "STATIC_PATH_NOT_FOUND_NO_RUNTIME_CLAIM"
        else:
            observed["label"] = "OBSERVED_HTTP_STATUS_ONLY"
        surfaces.append(observed)
    return surfaces


def analyze_receipt(raw_receipt: bytes, expected_github_sha: str, *,
                    now: dt.datetime | None = None,
                    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS) -> dict[str, Any]:
    """Compare a bounded retained receipt to a pin, with no external access."""
    expected = _sha(expected_github_sha, "EXPECTED_GITHUB_SHA_INVALID")
    require(type(raw_receipt) is bytes and len(raw_receipt) <= MAX_RECEIPT_BYTES,
            "RECEIPT_BYTES_INVALID_OR_EXCESSIVE")
    max_age = _int(max_age_seconds, "MAX_AGE_INVALID", 1)
    require(max_age <= 86400, "MAX_AGE_EXCESSIVE")
    if now is None:
        now = dt.datetime.now(dt.timezone.utc)
    require(type(now) is dt.datetime and now.tzinfo is not None
            and now.utcoffset() == dt.timedelta(0), "NOW_MUST_BE_UTC")
    receipt = _object(strict_json(raw_receipt), "RECEIPT_OBJECT_REQUIRED")
    _flags(receipt)
    require(receipt.get("schema") == "szl.domain-readback.v1", "RECEIPT_SCHEMA_UNSUPPORTED")
    policy = _object(receipt.get("request_policy"), "REQUEST_POLICY_MISSING")
    for flag in ("remote_mutations", "automatic_redirect_following", "browser_observation",
                 "credentials_read", "arbitrary_response_links_followed"):
        require(policy.get(flag) is False, "READ_ONLY_REQUEST_POLICY_REQUIRED")
    require(policy.get("method") == "GET", "READ_ONLY_METHOD_REQUIRED")
    rows = receipt.get("responses")
    require(type(rows) is list and 1 <= len(rows) <= 14, "RESPONSE_LIST_INVALID")
    rows = [_object(row, "RESPONSE_OBJECT_REQUIRED") for row in rows]
    require(_int(policy.get("requests_sent"), "REQUEST_COUNT_INVALID", 1) == len(rows),
            "REQUEST_COUNT_MISMATCH")
    require(_int(policy.get("max_requests"), "REQUEST_BUDGET_INVALID", 1) <= 14
            and len(rows) <= policy["max_requests"], "REQUEST_BUDGET_EXCEEDED")
    window = _object(receipt.get("observation_window_utc"), "OBSERVATION_WINDOW_MISSING")
    start, end = _timestamp(window.get("start")), _timestamp(window.get("end"))
    require(start <= end, "OBSERVATION_WINDOW_REVERSED")
    _fresh(start, now, max_age)
    _fresh(end, now, max_age)
    for row in rows:
        require(type(row.get("requested_url")) is str, "REQUEST_URL_INVALID")
        require(row.get("method") == "GET" and row.get("follow_redirects") is False,
                "RESPONSE_READ_ONLY_POLICY_REQUIRED")
        status = row.get("status")
        require(status is None or (type(status) is int and 100 <= status <= 599),
                "HTTP_STATUS_TYPE_OR_RANGE_INVALID")
        observed_at = _timestamp(row.get("observed_at_utc"))
        require(start <= observed_at <= end, "OBSERVATION_OUTSIDE_WINDOW")
        _fresh(observed_at, now, max_age)
    runtime = _runtime_identity(_single(rows, BUILD_INFO), expected)
    provider = _provider_identity(_single(rows, SPACE_API))
    # Revisions keep separate semantic roles even if two repositories happen to
    # share a commit object. Equality alone is neither confusion nor attestation.
    provider["revision_values_equal_to_github_revision"] = (
        provider["hf_content_revision"] == expected)
    return {
        "schema": "szl.source-alignment.local.v1",
        "label": "UNSIGNED_LOCAL_OBSERVATION", "release_chain": "PARTIAL_RELEASE_CHAIN",
        "promotion_eligible": False,
        "created_at_utc": now.isoformat(), "max_observation_age_seconds": max_age,
        "input_receipt_sha256": hashlib.sha256(raw_receipt).hexdigest(),
        "request_count_retained": len(rows), "network_requests_made_by_this_tool": 0,
        "expected_github_sha": expected,
        "caller_pin_role": "COMPARISON_ONLY_NOT_AUTHOR_AUTHENTICATION_OR_RELEASE_AUTHORIZATION",
        "source_identity_match": True, "runtime_identity": runtime,
        "provider_identity_reported": provider,
        "surface_observations": _surface_observations(rows),
        "proof_boundaries": {
            "author_authenticated": False, "release_authorized": False,
            "signed_attestation_verified": False, "immutable_byte_parity_verified": False,
            "exact_head_ci_verified": False, "functional_readiness_verified": False,
            "product_custom_domain_identity_verified": False,
        },
        "limitations": [
            "A matched environment-reported source SHA is not signed or byte-attested release proof.",
            "The expected SHA is caller supplied; no author authentication or release authority is inferred.",
            "Provider metadata is retained public API reporting; the complete API body is not retained here.",
            "Product-domain timeouts remain observer-specific, not evidence of a universal outage.",
            "Registry HTML reachability does not prove explanatory content or product readiness.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--expected-github-sha", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-age-seconds", type=int, default=DEFAULT_MAX_AGE_SECONDS)
    args = parser.parse_args(argv)
    try:
        with args.receipt.open("rb") as source:
            raw = source.read(MAX_RECEIPT_BYTES + 1)
        result = analyze_receipt(raw, args.expected_github_sha,
                                 max_age_seconds=args.max_age_seconds)
        encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
        # Exclusive create is the final authority, including concurrent writers/symlinks.
        with args.output.open("x", encoding="utf-8", newline="\n") as destination:
            destination.write(encoded)
    except VerificationError as error:
        print(json.dumps({"error": error.code, "promotion_eligible": False}), file=sys.stderr)
        return 2
    except FileExistsError:
        print(json.dumps({"error": "OUTPUT_EXISTS_REFUSED", "promotion_eligible": False}),
              file=sys.stderr)
        return 2
    except OSError:
        print(json.dumps({"error": "LOCAL_FILE_OPERATION_FAILED", "promotion_eligible": False}),
              file=sys.stderr)
        return 2
    print(json.dumps({"output": str(args.output.resolve()),
                      "label": result["label"], "release_chain": result["release_chain"],
                      "source_identity_match": True, "promotion_eligible": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
