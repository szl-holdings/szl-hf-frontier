"""Hostile offline tests for the exact retained domain-readback contract."""

import contextlib
import copy
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import source_alignment as observer


GITHUB_SHA = "5" * 40
HF_SHA = "8" * 40
STAMP = "2026-09-29T21:23:28+00:00"
NOW = dt.datetime(2026, 9, 29, 21, 30, tzinfo=dt.timezone.utc)


def fixture():
    payload = {
        "status": "OBSERVED", "service": "a11oy",
        "build": {"state": "OBSERVED", "revision": GITHUB_SHA,
                  "revision_source": "env:SZL_GIT_SHA", "version": None,
                  "version_source": "UNKNOWN", "working_tree": "UNKNOWN",
                  "working_tree_source": "UNKNOWN",
                  "field_evidence": {"revision": "OBSERVED", "version": "UNKNOWN",
                                     "working_tree": "UNKNOWN"}},
        "runtime": {"python": "3.14.7", "platform": "linux"}, "receipt_minted": False,
    }
    raw = json.dumps(payload, separators=(",", ":"))
    runtime_row = {
        "requested_url": observer.BUILD_INFO, "response_url": observer.BUILD_INFO,
        "method": "GET", "follow_redirects": False, "observed_at_utc": STAMP,
        "status": 200, "headers": {"content-type": "application/json"},
        "body_exceeded_cap": False, "digest_scope": "complete_response_body",
        "byte_cap": 65536, "observed_body_bytes": len(raw.encode()),
        "observed_body_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "raw_retention": "complete", "raw_body_retained": raw, "json": payload,
    }
    provider_row = {
        "requested_url": observer.SPACE_API, "response_url": observer.SPACE_API,
        "method": "GET", "follow_redirects": False, "observed_at_utc": STAMP,
        "status": 200, "headers": {"content-type": "application/json; charset=utf-8"},
        "body_exceeded_cap": False, "digest_scope": "complete_response_body",
        "observed_body_bytes": 99328, "observed_body_sha256": "a" * 64,
        "public_api_identity": {
            "id": observer.SPACE_ID, "host": observer.HF_ORIGIN,
            "subdomain": "szlholdings-a11oy", "private": False, "disabled": False,
            "sha": HF_SHA, "runtime": {"sha": HF_SHA, "stage": "RUNNING",
                "domains": [{"domain": "a-11-oy.com", "stage": "READY"},
                            {"domain": "szlholdings-a11oy.hf.space", "stage": "READY"}]}},
    }
    static_rows = [{
        "requested_url": url, "response_url": url, "method": "GET",
        "follow_redirects": False, "observed_at_utc": STAMP, "status": 200,
        "headers": {"content-type": "text/html; charset=utf-8"},
        "raw_body_prefix": "<!doctype html><title>Static surface scope</title>",
    } for url in ("https://a11oy.net/", "https://a11oy.net/api/build-info/",
                  "https://a11oy.net/readyz/")]
    timeout_row = {
        "requested_url": "https://a-11-oy.com/api/build-info", "response_url": None,
        "method": "GET", "follow_redirects": False, "observed_at_utc": STAMP,
        "status": None, "error": "TimeoutError: The read operation timed out",
    }
    return {
        "schema": "szl.domain-readback.v1",
        "observation_window_utc": {"start": "2026-09-29T21:23:00Z",
                                   "end": "2026-09-29T21:24:00Z"},
        "request_policy": {"method": "GET", "remote_mutations": False,
            "automatic_redirect_following": False, "browser_observation": False,
            "credentials_read": False, "arbitrary_response_links_followed": False,
            "requests_sent": 6, "max_requests": 14},
        "responses": [runtime_row, provider_row, *static_rows, timeout_row],
        # Deliberately dishonest input interpretations must never become output authority.
        "interpretation": {"promotion_eligible": True, "functional_readiness": "PROVEN"},
    }


def encode(receipt):
    return json.dumps(receipt, separators=(",", ":")).encode("utf-8")


