from __future__ import annotations

import hashlib
import http.client
import json
import tempfile
import unittest
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from tools.probe_estate_runtime import (
    LIMIT, RejectRedirects, RuntimeReader, WitnessError, app_facts,
    bounded_application, public_spaces, space_host, witness, assess_runtime,
)

SHA = "a" * 40
NAME = "SZLHOLDINGS/example"
HOST = "szlholdings-example.hf.space"


class Response:
    def __init__(self, body, code=200, content_type="application/json"):
        self.body, self.code = body, code
        self.headers = {"Content-Type": content_type}
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def read(self, limit):
        return self.body[:limit]


class Opener:
    def __init__(self, responses):
        self.responses, self.requests = responses, []
    def open(self, request, timeout):
        self.requests.append((request, timeout))
        value = self.responses[request.full_url]
        if isinstance(value, Exception):
            raise value
        return value


def reader_with(metadata=None, root=None, health=None, ready=None):
    data = {"id": NAME, "private": False, "sha": SHA, "subdomain": "szlholdings-example", "runtime": {"stage": "RUNNING", "sha": SHA}}
    data.update(metadata or {})
    reader = RuntimeReader("secret-test-token")
    reader.opener = Opener({
        f"https://huggingface.co/api/spaces/{NAME}": Response(json.dumps(data).encode()),
        f"https://{HOST}/": root or Response(b"<html>Application</html>", content_type="text/html"),
        f"https://{HOST}/healthz": health or Response(b"missing", code=404, content_type="text/plain"),
        f"https://{HOST}/readyz": ready or Response(b"missing", code=404, content_type="text/plain"),
    })
    return reader


class RuntimeWitnessTests(unittest.TestCase):
    def test_html_200_is_unknown_not_operational(self):
        result = witness({"path": NAME, "sha": SHA}, reader_with())
        self.assertEqual("UNKNOWN", result["runtime"])
        self.assertFalse(result["functional_inference_verified"])
        self.assertEqual(200, result["probes"][0]["http_status"])
        self.assertEqual({}, result["probes"][0]["application"])

    def test_health_object_is_observed_without_inference_claim(self):
        reader = reader_with(health=Response(b'{"ok":true,"source_revision":"' + SHA.encode() + b'"}'))
        result = witness({"path": NAME, "sha": SHA}, reader)
        self.assertEqual("HEALTH_RESPONSE_OBSERVED", result["runtime"])
        self.assertFalse(result["functional_inference_verified"])
        self.assertEqual("declared_only", result["probes"][1]["declared_revisions"][0]["binding"])

    def test_ready_failure_overrides_healthy_status(self):
        reader = reader_with(health=Response(b'{"ok":true}'), ready=Response(b'{"ready":false}'))
        self.assertEqual("FAIL", witness({"path": NAME, "sha": SHA}, reader)["runtime"])

    def test_root_failure_is_retained_with_hash(self):
        reader = reader_with(root=Response(b"server error", code=503))
        result = witness({"path": NAME, "sha": SHA}, reader)
        self.assertEqual("FAIL", result["runtime"])
        self.assertEqual(503, result["probes"][0]["http_status"])
        self.assertEqual(hashlib.sha256(b"server error").hexdigest(), result["probes"][0]["body_sha256"])

    def test_deployed_revision_mismatch_is_not_hidden_by_http_health(self):
        reader = reader_with(metadata={"runtime": {"stage": "RUNNING", "sha": "b" * 40}}, health=Response(b'{"ok":true}'))
        result = witness({"path": NAME, "sha": SHA}, reader)
        self.assertEqual("FAIL", result["runtime"])
        self.assertIn("RUNTIME_REVISION_MISMATCH", result["errors"])

    def test_hub_drift_is_separate_from_runtime_sha(self):
        reader = reader_with(metadata={"sha": "b" * 40})
        result = witness({"path": NAME, "sha": SHA}, reader)
        self.assertFalse(result["hub_revision_matches_snapshot"])
        self.assertTrue(result["runtime_revision_matches_snapshot"])
        self.assertIn("HUB_REVISION_DRIFT", result["errors"])

    def test_missing_runtime_revision_does_not_inherit_head(self):
        result = witness({"path": NAME, "sha": SHA}, reader_with(metadata={"runtime": {"stage": "RUNNING"}}))
        self.assertIsNone(result["runtime_observed_revision"])
        self.assertIsNone(result["runtime_revision_matches_snapshot"])

    def test_private_identity_at_live_api_stops_public_probes(self):
        reader = reader_with(metadata={"private": True})
        result = witness({"path": NAME, "sha": SHA}, reader)
        self.assertEqual(["LIVE_PUBLIC_IDENTITY_NOT_CONFIRMED"], result["errors"])
        self.assertEqual([], result["probes"])
        self.assertEqual(1, len(reader.opener.requests))

    def test_wrong_space_metadata_stops_public_probes(self):
        reader = reader_with(metadata={"id": "SZLHOLDINGS/other"})
        result = witness({"path": NAME, "sha": SHA}, reader)
        self.assertEqual([], result["probes"])

    def test_only_metadata_receives_authentication(self):
        reader = reader_with()
        witness({"path": NAME, "sha": SHA}, reader)
        requests = reader.opener.requests
        self.assertEqual("Bearer secret-test-token", requests[0][0].get_header("Authorization"))
        self.assertTrue(all(request.get_header("Authorization") is None for request, _ in requests[1:]))
        self.assertTrue(all(timeout == 15 for _, timeout in requests))

    def test_request_target_prevents_ssrf_and_unapproved_paths(self):
        reader = RuntimeReader("secret")
        for host, path in (("127.0.0.1", "/"), ("evil.hf.space.attacker.invalid", "/"), ("other." + HOST, "/"), (HOST, "/admin"), (HOST + ":443", "/")):
            with self.subTest(host=host, path=path), self.assertRaises(WitnessError):
                reader.fetch("https://" + host + path, api=False, allowed_host=host)

    def test_redirects_never_forward_credentials_or_change_hosts(self):
        request = urllib.request.Request("https://huggingface.co/api/spaces/" + NAME, headers={"Authorization": "Bearer test-secret"})
        for target in ("https://huggingface.co/other", "https://" + HOST + "/", "https://attacker.invalid"):
            with self.subTest(target=target), self.assertRaisesRegex(WitnessError, "REDIRECT_REJECTED"):
                RejectRedirects().redirect_request(request, None, 302, "Found", {}, target)

    def test_application_output_cannot_copy_secrets_or_arbitrary_strings(self):
        raw = {"ok": True, "token": "secret", "message": "secret", "status": "secret",
               "source_revision": "not-a-sha-secret", "app": {"ready": True, "env": "secret"}}
        self.assertEqual({"ok": True, "app": {"ready": True}}, bounded_application(raw))

    def test_oversized_response_is_hashed_as_prefix_not_full_body(self):
        reader = reader_with(root=Response(b"x" * (LIMIT + 20)))
        result = witness({"path": NAME, "sha": SHA}, reader)
        probe = result["probes"][0]
        self.assertTrue(probe["truncated"])
        self.assertEqual(LIMIT, probe["bytes_observed"])
        self.assertEqual("first_131072_bytes", probe["body_hash_scope"])
        self.assertEqual({}, probe["application"])

    def test_malformed_http_response_becomes_safe_failure_code(self):
        reader = reader_with()
        reader.opener.responses[f"https://{HOST}/"] = http.client.IncompleteRead(b"secret-body", 10)
        result = witness({"path": NAME, "sha": SHA}, reader)
        self.assertEqual("FAIL", result["runtime"])
        self.assertEqual("NETWORK_ERROR_OR_TIMEOUT", result["probes"][0]["error"])
        self.assertNotIn("secret-body", json.dumps(result))


