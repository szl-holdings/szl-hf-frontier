"""Adversarial source-decision admission tests; no network or release writes."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.reconcile_estate import reconcile


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sha = "a" * 40
        self.key = "github/szl-holdings/frozen"
        self.entry = {"id": self.key, "revision": self.sha, "surface": "github", "status": "ARCHIVED", "visibility": "public",
                      "canonical": {"role": "record", "url": "https://github.com/szl-holdings/frozen"},
                      "classification": "unresolved", "license": "UNKNOWN"}
        self.put("data/estate_registry.json", [self.entry, {"id": "github/szl-holdings/live", "revision": "b" * 40,
                 "surface": "github", "status": "REFERENCE", "visibility": "public", "canonical": {"role": "source", "url": "https://github.com/szl-holdings/live"}}])
        self.put("reports/unresolved_gaps.json", {"unresolved_gaps": [{"id": self.key, "gate": gate, "severity": "high"} for gate in ["canonical-route", "source-classification", "license", "alignment-review"]]})
        self.put("data/snapshots/snapshot_receipt.json", {"complete": True, "files": {}})
        card = self.root / "data/source-evidence/card.txt"
        card.parent.mkdir(parents=True)
        card.write_text("Frozen provenance record. License: MIT. No replacement product.")
        self.ref = {"kind": "source_card", "source_identity": self.key, "revision": self.sha,
                    "path": "data/source-evidence/card.txt", "sha256": self.digest(card),
                    "source_path": "README.md", "url": f"https://github.com/szl-holdings/frozen/blob/{self.sha}/README.md"}
        self.decision = {"id": self.key, "observed_revision": self.sha, "classification": "archived_provenance",
                         "canonical": self.entry["canonical"],
                         "lifecycle": {"status": "ARCHIVED", "disposition": "terminal_provenance", "reason": "Frozen immutable provenance record", "terminal_purpose": "Final frozen research record, no successor product"},
                         "findings": [self.finding("canonical-route"), self.finding("source-classification")]}
        self.ledger = {"schema": "szl.source-reconciliation/v1", "generated_at": "2026-09-24T12:00:00Z",
                       "census_receipt_sha256": self.digest(self.root / "data/snapshots/snapshot_receipt.json"),
                       "decisions": [self.decision]}

    def digest(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def put(self, path, value):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value))

    def finding(self, gate):
        return {"gate": gate, "disposition": "resolved", "reason": "Reviewed exact source record",
                "supported_facts": ["The card declares final archival purpose"], "evidence_refs": [self.ref]}

    def run_review(self):
        self.put("data/reconciliation/source_decisions.json", self.ledger)
        return reconcile(self.root)

    def test_terminal_provenance_closes_only_demonstrated_source_findings(self):
        before = (self.root / "data/estate_registry.json").read_bytes()
        report, registry = self.run_review()
        self.assertEqual(report["resolved_gap_count"], 2)
        self.assertEqual(report["remaining_gap_count"], 2)
        self.assertFalse(report["publication_authorized"])
        self.assertFalse(report["semantic_review_independently_verified"])
        self.assertEqual(registry[0]["status"], "ARCHIVED")
        self.assertEqual(before, (self.root / "data/estate_registry.json").read_bytes())

    def test_tampered_evidence_rejected(self):
        (self.root / self.ref["path"]).write_text("replaced")
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            self.run_review()

    def test_stale_decision_rejected(self):
        self.decision["observed_revision"] = "c" * 40
        with self.assertRaisesRegex(ValueError, "revision differs"):
            self.run_review()

    def test_different_census_rejected(self):
        self.ledger["census_receipt_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "census receipt"):
            self.run_review()

    def test_wrong_artifact_url_rejected(self):
        self.ref["url"] = self.ref["url"].replace("/frozen/", "/other/")
        with self.assertRaisesRegex(ValueError, "URL must bind"):
            self.run_review()

    def test_path_escape_rejected(self):
        self.ref["path"] = "../outside"
        with self.assertRaisesRegex(ValueError, "Unsafe evidence path"):
            self.run_review()

    def test_deprecated_artifact_cannot_use_terminal_archive_exemption(self):
        self.entry["status"] = "DEPRECATED"
        baseline = json.loads((self.root / "data/estate_registry.json").read_text())
        baseline[0]["status"] = "DEPRECATED"
        self.put("data/estate_registry.json", baseline)
        with self.assertRaisesRegex(ValueError, "Terminal provenance"):
            self.run_review()

    def test_archive_flag_alone_does_not_prove_terminal_purpose(self):
        self.decision["lifecycle"].pop("terminal_purpose")
        with self.assertRaisesRegex(ValueError, "Terminal provenance"):
            self.run_review()

    def test_alignment_cannot_be_closed_by_relationship_review(self):
        self.decision["findings"].append(self.finding("alignment-review"))
        with self.assertRaisesRegex(ValueError, "cannot close"):
            self.run_review()

    def test_duplicate_decisions_rejected(self):
        self.ledger["decisions"].append(self.decision)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.run_review()

    def test_canonical_ownership_cannot_be_transferred(self):
        self.decision["canonical"] = {"role": "record", "url": "https://github.com/szl-holdings/live"}
        with self.assertRaisesRegex(ValueError, "ownership"):
            self.run_review()

    def test_target_route_needs_its_own_evidence(self):
        self.decision["lifecycle"] = {"status": "ARCHIVED", "disposition": "superseded"}
        self.decision["implementation_route"] = {"repository": "https://github.com/szl-holdings/live", "revision": "b" * 40}
        with self.assertRaisesRegex(ValueError, "target-source evidence"):
            self.run_review()

    def test_valid_primary_does_not_admit_forged_secondary_implementation_route(self):
        source = self.root / "data/source-evidence/live.txt"
        source.write_text("Current implementation README.")
        target_ref = {"kind": "source_file", "source_identity": "github/szl-holdings/live",
                      "revision": "b" * 40, "path": "data/source-evidence/live.txt",
                      "sha256": self.digest(source), "source_path": "README.md",
                      "url": f"https://github.com/szl-holdings/live/blob/{'b' * 40}/README.md"}
        primary = {"repository": "https://github.com/szl-holdings/live", "revision": "b" * 40, "path": "README.md"}
        self.decision["lifecycle"] = {"status": "ARCHIVED", "disposition": "superseded"}
        self.decision["findings"][0]["evidence_refs"].append(target_ref)
        self.decision["implementation_route"] = primary
        self.decision["implementation_routes"] = [primary, {
            "repository": "https://github.com/attacker/nonexistent", "revision": "d" * 40,
            "path": "invented/private"}]
        with self.assertRaises(ValueError):
            self.run_review()

    def test_all_secondary_implementation_paths_require_retained_target_evidence(self):
        source = self.root / "data/source-evidence/live.txt"
        source.write_text("Current implementation README.")
        target_ref = {"kind": "source_file", "source_identity": "github/szl-holdings/live",
                      "revision": "b" * 40, "path": "data/source-evidence/live.txt",
                      "sha256": self.digest(source), "source_path": "README.md",
                      "url": f"https://github.com/szl-holdings/live/blob/{'b' * 40}/README.md"}
        primary = {"repository": "https://github.com/szl-holdings/live", "revision": "b" * 40, "path": "README.md"}
        self.decision["lifecycle"] = {"status": "ARCHIVED", "disposition": "superseded"}
        self.decision["findings"][0]["evidence_refs"].append(target_ref)
        self.decision["implementation_route"] = primary
        self.decision["implementation_routes"] = [primary, {**primary, "path": "nonexistent/implementation.py"}]
        with self.assertRaises(ValueError):
            self.run_review()

    def test_upstream_license_is_not_an_artifact_grant(self):
        self.decision["license"] = {"identifier": "MIT", "scope": "upstream"}
        self.decision["findings"].append(self.finding("license"))
        with self.assertRaisesRegex(ValueError, "not just an upstream"):
            self.run_review()

    def test_explicit_artifact_license_can_close_its_finding(self):
        self.decision["license"] = {"identifier": "MIT", "scope": "artifact"}
        self.decision["findings"].append(self.finding("license"))
        report, rows = self.run_review()
        self.assertEqual(rows[0]["license"], "MIT")
        self.assertEqual(report["resolved_by_gate"]["license"], 1)


if __name__ == "__main__":
    unittest.main()
