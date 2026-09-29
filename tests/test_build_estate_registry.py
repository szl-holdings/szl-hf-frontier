from __future__ import annotations
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from tools import build_estate_registry as builder
from tools.build_estate_registry import SNAPSHOTS, build_registry, gap_report, write_json

REV = "a" * 40
STAMP = "2026-09-24T12:00:00Z"
class EstateRegistryBuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.root = self.repo / "data" / "snapshots"
        self.rows = {name: [] for name in SNAPSHOTS}
        self.rows["github_repositories.json"] = [{"full_name": "szl-holdings/active", "html_url": "https://github.com/szl-holdings/active", "private": False, "archived": False, "source_revision": REV, "license": {"spdx_id": "Apache-2.0"}}]
        self.rows["huggingface_models.json"] = [{"path": "SZLHOLDINGS/szl-invariants", "private": False, "sha": REV, "license": "mit"}]
        self.save()

    def save(self):
        files = {}
        for name, rows in self.rows.items():
            path = self.root / name
            write_json(path, rows)
            files[name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "count": len(rows)}
        write_json(self.root / "snapshot_receipt.json", {"complete": True, "completed_at": STAMP, "files": files})

    def review(self, **updates):
        evidence = self.repo / "data" / "source-evidence" / "card.md"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text("Source: https://github.com/szl-holdings/active\n", encoding="utf-8")
        value = {"id": "huggingface-model/szlholdings/szl-invariants", "observed_revision": REV, "artifact_class": "kernel", "status": "SOFTWARE", "classification": "mirror_distribution", "links": {"github": "https://github.com/szl-holdings/active"}, "audit": {"status": "UNREVIEWED", "last_checked": STAMP, "notes": ["Source card inspected, no runtime qualification."]}, "evidence": [{"path": "data/source-evidence/card.md", "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(), "revision": REV}]}
        value["evidence"][0]["kind"] = "source_card"
        value["evidence"][0]["url"] = f"https://huggingface.co/SZLHOLDINGS/szl-invariants/resolve/{REV}/README.md"
        value["evidence"][0]["source_path"] = "README.md"
        value.update(updates)
        target = self.repo / "data" / "source_reviews.json"
        write_json(target, [value])
        return target

    def test_identical_receipted_inputs_produce_identical_registry_and_gaps(self):
        first, second = build_registry(self.root), build_registry(self.root)
        self.assertEqual(first, second)
        self.assertEqual(gap_report(first), gap_report(second))
        self.assertEqual([r["id"] for r in first], sorted(r["id"] for r in first))
        self.assertFalse(gap_report(first)["promotion_eligible"])

    def test_hub_listing_does_not_establish_source_training_or_runtime(self):
        model = build_registry(self.root)[1]
        self.assertEqual(model["status"], "EXPERIMENTAL")
        self.assertEqual(model["license"], "mit")
        self.assertEqual(model["revision"], REV)
        self.assertEqual(model["audit"]["status"], "UNREVIEWED")
        self.assertIn("canonical-route", [gap["gate"] for gap in gap_report([model])["unresolved_gaps"]])

    def test_missing_snapshot_and_tamper_fail_closed(self):
        target = self.root / "huggingface_spaces.json"
        target.unlink()
        with self.assertRaises(FileNotFoundError):
            build_registry(self.root)
        self.save()
        target.write_text('[{"injected": true}]', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            build_registry(self.root)

    def test_incomplete_receipt_does_not_compile_stale_files(self):
        receipt = self.root / "snapshot_receipt.json"
        value = json.loads(receipt.read_text())
        value["complete"] = False
        write_json(receipt, value)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            build_registry(self.root)

    def test_visibility_must_be_explicit(self):
        self.rows["huggingface_models.json"][0].pop("private")
        self.save()
        with self.assertRaisesRegex(ValueError, "visibility"):
            build_registry(self.root)

    def test_duplicate_identity_rejected(self):
        self.rows["huggingface_models.json"] *= 2
        self.save()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_registry(self.root)

    def test_archive_keeps_own_identity_and_explicit_successor(self):
        self.rows["github_repositories.json"].append({"full_name": "szl-holdings/old", "html_url": "https://github.com/szl-holdings/old", "private": False, "archived": True, "description": "ARCHIVED. Canonical: https://github.com/szl-holdings/active", "source_revision": REV})
        self.save()
        archived = next(row for row in build_registry(self.root) if row["id"].endswith("/old"))
        self.assertEqual(archived["canonical"], {"role": "record", "url": "https://github.com/szl-holdings/old"})
        self.assertEqual(archived["links"]["successor"], "https://github.com/szl-holdings/active")

    def test_source_review_requires_matching_revision_and_real_hash(self):
        review = self.review()
        model = build_registry(self.root, review)[1]
        self.assertEqual(model["classification"], "mirror_distribution")
        self.assertEqual(model["status"], "SOFTWARE")
        self.assertEqual(model["audit"]["status"], "UNREVIEWED")
        self.assertFalse(gap_report([model])["promotion_eligible"])
        (self.repo / "data/source-evidence/card.md").write_text("tampered", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "digest"):
            build_registry(self.root, review)
        review = self.review(observed_revision="b" * 40)
        with self.assertRaisesRegex(ValueError, "revision"):
            build_registry(self.root, review)

    def test_successor_outside_census_remains_a_high_route_gap(self):
        row = build_registry(self.root)[0]
        row["status"] = "ARCHIVED"
        row["links"]["successor"] = "https://github.com/szl-holdings/not-in-census"
        self.assertTrue(any(gap["gate"] == "canonical-route" for gap in gap_report([row])["unresolved_gaps"]))

    def test_review_cannot_promote_alignment_or_replace_identity(self):
        review = self.review(audit={"status": "ALIGNED_ACTIVE", "last_checked": STAMP})
        with self.assertRaisesRegex(ValueError, "alignment"):
            build_registry(self.root, review)
        review = self.review(canonical={"role": "mirror", "url": "https://github.com/szl-holdings/active"})
        with self.assertRaisesRegex(ValueError, "ownership"):
            build_registry(self.root, review)

    def test_automated_card_review_cannot_reactivate_deprecated_inventory(self):
        self.rows["github_repositories.json"][0]["description"] = "DEPRECATED: retained provenance"
        self.save()
        path = self.review()
        review = json.loads(path.read_text())[0]
        review.update(id="github/szl-holdings/active", status="SOURCE_BACKED", artifact_class="repository", classification="canonical_source", links={"github": "https://github.com/szl-holdings/active"})
        review["evidence"][0]["url"] = f"https://github.com/szl-holdings/active/blob/{REV}/README.md"
        write_json(path, [review])
        row = build_registry(self.root, path)[0]
        self.assertEqual(row["status"], "DEPRECATED")
        self.assertEqual(row["classification"], "successor_deprecated")
        self.assertEqual(row["audit"]["status"], "NEEDS_CANONICAL_MAPPING")

    def test_absent_source_evidence_remains_unresolved(self):
        model = build_registry(self.root, self.review(evidence=[]))[1]
        self.assertEqual(model["status"], "EXPERIMENTAL")
        self.assertEqual(model["classification"], "unresolved")
        self.assertEqual(model["audit"]["status"], "UNAVAILABLE_WITH_REASON")

    def test_review_rejects_foreign_or_mutable_source_card_url(self):
        path = self.review()
        reviews = json.loads(path.read_text())
        for url in (f"https://huggingface.co/SZLHOLDINGS/other/resolve/{REV}/README.md",
                    "https://huggingface.co/SZLHOLDINGS/szl-invariants/resolve/main/README.md"):
            reviews[0]["evidence"][0]["url"] = url
            write_json(path, reviews)
            with self.assertRaisesRegex(ValueError, "source card URL"):
                build_registry(self.root, path)

    def test_structure_pass_does_not_clear_release_gate(self):
        registry = self.repo / "registry.json"
        write_json(registry, build_registry(self.root))
        validator = Path(__file__).resolve().parents[1] / "validators/validate_estate_registry.py"
        draft = subprocess.run([sys.executable, str(validator), str(registry), "--structure-only"], capture_output=True, text=True)
        release = subprocess.run([sys.executable, str(validator), str(registry)], capture_output=True, text=True)
        self.assertEqual(draft.returncode, 0, draft.stderr)
        self.assertNotEqual(release.returncode, 0)
        self.assertIn("FAIL:", release.stderr)

    def invoke_cli(self, *args):
        original = Path.cwd()
        try:
            os.chdir(self.repo)
            with mock.patch.object(builder, "ROOT", self.repo):
                builder.main(["--input", str(self.root), *args])
        finally:
            os.chdir(original)

    def set_scope(self, scope):
        path = self.root / "snapshot_receipt.json"
        value = json.loads(path.read_text())
        value["scope"] = scope
        write_json(path, value)

    def make_private_input(self):
        self.rows["huggingface_models.json"][0]["private"] = True
        self.save()
        self.set_scope("TOKEN_VISIBLE")

    def test_direct_cli_blocks_private_input_before_default_output_writes(self):
        self.make_private_input()
        with self.assertRaisesRegex(ValueError, "PRIVATE_INPUT_REQUIRES_LOCAL_OUTPUTS"):
            self.invoke_cli()
        self.assertFalse((self.repo / "data/estate_registry.json").exists())
        self.assertFalse((self.repo / "reports/unresolved_gaps.json").exists())

    def test_direct_cli_checks_both_destinations_before_writing_either(self):
        self.make_private_input()
        for flag, name in (("--registry", "registry.json"), ("--gaps", "gaps.json")):
            with self.subTest(flag=flag):
                destination = self.repo / ".estate-private" / name
                with self.assertRaisesRegex(ValueError, "PRIVATE_INPUT_REQUIRES_LOCAL_OUTPUTS"):
                    self.invoke_cli(flag, str(destination))
                self.assertFalse(destination.exists())

    def test_direct_cli_preserves_explicit_local_private_build(self):
        self.make_private_input()
        registry = self.repo / ".estate-private/registry.json"
        gaps = self.repo / ".estate-private/gaps.json"
        self.invoke_cli("--registry", str(registry), "--gaps", str(gaps))
        self.assertEqual(sum(row["visibility"] == "private" for row in json.loads(registry.read_text())), 1)
        self.assertGreater(len(json.loads(gaps.read_text())["unresolved_gaps"]), 0)

    def test_direct_cli_allows_explicit_external_private_outputs(self):
        self.make_private_input()
        with tempfile.TemporaryDirectory() as folder:
            registry, gaps = Path(folder) / "registry.json", Path(folder) / "gaps.json"
            self.invoke_cli("--registry", str(registry), "--gaps", str(gaps))
            self.assertTrue(registry.is_file() and gaps.is_file())

    def test_token_visible_scope_requires_local_outputs_even_if_rows_are_public(self):
        self.set_scope("TOKEN_VISIBLE")
        with self.assertRaisesRegex(ValueError, "PRIVATE_INPUT_REQUIRES_LOCAL_OUTPUTS"):
            self.invoke_cli()

    def test_private_rows_cannot_bypass_guard_by_claiming_public_scope(self):
        self.make_private_input()
        self.set_scope("PUBLIC_PROJECTION_OF_AUTHENTICATED_CENSUS")
        with self.assertRaisesRegex(ValueError, "PRIVATE_INPUT_REQUIRES_LOCAL_OUTPUTS"):
            self.invoke_cli()

    def test_private_destination_cannot_escape_ignored_directory(self):
        self.make_private_input()
        with self.assertRaisesRegex(ValueError, "PRIVATE_INPUT_REQUIRES_LOCAL_OUTPUTS"):
            self.invoke_cli("--registry", ".estate-private/../data/registry.json",
                            "--gaps", ".estate-private/gaps.json")

    def test_direct_cli_can_compile_public_projection_to_default_outputs(self):
        self.set_scope("PUBLIC_PROJECTION_OF_AUTHENTICATED_CENSUS")
        self.invoke_cli()
        self.assertTrue((self.repo / "data/estate_registry.json").is_file())
        self.assertTrue((self.repo / "reports/unresolved_gaps.json").is_file())

if __name__ == "__main__":
    unittest.main()