class HostAndReceiptTests(unittest.TestCase):
    def test_live_api_host_preferred_to_derived_slug(self):
        self.assertEqual(("provider-assigned.hf.space", "live_provider_metadata"), space_host(NAME, {"subdomain": "provider-assigned"}))
        self.assertEqual((HOST, "derived_from_public_space_identity"), space_host(NAME, {}))

    def test_conflicting_hosts_fail_closed(self):
        with self.assertRaisesRegex(WitnessError, "MISMATCH"):
            space_host(NAME, {"subdomain": "one", "host": "https://two.hf.space"})

    def test_static_sdk_accepts_exact_provider_static_host(self):
        metadata = {"sdk": "static", "subdomain": "szlholdings-example", "host": "https://szlholdings-example.static.hf.space"}
        self.assertEqual(("szlholdings-example.static.hf.space", "live_provider_metadata"), space_host(NAME, metadata))
        metadata["subdomain"] = "szlholdings-example.static.hf.space"
        self.assertEqual("szlholdings-example.static.hf.space", space_host(NAME, metadata)[0])

    def test_static_suffix_does_not_allow_arbitrary_nested_hosts(self):
        for host in ("https://foo.bar.static.hf.space", "https://szlholdings-example.other.hf.space"):
            with self.subTest(host=host), self.assertRaises(WitnessError):
                space_host(NAME, {"sdk": "static", "host": host})
        with self.assertRaisesRegex(WitnessError, "STATIC_SDK"):
            space_host(NAME, {"sdk": "docker", "host": "https://szlholdings-example.static.hf.space"})

    def test_static_root_200_stays_unknown_and_unauthenticated(self):
        host = "szlholdings-example.static.hf.space"
        reader = reader_with(metadata={"sdk": "static", "host": "https://" + host})
        for path in ("/", "/healthz", "/readyz"):
            reader.opener.responses[f"https://{host}{path}"] = reader.opener.responses[f"https://{HOST}{path}"]
        result = witness({"path": NAME, "sha": SHA}, reader)
        self.assertEqual("UNKNOWN", result["runtime"])
        self.assertEqual(host, result["host"])
        self.assertTrue(all(request.get_header("Authorization") is None for request, _ in reader.opener.requests[1:]))

    def test_custom_hosts_credentials_ports_and_multilabel_subdomains_rejected(self):
        for host in ("https://attacker.invalid", "https://user:secret@" + HOST, "https://" + HOST + ":443", "https://foo.bar.hf.space", "http://" + HOST):
            with self.subTest(host=host), self.assertRaises(WitnessError):
                space_host(NAME, {"host": host})

    def make_snapshot(self, root, rows, complete=True):
        body = json.dumps(rows).encode()
        (root / "huggingface_spaces.json").write_bytes(body)
        receipt = {"schema": "szl.estate-snapshot-receipt/v1", "complete": complete,
                   "completed_at": "2026-09-24T12:00:00Z", "files": {"huggingface_spaces.json": {"sha256": hashlib.sha256(body).hexdigest(), "count": len(rows)}}}
        (root / "snapshot_receipt.json").write_text(json.dumps(receipt))

    def test_receipted_inventory_is_public_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_snapshot(root, [{"path": NAME, "private": False, "sha": SHA}, {"path": "SZLHOLDINGS/secret", "private": True}, {"path": "SZLHOLDINGS/unknown"}])
            rows, receipt = public_spaces(root)
            self.assertEqual([NAME], [row["path"] for row in rows])
            self.assertEqual(64, len(receipt["sha256"]))
            self.assertEqual(3, receipt["rows_in_snapshot"])
            self.assertEqual(1, receipt["public_space_candidates"])
            self.assertEqual(1, receipt["private_rows_excluded"])
            self.assertEqual(1, receipt["unknown_visibility_rows_excluded"])
            self.assertEqual("HOLD_STALE_OR_UNOBSERVED_VISIBILITY", receipt["coverage_status"])
            self.assertFalse(receipt["complete_org_coverage_verified"])
            self.assertNotIn("SZLHOLDINGS/secret", json.dumps(receipt))
            self.assertNotIn("SZLHOLDINGS/unknown", json.dumps(receipt))

    def test_recent_complete_snapshot_is_still_only_a_public_subset(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_snapshot(root, [{"path": NAME, "private": False, "sha": SHA}])
            observed = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
            rows, evidence = public_spaces(root, observed_at=observed)
            self.assertEqual(1, len(rows))
            self.assertEqual(2, evidence["snapshot_age_days"])
            self.assertFalse(evidence["snapshot_stale"])
            self.assertEqual("OBSERVED_PUBLIC_SUBSET_ONLY", evidence["coverage_status"])
            self.assertFalse(evidence["training_or_serving_verified"])

    def test_old_receipt_is_labelled_historical_and_cannot_claim_current_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_snapshot(root, [{"path": NAME, "private": False, "sha": SHA}])
            observed = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
            rows, evidence = public_spaces(root, observed_at=observed)
            self.assertEqual(1, len(rows))
            self.assertEqual(57, evidence["snapshot_age_days"])
            self.assertTrue(evidence["snapshot_stale"])
            self.assertEqual("HOLD_STALE_OR_UNOBSERVED_VISIBILITY", evidence["coverage_status"])
            self.assertFalse(evidence["complete_org_coverage_verified"])

    def test_future_snapshot_or_invalid_freshness_policy_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_snapshot(root, [{"path": NAME, "private": False, "sha": SHA}])
            before = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
            with self.assertRaisesRegex(WitnessError, "TIMESTAMP_IN_FUTURE"):
                public_spaces(root, observed_at=before)
            with self.assertRaisesRegex(WitnessError, "FRESHNESS_POLICY"):
                public_spaces(root, observed_at=before, max_age_days=0)

    def test_non_object_snapshot_row_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_snapshot(root, [{"path": NAME, "private": False, "sha": SHA}, None])
            with self.assertRaisesRegex(WitnessError, "INVALID_SPACE_SNAPSHOT_ROW"):
                public_spaces(root)

    def test_incomplete_inventory_receipt_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_snapshot(root, [], complete=False)
            with self.assertRaisesRegex(WitnessError, "INCOMPLETE"):
                public_spaces(root)

    def test_tampered_inventory_bytes_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_snapshot(root, [])
            (root / "huggingface_spaces.json").write_text("[ ]")
            with self.assertRaisesRegex(WitnessError, "HASH_MISMATCH"):
                public_spaces(root)


class RetainedAssessmentTests(unittest.TestCase):
    def test_refused_redirect_is_unknown_and_revision_drift_still_fails(self):
        result = {"provider_stage": "RUNNING", "hub_revision_matches_snapshot": True,
                  "runtime_revision_matches_snapshot": None,
                  "probes": [{"path": "/", "http_status": None, "error": "REDIRECT_REJECTED", "application": {}},
                             {"path": "/healthz", "http_status": 404, "application": {}}]}
        self.assertEqual(assess_runtime(result), "UNKNOWN")
        result["hub_revision_matches_snapshot"] = False
        self.assertEqual(assess_runtime(result), "FAIL")


if __name__ == "__main__":
    unittest.main()
