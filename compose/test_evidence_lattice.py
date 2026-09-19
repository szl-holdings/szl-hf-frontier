from __future__ import annotations

import copy
import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from compose.evidence_lattice import (
    EvidenceError,
    SNAPSHOT_SCHEMA,
    assess_snapshot,
    canonical_json,
    main,
    make_receipt,
    sha256_json,
    validate_snapshot,
    verify_receipt,
)

REVISION = "a" * 40
OTHER_REVISION = "b" * 40


def evidence(layer: str, revision: str = REVISION) -> dict:
    return {
        "state": "PASS",
        "subject_revision": revision,
        "evidence": [
            {
                "uri": f"https://evidence.invalid/{layer}/{revision}",
                "observation": "DIRECT_OBSERVATION",
                "subject_revision": revision,
                "observed_at": "2026-09-05T16:00:00Z",
                "observer": "test-observer",
            }
        ],
    }


def model_asset(*, disposition: str = "CANDIDATE") -> dict:
    return {
        "id": "SZLHOLDINGS/frontier-model",
        "kind": "model",
        "revision": REVISION,
        "disposition": disposition,
        "layers": {
            "metadata": evidence("metadata"),
            "source": evidence("source"),
            "artifact": evidence("artifact"),
            "evaluation": evidence("evaluation"),
            "provenance": evidence("provenance"),
            "controller": evidence("controller"),
        },
    }


def snapshot(*assets: dict) -> dict:
    return {
        "schema": SNAPSHOT_SCHEMA,
        "generated_at": "2026-09-05T16:00:00Z",
        "observer": "test-observer",
        "max_evidence_age_seconds": 3600,
        "assets": list(assets),
    }


