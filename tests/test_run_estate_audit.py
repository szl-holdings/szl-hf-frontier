from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.test_capture_estate_snapshots import successful_capture
from tools import run_estate_audit as runner


class AuditRunnerTests(unittest.TestCase):
    def test_default_refresh_exports_public_projection_before_build(self):
        from tests.test_capture_estate_snapshots import fake_api
        from tools import capture_estate_snapshots as collector
        import os
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with (mock.patch.object(runner, "ROOT", root),
                  mock.patch.dict(os.environ, {"GH_TOKEN": "fixture", "HF_TOKEN": "fixture"}, clear=True),
                  mock.patch.object(collector, "request_json", side_effect=fake_api),
                  mock.patch.object(collector, "source_identity", return_value={"git_sha": "c" * 40}),
                  mock.patch.object(runner, "run", return_value=subprocess.CompletedProcess([], 1, "", "fixture build stop")),
                  contextlib.redirect_stdout(io.StringIO())):
                self.assertEqual(runner.main([]), 1)
            public = collector.verify_snapshot_set(root / "data/snapshots")
            raw = collector.verify_snapshot_set(root / ".estate-private/snapshots")
            self.assertEqual(public["scope"], "PUBLIC_PROJECTION_OF_AUTHENTICATED_CENSUS")
            self.assertEqual(raw["scope"], "TOKEN_VISIBLE")
            content = "".join(p.read_text() for p in (root / "data/snapshots").glob("*.json"))
            self.assertNotIn("private-fixture", content)
            self.assertNotIn("repo-2", content)

    def test_help_does_not_capture_or_run_subprocess(self):
        with (mock.patch.object(runner, "capture", side_effect=AssertionError("network")),
              mock.patch.object(runner, "run", side_effect=AssertionError("process")),
              contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as caught):
            runner.main(["--help"])
        self.assertEqual(caught.exception.code, 0)

    def test_skip_capture_runs_real_compiler_and_retains_blocked_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with successful_capture(root / "snapshots"):
                pass
            receipt_path = root / "audit.json"
            with mock.patch.object(runner, "capture", side_effect=AssertionError("network")), contextlib.redirect_stdout(io.StringIO()):
                code = runner.main(["--skip-capture", "--snapshots", str(root / "snapshots"), "--registry", str(root / "registry.json"), "--gaps", str(root / "gaps.json"), "--receipt", str(receipt_path)])
            receipt = json.loads(receipt_path.read_text())
            self.assertEqual(code, 2)
            self.assertTrue(receipt["complete"])
            self.assertEqual(receipt["status"], "BLOCKED_GAPS")
            self.assertEqual(receipt["stages"]["build"], "COMPLETE")
            self.assertGreater(receipt["unresolved_gap_count"], 0)
            self.assertFalse(receipt["publication_authorized"])
            self.assertTrue(receipt_path.with_suffix(".validation.log").is_file())

    def test_raw_authenticated_input_cannot_write_default_public_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / ".estate-private/snapshots"
            with successful_capture(raw):
                pass
            with (mock.patch.object(runner, "ROOT", root),
                  mock.patch.object(runner, "capture", side_effect=AssertionError("network")),
                  mock.patch.object(runner, "run") as run,
                  contextlib.redirect_stdout(io.StringIO()) as stdout):
                code = runner.main(["--skip-capture", "--snapshots", str(raw)])
            self.assertEqual(code, 1)
            run.assert_not_called()
            self.assertFalse((root / "data/estate_registry.json").exists())
            self.assertFalse((root / "reports/unresolved_gaps.json").exists())
            self.assertFalse((root / "reports/estate_audit_receipt.validation.log").exists())
            self.assertFalse((root / "reports/estate_audit_receipt.build.log").exists())
            receipt = json.loads((root / "reports/estate_audit_receipt.json").read_text())
            self.assertEqual(receipt["status"], "FAILED")
            self.assertFalse(receipt["complete"])
            self.assertNotIn("private-fixture", stdout.getvalue())
            self.assertNotIn("repo-2", stdout.getvalue())

    def test_missing_receipt_prevents_build_and_retains_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with mock.patch.object(runner, "run") as run, contextlib.redirect_stdout(io.StringIO()):
                code = runner.main(["--skip-capture", "--snapshots", str(root / "absent"), "--receipt", str(root / "audit.json")])
            run.assert_not_called()
            self.assertEqual(code, 1)
            receipt = json.loads((root / "audit.json").read_text())
            self.assertFalse(receipt["complete"])
            self.assertEqual(receipt["failure"], "SNAPSHOT_RECEIPT_INVALID")

    def test_build_failure_preserves_capture_evidence_without_success_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with successful_capture(root / "snapshots"):
                pass
            with (mock.patch.object(runner, "run", return_value=subprocess.CompletedProcess([], 1, "", "private-name")),
                  contextlib.redirect_stdout(io.StringIO()) as stdout):
                code = runner.main(["--skip-capture", "--snapshots", str(root / "snapshots"), "--registry", str(root / "registry.json"), "--gaps", str(root / "gaps.json"), "--receipt", str(root / "audit.json")])
            self.assertEqual(code, 1)
            receipt = json.loads((root / "audit.json").read_text())
            self.assertEqual(receipt["stages"]["snapshot_integrity"], "VERIFIED_UNSIGNED")
            self.assertEqual(receipt["stages"]["build"], "FAILED")
            self.assertNotIn("private-name", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