def refresh_runtime(row, payload):
    raw = json.dumps(payload, separators=(",", ":"))
    row.update({"json": payload, "raw_body_retained": raw,
                "observed_body_bytes": len(raw.encode()),
                "observed_body_sha256": hashlib.sha256(raw.encode()).hexdigest()})


class SourceAlignmentTests(unittest.TestCase):
    def analyze(self, receipt=None, expected=GITHUB_SHA, **kwargs):
        return observer.analyze_receipt(encode(receipt or fixture()), expected,
                                        now=NOW, **kwargs)

    def rejected(self, receipt, code, **kwargs):
        with self.assertRaises(observer.VerificationError) as caught:
            self.analyze(receipt, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_matching_identity_stays_unsigned_partial_ineligible(self):
        result = self.analyze()
        self.assertEqual(result["label"], "UNSIGNED_LOCAL_OBSERVATION")
        self.assertEqual(result["release_chain"], "PARTIAL_RELEASE_CHAIN")
        self.assertIs(result["promotion_eligible"], False)
        self.assertIs(result["source_identity_match"], True)
        self.assertEqual(result["expected_github_sha"], GITHUB_SHA)
        self.assertEqual(result["provider_identity_reported"]["hf_content_revision"], HF_SHA)
        self.assertTrue(all(value is False for value in result["proof_boundaries"].values()))

    def test_wrong_source_sha_is_rejected(self):
        self.rejected(fixture(), "RUNTIME_GITHUB_SOURCE_MISMATCH", expected="6" * 40)

    def test_hf_sha_cannot_replace_github_pin(self):
        self.rejected(fixture(), "RUNTIME_GITHUB_SOURCE_MISMATCH", expected=HF_SHA)

    def test_equal_values_still_preserve_source_and_provider_roles(self):
        receipt = fixture()
        provider = receipt["responses"][1]["public_api_identity"]
        provider["sha"] = provider["runtime"]["sha"] = GITHUB_SHA
        result = self.analyze(receipt)
        self.assertEqual(result["runtime_identity"]["revision_source"], "env:SZL_GIT_SHA")
        self.assertEqual(result["provider_identity_reported"]["hf_content_revision"], GITHUB_SHA)
        self.assertIs(result["provider_identity_reported"]["revision_values_equal_to_github_revision"], True)
        self.assertIs(result["promotion_eligible"], False)

    def test_pin_requires_strict_lowercase_40_hex(self):
        for value in (True, "ABCDEF" * 6 + "ABCD", " 5" + "5" * 39, "5" * 39, "g" * 40):
            with self.subTest(value=value):
                self.rejected(fixture(), "EXPECTED_GITHUB_SHA_INVALID", expected=value)

    def test_stale_observation_is_rejected(self):
        with self.assertRaises(observer.VerificationError) as caught:
            observer.analyze_receipt(encode(fixture()), GITHUB_SHA,
                                      now=NOW + dt.timedelta(hours=2))
        self.assertEqual(caught.exception.code, "STALE_OBSERVATION")

    def test_future_observation_is_rejected(self):
        with self.assertRaises(observer.VerificationError) as caught:
            observer.analyze_receipt(encode(fixture()), GITHUB_SHA,
                                      now=NOW - dt.timedelta(hours=2))
        self.assertEqual(caught.exception.code, "FUTURE_OBSERVATION")

    def test_missing_mapped_runtime_response_is_rejected(self):
        receipt = fixture()
        receipt["responses"].pop(0)
        receipt["request_policy"]["requests_sent"] -= 1
        self.rejected(receipt, "MISSING_OR_AMBIGUOUS_ENDPOINT")

    def test_missing_timestamp_is_rejected(self):
        receipt = fixture()
        del receipt["responses"][0]["observed_at_utc"]
        self.rejected(receipt, "TIMESTAMP_INVALID")

    def test_malformed_raw_json_is_rejected_after_digest_verification(self):
        receipt = fixture()
        row = receipt["responses"][0]
        row["raw_body_retained"] = "{malformed}"
        row["observed_body_bytes"] = len(row["raw_body_retained"].encode())
        row["observed_body_sha256"] = hashlib.sha256(row["raw_body_retained"].encode()).hexdigest()
        self.rejected(receipt, "MALFORMED_JSON")

    def test_recursive_outer_duplicate_json_keys_are_rejected(self):
        raw = encode(fixture()).replace(b'"private":false', b'"private":false,"private":false', 1)
        with self.assertRaises(observer.VerificationError) as caught:
            observer.analyze_receipt(raw, GITHUB_SHA, now=NOW)
        self.assertEqual(caught.exception.code, "DUPLICATE_JSON_KEY")

    def test_recursive_embedded_duplicate_json_keys_are_rejected(self):
        receipt = fixture()
        row = receipt["responses"][0]
        raw = row["raw_body_retained"].replace('"revision":"OBSERVED"',
                                               '"revision":"OBSERVED","revision":"OBSERVED"')
        row.update({"raw_body_retained": raw, "observed_body_bytes": len(raw.encode()),
                    "observed_body_sha256": hashlib.sha256(raw.encode()).hexdigest()})
        self.rejected(receipt, "DUPLICATE_JSON_KEY")

    def test_digest_alteration_is_rejected(self):
        receipt = fixture()
        receipt["responses"][0]["observed_body_sha256"] = "0" * 64
        self.rejected(receipt, "RAW_JSON_DIGEST_MISMATCH")

    def test_body_size_and_parsed_json_disagreement_are_rejected(self):
        receipt = fixture()
        receipt["responses"][0]["observed_body_bytes"] += 1
        self.rejected(receipt, "RAW_JSON_BYTE_COUNT_MISMATCH")
        receipt = fixture()
        receipt["responses"][0]["json"]["build"]["revision"] = "6" * 40
        self.rejected(receipt, "RETAINED_JSON_PAYLOAD_MISMATCH")

    def test_wrong_final_runtime_host_is_rejected(self):
        receipt = fixture()
        receipt["responses"][0]["response_url"] = "https://evil.example/api/build-info"
        self.rejected(receipt, "FINAL_ENDPOINT_MISMATCH")

    def test_wrong_space_id_and_host_are_rejected(self):
        receipt = fixture()
        receipt["responses"][1]["public_api_identity"]["id"] = "OTHER/a11oy"
        self.rejected(receipt, "CANONICAL_SPACE_ID_MISMATCH")
        receipt = fixture()
        receipt["responses"][1]["public_api_identity"]["host"] = "https://evil.example"
        self.rejected(receipt, "CANONICAL_SPACE_HOST_MISMATCH")

    def test_wrong_custom_domain_mapping_is_rejected(self):
        receipt = fixture()
        receipt["responses"][1]["public_api_identity"]["runtime"]["domains"][0]["domain"] = "a11oy.net"
        self.rejected(receipt, "CUSTOM_DOMAIN_MAPPING_NOT_REPORTED_READY")

    def test_wrong_content_type_and_unobserved_build_contract_are_rejected(self):
        receipt = fixture()
        receipt["responses"][0]["headers"]["content-type"] = "text/html"
        self.rejected(receipt, "JSON_CONTENT_TYPE_REQUIRED")
        for section, key, value, code in (
            ("build", "state", "UNKNOWN", "BUILD_STATE_NOT_OBSERVED"),
            ("build", "revision_source", "env:HF_SHA", "GITHUB_REVISION_SOURCE_NOT_OBSERVED"),
            ("field_evidence", "revision", "UNKNOWN", "REVISION_EVIDENCE_NOT_OBSERVED"),
        ):
            receipt = fixture()
            payload = copy.deepcopy(receipt["responses"][0]["json"])
            container = payload["build"] if section == "build" else payload["build"]["field_evidence"]
            container[key] = value
            refresh_runtime(receipt["responses"][0], payload)
            self.rejected(receipt, code)

    def test_truthy_strings_and_boolean_as_integer_are_rejected(self):
        for value in ("false", "true", 0, 1, [], None):
            receipt = fixture()
            receipt["responses"][0]["body_exceeded_cap"] = value
            self.rejected(receipt, "BOOLEAN_FLAG_TYPE_INVALID")
        receipt = fixture()
        receipt["request_policy"]["requests_sent"] = True
        self.rejected(receipt, "REQUEST_COUNT_INVALID")
        receipt = fixture()
        receipt["responses"][0]["observed_body_bytes"] = True
        self.rejected(receipt, "BODY_BYTE_COUNT_INVALID")
        receipt = fixture()
        receipt["responses"][2]["status"] = True
        self.rejected(receipt, "HTTP_STATUS_TYPE_OR_RANGE_INVALID")

    def test_excessive_json_nesting_is_rejected(self):
        receipt = fixture()
        nested = {}
        cursor = nested
        for _ in range(70):
            cursor["nested"] = {}
            cursor = cursor["nested"]
        receipt["extra"] = nested
        self.rejected(receipt, "JSON_NESTING_EXCESSIVE")

    def test_unknown_schema_and_timezone_are_rejected(self):
        receipt = fixture()
        receipt["schema"] = "invented.universal.schema"
        self.rejected(receipt, "RECEIPT_SCHEMA_UNSUPPORTED")
        receipt = fixture()
        receipt["responses"][0]["observed_at_utc"] = "2026-09-29T21:23:28"
        self.rejected(receipt, "TIMESTAMP_NOT_UTC")

    def test_static_route_html_is_not_content_or_product_health_proof(self):
        surfaces = self.analyze()["surface_observations"]
        scope = [row for row in surfaces if row["requested_url"].endswith(("build-info/", "readyz/"))]
        self.assertEqual(len(scope), 2)
        for row in scope:
            self.assertEqual(row["label"], "STATIC_ROUTE_HTML_REACHABILITY_ONLY")
            self.assertEqual(row["route_role"], "CONFIGURED_REGISTRY_ROUTE_NOT_PRODUCT_API")
            self.assertIs(row["explanatory_content_verified"], False)
            self.assertNotIn("not_a_broken_product_json_api", row)
            self.assertIs(row["functional_readiness_proven"], False)

    def test_custom_domain_timeout_stays_observer_specific(self):
        timeout = self.analyze()["surface_observations"][-1]
        self.assertEqual(timeout["label"], "UNAVAILABLE")
        self.assertEqual(timeout["evidence_scope"], "THIS_OBSERVER_NETWORK_ONLY")

    def test_no_overwrite_preserves_existing_bytes(self):
        receipt = fixture()
        stamp = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        receipt["observation_window_utc"] = {
            "start": (stamp - dt.timedelta(seconds=1)).isoformat(),
            "end": (stamp + dt.timedelta(seconds=1)).isoformat(),
        }
        for row in receipt["responses"]:
            row["observed_at_utc"] = stamp.isoformat()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "receipt.json"
            output = Path(directory) / "out.json"
            source.write_bytes(encode(receipt))
            output.write_bytes(b"preserve these exact bytes")
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                code = observer.main([str(source), "--expected-github-sha", GITHUB_SHA,
                                      "--output", str(output)])
            self.assertEqual(code, 2)
            self.assertIn("OUTPUT_EXISTS_REFUSED", errors.getvalue())
            self.assertEqual(output.read_bytes(), b"preserve these exact bytes")

    def test_malformed_utf8_nan_and_excessive_receipt_are_rejected(self):
        for raw, code in ((b"\xff", "MALFORMED_JSON"),
                          (b'{"nested":{"value":NaN}}', "NON_FINITE_JSON_NUMBER"),
                          (b'{"nested":{"value":1e999}}', "NON_FINITE_JSON_NUMBER"),
                          (b'{"nested":{"value":-1e999}}', "NON_FINITE_JSON_NUMBER"),
                          (b"x" * (observer.MAX_RECEIPT_BYTES + 1), "RECEIPT_BYTES_INVALID_OR_EXCESSIVE")):
            with self.subTest(code=code):
                with self.assertRaises(observer.VerificationError) as caught:
                    observer.analyze_receipt(raw, GITHUB_SHA, now=NOW)
                self.assertEqual(caught.exception.code, code)


if __name__ == "__main__":
    unittest.main()
