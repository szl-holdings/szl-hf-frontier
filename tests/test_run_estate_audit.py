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
                code = runner.main(["--skip-capture", "--snapshots", str(root / "snapshots"), "--receipt", str(root / "audit.json")])
            self.assertEqual(code, 1)
            receipt = json.loads((root / "audit.json").read_text())
            self.assertEqual(receipt["stages"]["snapshot_integrity"], "VERIFIED_UNSIGNED")
            self.assertEqual(receipt["stages"]["build"], "FAILED")
            self.assertNotIn("private-name", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
