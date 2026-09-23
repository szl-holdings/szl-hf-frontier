from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.build_estate_registry import build_registry, gap_report


class EstateRegistryBuilderTests(unittest.TestCase):
    def test_builds_sorted_entries_and_preserves_archive_successor(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "github_repositories.json").write_text(json.dumps([
                {"full_name": "szl-holdings/active", "html_url": "https://github.com/szl-holdings/active", "private": False, "archived": False, "license": {"spdx_id": "Apache-2.0"}},
                {"full_name": "szl-holdings/old", "html_url": "https://github.com/szl-holdings/old", "private": False, "archived": True, "description": "ARCHIVED. Canonical: https://github.com/szl-holdings/active", "license": {"spdx_id": "Apache-2.0"}},
            ]), encoding="utf-8")
            (root / "huggingface_models.json").write_text(json.dumps([
                {"path": "SZLHOLDINGS/szl-invariants", "private": False},
            ]), encoding="utf-8")
            registry = build_registry(root)
            self.assertEqual(3, len(registry))
            archived = next(entry for entry in registry if entry["id"].endswith("/old"))
            self.assertEqual("ARCHIVED", archived["status"])
            self.assertEqual("https://github.com/szl-holdings/active", archived["links"]["successor"])
            kernel = next(entry for entry in registry if entry["surface"] == "huggingface-model")
            self.assertEqual("kernel", kernel["artifact_class"])

    def test_gap_report_flags_unknown_license(self) -> None:
        registry = [{"id": "github/x", "license": "UNKNOWN", "status": "SOURCE_BACKED", "surface": "github", "artifact_class": "repository", "links": {}}]
        report = gap_report(registry)
        self.assertEqual(1, len(report["unresolved_gaps"]))
        self.assertEqual("license", report["unresolved_gaps"][0]["gate"])


if __name__ == "__main__":
    unittest.main()