class EvidenceLatticeTests(unittest.TestCase):
    def test_receipt_numeric_equality_does_not_replace_canonical_integrity(self) -> None:
        candidate = snapshot(model_asset())
        _, receipt = make_receipt(candidate, "promote")
        receipt["max_evidence_age_seconds"] = float(receipt["max_evidence_age_seconds"])
        with self.assertRaisesRegex(EvidenceError, "max_evidence_age_seconds"):
            verify_receipt(candidate, receipt)

    def test_current_check_expires_evidence_before_snapshot_expires(self) -> None:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        candidate = snapshot(model_asset())
        candidate["max_evidence_age_seconds"] = 3600
        candidate["generated_at"] = (now - timedelta(minutes=30)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        for layer in candidate["assets"][0]["layers"].values():
            for row in layer["evidence"]:
                row["observed_at"] = (now - timedelta(minutes=80)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
        self.assertTrue(assess_snapshot(candidate, "promote")["all_evidence_complete"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            path.write_text(json.dumps(candidate), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = main([str(path), "--require-complete"])
            result = json.loads(stdout.getvalue())
        self.assertEqual(code, 2)
        self.assertTrue(result["current_check"]["snapshot_fresh"])
        self.assertFalse(result["current_check"]["all_evidence_complete"])
        self.assertFalse(result["current_check"]["authorized"])

    def test_historical_verification_cannot_bypass_current_completeness_flag(self) -> None:
        candidate = snapshot(model_asset())
        _, receipt = make_receipt(candidate, "promote")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            receipt_path = Path(directory) / "receipt.json"
            path.write_text(json.dumps(candidate), encoding="utf-8")
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            for extra in (["--require-complete"], ["--receipt-out", "ignored.json"],
                          ["--previous-receipt-hash", "a" * 64]):
                with self.subTest(extra=extra), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main([str(path), "--verify-receipt",
                                           str(receipt_path), *extra]), 4)

    def test_canonical_json_ignores_mapping_order(self) -> None:
        left = {"b": [2, 1], "a": {"z": True, "x": None}}
        right = {"a": {"x": None, "z": True}, "b": [2, 1]}
        self.assertEqual(canonical_json(left), canonical_json(right))
        self.assertEqual(sha256_json(left), sha256_json(right))

    def test_evidence_reference_order_is_normalized(self) -> None:
        left = model_asset()
        left["layers"]["source"]["evidence"] = [
            {
                "uri": "https://evidence.invalid/z",
                "observation": "DIRECT_OBSERVATION",
                "subject_revision": REVISION,
                "observed_at": "2026-09-05T16:00:00Z",
                "observer": "test-observer",
            },
            {
                "uri": "https://evidence.invalid/a",
                "observation": "DIRECT_OBSERVATION",
                "subject_revision": REVISION,
                "observed_at": "2026-09-05T16:00:00Z",
                "observer": "test-observer",
            },
        ]
        right = copy.deepcopy(left)
        right["layers"]["source"]["evidence"].reverse()
        self.assertEqual(
            sha256_json(validate_snapshot(snapshot(left))),
            sha256_json(validate_snapshot(snapshot(right))),
        )

    def test_public_metadata_cannot_infer_trained_or_evaluated(self) -> None:
        asset = model_asset()
        asset["layers"] = {"metadata": evidence("hub-listing")}
        result = assess_snapshot(snapshot(asset), "promote")
        self.assertFalse(result["all_evidence_complete"])
        decision = result["decisions"][0]
        missing = {
            blocker["layer"]
            for blocker in decision["blockers"]
            if blocker["code"] == "REQUIRED_LAYER_MISSING"
        }
        self.assertEqual(
            missing,
            {"source", "artifact", "evaluation", "provenance", "controller"},
        )

    def test_full_bound_model_is_promotion_eligible(self) -> None:
        result = assess_snapshot(snapshot(model_asset()), "promote")
        self.assertTrue(result["all_evidence_complete"])
        self.assertEqual(result["complete_count"], 1)
        self.assertEqual(result["decisions"][0]["decision"], "EVIDENCE_COMPLETE_UNTRUSTED")
        self.assertFalse(result["authorized"])
        self.assertFalse(result["decisions"][0]["authorized"])

    def test_freshness_is_bound_to_observation_time(self) -> None:
        snap = snapshot(model_asset())
        snap["generated_at"] = "2026-09-05T18:00:00Z"
        result = assess_snapshot(snap, "promote")
        self.assertFalse(result["all_evidence_complete"])
        self.assertIn(
            "NO_FRESH_REVISION_BOUND_QUALIFYING_EVIDENCE",
            {b["code"] for b in result["decisions"][0]["blockers"]},
        )

    def test_invalid_calendar_and_future_observation_fail_closed(self) -> None:
        snap = snapshot(model_asset())
        snap["generated_at"] = "2026-02-30T16:00:00Z"
        with self.assertRaisesRegex(EvidenceError, "calendar"):
            validate_snapshot(snap)
        snap = snapshot(model_asset())
        snap["generated_at"] = "2026-09-05T15:00:00Z"
        with self.assertRaisesRegex(EvidenceError, "after generated_at"):
            validate_snapshot(snap)

    def test_duplicate_json_keys_fail_without_echoing_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ambiguous.json"
            path.write_text('{"schema":1,"schema":2}', encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()) as output:
                code = main([str(path)])
            self.assertEqual(code, 4)
            self.assertIn("duplicate key", output.getvalue())

    def test_publish_evidence_does_not_infer_operational_runtime(self) -> None:
        result = assess_snapshot(snapshot(model_asset()), "operate")
        decision = result["decisions"][0]
        self.assertFalse(decision["evidence_complete"])
        missing = {
            blocker["layer"]
            for blocker in decision["blockers"]
            if blocker["code"] == "REQUIRED_LAYER_MISSING"
        }
        self.assertEqual(missing, {"deployment", "runtime"})

    def test_unbound_evaluation_cannot_qualify_another_revision(self) -> None:
        asset = model_asset()
        asset["layers"]["evaluation"] = evidence("evaluation", OTHER_REVISION)
        decision = assess_snapshot(snapshot(asset), "promote")["decisions"][0]
        self.assertFalse(decision["evidence_complete"])
        self.assertIn(
            {
                "code": "LAYER_NOT_BOUND_TO_ASSET_REVISION",
                "layer": "evaluation",
                "asset_revision": REVISION,
                "subject_revision": OTHER_REVISION,
            },
            decision["blockers"],
        )

    def test_quarantine_dominates_complete_evidence(self) -> None:
        decision = assess_snapshot(
            snapshot(model_asset(disposition="QUARANTINED")), "promote"
        )["decisions"][0]
        self.assertFalse(decision["evidence_complete"])
        self.assertIn(
            {
                "code": "DISPOSITION_BLOCKS_ADMISSION",
                "disposition": "QUARANTINED",
            },
            decision["blockers"],
        )

    def test_http_runtime_evidence_does_not_infer_space_deployment(self) -> None:
        asset = {
            "id": "SZLHOLDINGS/frontier-space",
            "kind": "space",
            "revision": REVISION,
            "disposition": "ACTIVE",
            "layers": {
                "metadata": evidence("hub-listing"),
                "runtime": evidence("http-200"),
            },
        }
        decision = assess_snapshot(snapshot(asset), "operate")["decisions"][0]
        self.assertFalse(decision["evidence_complete"])
        missing = {
            blocker["layer"]
            for blocker in decision["blockers"]
            if blocker["code"] == "REQUIRED_LAYER_MISSING"
        }
        self.assertEqual(missing, {"source", "deployment", "provenance", "controller"})

    def test_caller_declared_presence_is_not_runtime_observation(self) -> None:
        asset = {
            "id": "SZLHOLDINGS/frontier-space",
            "kind": "space",
            "revision": REVISION,
            "disposition": "ACTIVE",
            "layers": {
                "source": evidence("source"),
                "deployment": evidence("deployment"),
                "runtime": {
                    "state": "PASS",
                    "subject_revision": REVISION,
                    "evidence": [
                        {
                            "uri": "receipt:caller-supplied-present-set",
                            "observation": "CALLER_DECLARED",
                            "subject_revision": REVISION,
                            "observed_at": "2026-09-05T16:00:00Z",
                            "observer": "test-observer",
                        }
                    ],
                },
                "provenance": evidence("provenance"),
                "controller": evidence("controller"),
            },
        }
        decision = assess_snapshot(snapshot(asset), "operate")["decisions"][0]
        self.assertFalse(decision["evidence_complete"])
        blocker = next(
            item
            for item in decision["blockers"]
            if item["code"] == "NO_QUALIFYING_OBSERVATION"
        )
        self.assertEqual(blocker["layer"], "runtime")
        self.assertEqual(blocker["observed_modes"], ["CALLER_DECLARED"])

    def test_receipt_round_trip_and_tamper_detection(self) -> None:
        snap = snapshot(model_asset())
        assessment, receipt = make_receipt(snap, "promote")
        self.assertTrue(assessment["all_evidence_complete"])
        self.assertTrue(verify_receipt(snap, receipt)["valid"])

        tampered = copy.deepcopy(snap)
        tampered["assets"][0]["disposition"] = "QUARANTINED"
        verification = verify_receipt(tampered, receipt)
        self.assertFalse(verification["valid"])
        self.assertIn("snapshot_sha256", verification["mismatches"])
        self.assertIn("receipt_sha256", verification["mismatches"])

    def test_receipt_chain_hash_is_bound(self) -> None:
        previous = "c" * 64
        _, receipt = make_receipt(
            snapshot(model_asset()),
            "promote",
            previous_receipt_sha256=previous,
        )
        self.assertEqual(receipt["previous_receipt_sha256"], previous)
        self.assertTrue(
            verify_receipt(snapshot(model_asset()), receipt)["valid"]
        )

    def test_conflicting_receipt_chain_pointer_fails_closed(self) -> None:
        snap = snapshot(model_asset())
        snap["previous_receipt_sha256"] = "c" * 64
        with self.assertRaisesRegex(EvidenceError, "conflicts with snapshot chain"):
            make_receipt(
                snap,
                "promote",
                previous_receipt_sha256="d" * 64,
            )

    def test_malformed_receipt_fields_fail_without_type_error(self) -> None:
        snap = snapshot(model_asset())
        _, receipt = make_receipt(snap, "promote")
        malformed = copy.deepcopy(receipt)
        malformed["previous_receipt_sha256"] = 7
        with self.assertRaisesRegex(EvidenceError, "expected lowercase sha256"):
            verify_receipt(snap, malformed)

        malformed = copy.deepcopy(receipt)
        malformed["goal"] = ["promote"]
        with self.assertRaisesRegex(EvidenceError, "unsupported goal"):
            verify_receipt(snap, malformed)

    def test_subset_receipt_is_self_describing(self) -> None:
        other = copy.deepcopy(model_asset())
        other["id"] = "SZLHOLDINGS/other-model"
        snap = snapshot(model_asset(), other)
        _, receipt = make_receipt(
            snap, "promote", ["model:SZLHOLDINGS/frontier-model"]
        )
        self.assertEqual(
            receipt["selectors"], ["model:SZLHOLDINGS/frontier-model"]
        )
        self.assertTrue(verify_receipt(snap, receipt)["valid"])
        self.assertFalse(
            verify_receipt(
                snap,
                receipt,
                ["model:SZLHOLDINGS/other-model"],
            )["valid"]
        )

    def test_duplicate_asset_ids_fail_closed(self) -> None:
        with self.assertRaisesRegex(EvidenceError, "duplicate ids"):
            validate_snapshot(snapshot(model_asset(), model_asset()))

    def test_same_asset_id_in_different_kinds_is_unambiguous_by_typed_selector(self) -> None:
        space = copy.deepcopy(model_asset())
        space["kind"] = "space"
        space["layers"] = {
            "source": evidence("source"),
            "deployment": evidence("deployment"),
            "runtime": evidence("runtime"),
            "provenance": evidence("provenance"),
            "controller": evidence("controller"),
        }
        snap = snapshot(model_asset(), space)
        validated = validate_snapshot(snap)
        self.assertEqual(len(validated["assets"]), 2)
        with self.assertRaisesRegex(EvidenceError, "ambiguous asset id"):
            assess_snapshot(snap, "promote", ["SZLHOLDINGS/frontier-model"])
        result = assess_snapshot(
            snap, "promote", ["model:SZLHOLDINGS/frontier-model"]
        )
        self.assertEqual(result["asset_count"], 1)
        self.assertEqual(
            result["decisions"][0]["selector"],
            "model:SZLHOLDINGS/frontier-model",
        )

    def test_aliases_cannot_select_the_same_asset_twice(self) -> None:
        with self.assertRaisesRegex(EvidenceError, "same asset"):
            assess_snapshot(
                snapshot(model_asset()),
                "promote",
                [
                    "SZLHOLDINGS/frontier-model",
                    "model:SZLHOLDINGS/frontier-model",
                ],
            )

    def test_passing_layer_requires_evidence(self) -> None:
        asset = model_asset()
        asset["layers"]["evaluation"]["evidence"] = []
        with self.assertRaisesRegex(EvidenceError, "requires at least one"):
            validate_snapshot(snapshot(asset))

    def test_credential_like_material_is_rejected(self) -> None:
        asset = model_asset()
        asset["layers"]["source"]["evidence"][0][
            "uri"
        ] = "https://example.invalid/?token=hf_AAAAAAAAAAAAAAAAAAAAAAAA"
        with self.assertRaisesRegex(EvidenceError, "credential-like"):
            validate_snapshot(snapshot(asset))

    def test_encoded_credential_and_sensitive_query_are_rejected(self) -> None:
        asset = model_asset()
        asset["layers"]["source"]["evidence"][0]["uri"] = (
            "https://example.invalid/?value=hf%5FAAAAAAAAAAAAAAAAAAAAAAAA"
        )
        with self.assertRaisesRegex(EvidenceError, "credential-like"):
            validate_snapshot(snapshot(asset))

        asset = model_asset()
        asset["layers"]["source"]["evidence"][0]["uri"] = (
            "https://example.invalid/?access_token=opaque-value"
        )
        with self.assertRaisesRegex(EvidenceError, "credential-bearing"):
            validate_snapshot(snapshot(asset))

    def test_url_userinfo_is_rejected(self) -> None:
        asset = model_asset()
        asset["layers"]["source"]["evidence"][0]["uri"] = (
            "https://user:password@example.invalid/evidence"
        )
        with self.assertRaisesRegex(EvidenceError, "userinfo"):
            validate_snapshot(snapshot(asset))

    def test_credential_shaped_unknown_key_is_not_echoed(self) -> None:
        snap = snapshot(model_asset())
        secret_key = "hf_AAAAAAAAAAAAAAAAAAAAAAAA"
        snap[secret_key] = "not-a-secret-value"
        with self.assertRaises(EvidenceError) as raised:
            validate_snapshot(snap)
        self.assertNotIn(secret_key, str(raised.exception))

    def test_unbound_direct_observation_cannot_qualify_revision(self) -> None:
        asset = model_asset()
        del asset["layers"]["evaluation"]["evidence"][0]["subject_revision"]
        decision = assess_snapshot(snapshot(asset), "promote")["decisions"][0]
        self.assertIn(
            {
                "code": "NO_REVISION_BOUND_QUALIFYING_EVIDENCE",
                "layer": "evaluation",
                "asset_revision": REVISION,
                "evidence_revisions": [],
            },
            decision["blockers"],
        )

    def test_nonfinite_number_is_rejected(self) -> None:
        snap = snapshot(model_asset())
        snap["notes"] = {"bad": float("nan")}
        with self.assertRaisesRegex(EvidenceError, "non-finite"):
            validate_snapshot(snap)

    def test_unknown_selection_fails_closed(self) -> None:
        with self.assertRaisesRegex(EvidenceError, "unknown asset ids"):
            assess_snapshot(snapshot(model_asset()), "promote", ["SZLHOLDINGS/missing"])

    def test_empty_selection_is_not_all_admitted(self) -> None:
        result = assess_snapshot(snapshot(model_asset()), "promote", [])
        self.assertEqual(result["asset_count"], 0)
        self.assertFalse(result["all_evidence_complete"])

    def test_cli_writes_and_verifies_hash_only_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot_path = root / "snapshot.json"
            receipt_path = root / "receipt.json"
            current = snapshot(model_asset())
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            current["generated_at"] = now
            for asset in current["assets"]:
                for layer in asset["layers"].values():
                    for item in layer["evidence"]:
                        item["observed_at"] = now
            snapshot_path.write_text(
                json.dumps(current), encoding="utf-8"
            )
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = main(
                    [
                        str(snapshot_path),
                        "--goal",
                        "promote",
                        "--receipt-out",
                        str(receipt_path),
                        "--require-complete",
                    ]
                )
            self.assertEqual(exit_code, 0)
            self.assertTrue(receipt_path.is_file())
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = main(
                    [
                        str(snapshot_path),
                        "--verify-receipt",
                        str(receipt_path),
                    ]
                )
            self.assertEqual(exit_code, 0)

            with contextlib.redirect_stderr(io.StringIO()):
                overwrite_code = main(
                    [
                        str(snapshot_path),
                        "--goal",
                        "promote",
                        "--receipt-out",
                        str(receipt_path),
                    ]
                )
            self.assertEqual(overwrite_code, 4)


if __name__ == "__main__":
    unittest.main()
