from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.capture_estate_snapshots import FILES, SCHEMA, write_json
from tools.classify_estate_sources import classify, observation_path, public_items
from tools.report_model_evidence import LABEL, build_report, filename_findings

REVISION = "a" * 40
STAMP = "2026-09-24T12:00:00Z"


class ModelEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.snapshots = self.root / "data/snapshots"
        self.evidence = self.root / "data/source-evidence"
        self.rows = {filename: [] for filename in FILES.values()}
        self.rows["github_repositories.json"] = [{"full_name": "szl-holdings/source", "private": False}]
        self.rows["huggingface_models.json"] = [{"path": "SZLHOLDINGS/model", "private": False, "sha": REVISION, "license": "apache-2.0"}]
        self.save_snapshots()
        self.item = next(item for item in public_items(self.snapshots) if item["kind"] == "models")
        self.files = sorted(["README.md", "model.safetensors", "model.gguf", "pytorch_model.bin", "optimizer.pt", "snapshot.pth", "export/model.onnx", "config.json", "adapter_config.json", "adapter_model.safetensors", "training/train_log.jsonl", "eval/results.json"])
        self.observation = {"id": self.item["id"], "observed_at": STAMP, "observed_revision": REVISION,
                            "card": "# Research model\nCanonical source: https://github.com/szl-holdings/source\n",
                            "files": self.files, "errors": [], "evidence": []}
        self.attach_inventory()
        self.attach_card()
        self.save_observation()

    def save_snapshots(self):
        files = {}
        for filename, rows in self.rows.items():
            path = self.snapshots / filename
            write_json(path, rows)
            files[filename] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "count": len(rows)}
        write_json(self.snapshots / "snapshot_receipt.json", {"schema": SCHEMA, "complete": True,
            "scope": "PUBLIC_PROJECTION_OF_AUTHENTICATED_CENSUS", "completed_at": STAMP,
            "files": files, "inventories": {kind: {"completion": "COMPLETE"} for kind in FILES}})

    def record(self, kind, body, url, source_path=""):
        digest = hashlib.sha256(body).hexdigest()
        relative = f"data/source-evidence/blobs/{digest}.{'md' if kind == 'source_card' else 'json'}"
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return {"kind": kind, "revision": REVISION, "sha256": digest, "path": relative,
                "url": url, "source_path": source_path, "bytes": len(body), "status": "observed"}

    def attach_inventory(self):
        body = (json.dumps({"revision": REVISION, "files": self.observation["files"]}, sort_keys=True) + "\n").encode()
        self.observation["evidence"].append(self.record("file_inventory", body, f"https://huggingface.co/api/models/SZLHOLDINGS/model/revision/{REVISION}"))

    def attach_card(self):
        self.observation["evidence"].append(self.record("source_card", self.observation["card"].encode(), f"https://huggingface.co/SZLHOLDINGS/model/resolve/{REVISION}/README.md", "README.md"))

    def save_observation(self):
        write_json(observation_path(self.evidence, self.item), self.observation)
        review = classify(self.item, self.observation, {"szl-holdings/source"})
        write_json(self.root / "data/source_reviews.json", [review])

    def test_weight_config_adapter_and_log_candidates_are_bounded_file_observations(self):
        report = build_report(self.root)
        model = report["models"][0]
        self.assertEqual(model["evidence_label"], LABEL)
        self.assertEqual(model["revision"], REVISION)
        self.assertEqual(model["findings"]["weight_candidates"]["count"], 7)
        self.assertEqual(model["findings"]["adapter_weight_candidates"]["candidate_files"], ["adapter_model.safetensors"])
        self.assertEqual(model["findings"]["training_log_or_receipt_candidates"]["candidate_files"], ["training/train_log.jsonl"])
        self.assertEqual(model["findings"]["evaluation_or_result_candidates"]["candidate_files"], ["eval/results.json"])
        for finding in model["findings"].values():
            self.assertEqual(finding["evidence_label"], LABEL)
        self.assertEqual(model["file_inventory_evidence"]["sha256"], self.observation["evidence"][0]["sha256"])
        self.assertEqual(model["canonical_source_mapping"], "https://github.com/szl-holdings/source")
        self.assertEqual(report["coverage"]["qualified_model_count"], 0)
        for field in ("weight_bytes_verified", "weight_integrity_verified", "training_verified", "evaluation_verified", "serving_verified", "promotion_eligible"):
            self.assertIs(model[field], False)
        self.assertEqual(model["qualification_status"], "UNKNOWN")

    def test_report_is_reproducible_offline_and_independent_of_working_directory(self):
        with mock.patch("socket.socket.connect", side_effect=AssertionError("network forbidden")):
            first = build_report(self.root)
            original = Path.cwd()
            try:
                os.chdir(self.root.parent)
                second = build_report(self.root)
            finally:
                os.chdir(original)
        self.assertEqual(first, second)
        self.assertEqual(first["generated_at"], STAMP)

    def test_card_production_claims_cannot_promote_verification(self):
        self.observation["card"] += "Fully operational. Production-ready. All training passed."
        self.observation["evidence"] = self.observation["evidence"][:1]
        self.attach_card()
        self.save_observation()
        model = build_report(self.root)["models"][0]
        self.assertFalse(model["training_verified"])
        self.assertFalse(model["serving_verified"])
        self.assertEqual(model["qualification_status"], "UNKNOWN")

    def test_software_classification_is_preserved_without_inventing_checkpoint_requirement(self):
        self.observation["card"] = "This is a Python kernel, not a trained model.\nCanonical source: https://github.com/szl-holdings/source"
        self.observation["files"] = ["README.md", "kernel.py"]
        self.observation["evidence"] = []
        self.attach_inventory()
        self.attach_card()
        self.save_observation()
        report = build_report(self.root)
        model = report["models"][0]
        self.assertEqual(model["source_classification"]["status"], "SOFTWARE")
        self.assertEqual(model["source_classification"]["artifact_class"], "kernel")
        self.assertIn("software_verification", [step["gate"] for step in model["required_next_evidence"]])
        self.assertNotIn("training_or_derivation_lineage", [step["gate"] for step in model["required_next_evidence"]])
        self.assertEqual(report["coverage"]["no_weight_candidates_in_observed_inventory_count"], 1)

    def test_unavailable_listing_is_not_counted_as_no_weights(self):
        self.observation.update(files=[], card="", evidence=[], errors=["HTTP_404"])
        self.save_observation()
        report = build_report(self.root)
        self.assertEqual(report["coverage"]["file_inventory_unavailable_count"], 1)
        self.assertEqual(report["coverage"]["no_weight_candidates_in_observed_inventory_count"], 0)
        self.assertIsNone(report["models"][0]["listed_file_count"])
        self.assertIsNone(report["models"][0]["file_inventory_evidence"])

    def test_private_or_unknown_snapshot_rows_are_rejected(self):
        for visibility in (True, None, "false"):
            with self.subTest(visibility=visibility):
                self.rows["huggingface_models.json"][0]["private"] = visibility
                self.save_snapshots()
                with self.assertRaisesRegex(ValueError, "non-public"):
                    build_report(self.root)

    def test_tampered_inventory_bytes_are_rejected(self):
        (self.root / self.observation["evidence"][0]["path"]).write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            build_report(self.root)

    def test_observation_cannot_add_files_absent_from_retained_inventory(self):
        self.observation["files"] = sorted(self.files + ["imaginary-weights.safetensors"])
        self.save_observation()
        with self.assertRaisesRegex(ValueError, "filenames differ"):
            build_report(self.root)

    def test_revision_and_artifact_url_mismatches_are_rejected(self):
        self.observation["observed_revision"] = "b" * 40
        self.save_observation()
        with self.assertRaisesRegex(ValueError, "revision differs"):
            build_report(self.root)
        self.observation["observed_revision"] = REVISION
        self.observation["evidence"][0]["url"] = f"https://huggingface.co/api/models/OTHER/foreign/revision/{REVISION}"
        self.save_observation()
        with self.assertRaisesRegex(ValueError, "URL does not bind"):
            build_report(self.root)

    def test_escaping_or_absolute_evidence_paths_are_rejected_before_read(self):
        for path in ("../outside.json", "data/source-evidence/../../outside.json", "C:/owner/file.json", "/tmp/file.json"):
            with self.subTest(path=path):
                self.observation["evidence"][0]["path"] = path
                self.save_observation()
                with self.assertRaisesRegex(ValueError, "evidence path"):
                    build_report(self.root)

    def test_fabricated_source_review_promotion_is_rejected(self):
        path = self.root / "data/source_reviews.json"
        reviews = json.loads(path.read_text())
        reviews[0]["status"] = "MEASURED"
        write_json(path, reviews)
        with self.assertRaisesRegex(ValueError, "review differs"):
            build_report(self.root)

    def test_duplicate_inventory_evidence_and_malformed_lists_are_rejected(self):
        self.observation["evidence"].append(self.observation["evidence"][0])
        self.save_observation()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_report(self.root)
        self.observation["evidence"] = []
        self.observation["files"] = ["README.md", "../unsafe.bin"]
        self.attach_inventory()
        self.save_observation()
        with self.assertRaisesRegex(ValueError, "repository file path"):
            build_report(self.root)

    def test_train_script_name_alone_is_not_a_training_log(self):
        findings = filename_findings(["train.py", "trainer_state.json", "training/receipt.json", "evaluator.py", "results.json"])
        self.assertEqual(findings["training_log_or_receipt_candidates"]["candidate_files"], ["trainer_state.json", "training/receipt.json"])
        self.assertEqual(findings["evaluation_or_result_candidates"]["candidate_files"], ["results.json"])


if __name__ == "__main__":
    unittest.main()
