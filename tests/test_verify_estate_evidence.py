from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.classify_estate_sources import json_bytes
from tools.verify_estate_evidence import ROOT, load_canonical_reviews

REVIEWS = [{"id": "github/szl-holdings/example", "audit": {"status": "UNREVIEWED", "notes": ["a", "b"]}}]


class CanonicalReviewBytesTests(unittest.TestCase):
    def write(self, raw: bytes) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "source_reviews.json"
        path.write_bytes(raw)
        return path

    def test_canonical_lf_reviews_are_accepted(self):
        self.assertEqual(REVIEWS, load_canonical_reviews(self.write(json_bytes(REVIEWS))))

    def test_crlf_reviews_with_identical_content_are_rejected(self):
        # Same JSON content, different bytes: the model evidence report binds the
        # file hash, so this must fail with its cause, not as a later hash mismatch.
        raw = json_bytes(REVIEWS).replace(b"\n", b"\r\n")
        self.assertEqual(REVIEWS, json.loads(raw))
        with self.assertRaisesRegex(ValueError, "LF line endings"):
            load_canonical_reviews(self.write(raw))

    def test_unsorted_or_reindented_reviews_are_rejected(self):
        for raw in (json.dumps(REVIEWS).encode("utf-8") + b"\n",
                    (json.dumps(REVIEWS, indent=4, sort_keys=True) + "\n").encode("utf-8")):
            with self.subTest(raw=raw[:20]):
                with self.assertRaisesRegex(ValueError, "canonical serialization"):
                    load_canonical_reviews(self.write(raw))

    def test_committed_reviews_are_canonical_and_bound_by_the_model_report(self):
        path = ROOT / "data/source_reviews.json"
        load_canonical_reviews(path)
        report = json.loads((ROOT / "reports/model_evidence_inventory.json").read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         report["input_bindings"]["source_reviews_sha256"])


if __name__ == "__main__":
    unittest.main()
