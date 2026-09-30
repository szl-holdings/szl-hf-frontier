import copy
import json
import math
from pathlib import Path
import tempfile
import unittest

from selective_calibration import calibrate, evaluate, run_cli
from evidence_lab import MAX_BYTES, digest


def samples(n, score=.8, error=False, prefix="cal"):
    return [{"episode_id": f"{prefix}-{i}", "score": score, "capability_valid": True, "error": error} for i in range(n)]


class CalibrationTests(unittest.TestCase):
    def test_empty_never_certifies_zero_risk(self):
        result = calibrate([])
        self.assertEqual(result["decision"], "ABSTAIN_ALL")
        self.assertTrue(all(c["upper_bound"] is None for c in result["candidates"]))

    def test_small_zero_error_sample_insufficient(self):
        self.assertEqual(calibrate(samples(20))["decision"], "ABSTAIN_ALL")

    def test_qualifying_sample_and_deterministic_larger_threshold_tie_break(self):
        result = calibrate(samples(2000))
        self.assertEqual(result["selection"]["threshold"], .8)
        self.assertEqual(result["selection"]["accepted"], 2000)
        self.assertAlmostEqual(result["selection"]["upper_bound"], math.sqrt(math.log(21 / .05) / 4000))
        self.assertEqual(result, calibrate(samples(2000)))

    def test_high_confidence_invalid_capability_has_no_coverage(self):
        data = samples(2000, score=1)
        for e in data:
            e["capability_valid"] = False
        self.assertEqual(calibrate(data)["decision"], "ABSTAIN_ALL")

    def test_errors_cannot_be_relabeled_as_abstentions(self):
        self.assertEqual(calibrate(samples(2000, error=True))["decision"], "ABSTAIN_ALL")

    def test_fixed_grid_multiple_testing_correction(self):
        result = calibrate(samples(2000), grid=(0., .8))
        self.assertAlmostEqual(result["selection"]["upper_bound"], math.sqrt(math.log(2 / .05) / 4000))

    def test_invalid_inputs(self):
        for changes in ({"score": True}, {"score": float("nan")}, {"score": 1.01}, {"error": 0}, {"capability_valid": 1}, {"extra": True}):
            data = samples(1)
            data[0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                calibrate(data)
        with self.assertRaises(ValueError):
            calibrate(samples(1) * 2)
        with self.assertRaises(ValueError):
            calibrate([], grid=(.5, .5))

    def test_test_labels_do_not_recalibrate(self):
        data = samples(2000)
        calibration = calibrate(data)
        test = samples(100, error=True, prefix="test")
        result = evaluate(test, calibration, data)
        self.assertEqual(result["selective_error"], 1)
        self.assertEqual(calibration["selection"]["threshold"], .8)

    def test_overlap_or_self_asserted_certificate_rejected(self):
        data = samples(2000)
        calibration = calibrate(data)
        with self.assertRaisesRegex(ValueError, "overlap"):
            evaluate(data[:1], calibration, data)
        altered = copy.deepcopy(calibration)
        altered["selection"]["threshold"] = 0.
        with self.assertRaisesRegex(ValueError, "replay"):
            evaluate(samples(10, prefix="test"), altered, data)

    def test_abstain_all_test_has_null_conditional_error(self):
        data = samples(1)
        result = evaluate(samples(2, prefix="test"), calibrate(data), data)
        self.assertEqual(result["accepted"], 0)
        self.assertIsNone(result["selective_error"])


class CalibrationCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cal = self.root / "cal.json"
        self.test = self.root / "test.json"
        self.output = self.root / "result.json"

    def write_cal(self, data):
        self.cal.write_text(json.dumps(data), encoding="utf-8")

    def test_small_fixture_cli_is_local_insufficient_not_model_evidence(self):
        self.write_cal(samples(20))
        result = run_cli(self.cal, self.output)
        self.assertEqual(result["calibration"]["decision"], "ABSTAIN_ALL")
        self.assertIs(result["model_inference_performed"], False)
        self.assertIsNone(result["test"])
        payload = dict(result)
        expected = payload.pop("payload_sha256")
        self.assertEqual(digest(payload), expected)
        self.assertEqual(json.loads(self.output.read_text()), result)

    def test_cli_frozen_selection_test_error_remains_visible(self):
        self.write_cal(samples(2000))
        self.test.write_text(json.dumps(samples(5, prefix="heldout", error=True)), encoding="utf-8")
        result = run_cli(self.cal, self.output, test_path=self.test)
        self.assertEqual(result["calibration"]["selection"]["threshold"], .8)
        self.assertEqual(result["test"]["selective_error"], 1)

    def test_cli_overlap_rejects_before_output(self):
        self.write_cal(samples(20))
        self.test.write_text(json.dumps(samples(2)), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "overlap"):
            run_cli(self.cal, self.output, test_path=self.test)
        self.assertFalse(self.output.exists())

    def test_cli_does_not_overwrite_evidence(self):
        self.write_cal(samples(20))
        self.output.write_text("preserved", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            run_cli(self.cal, self.output)
        self.assertEqual(self.output.read_text(), "preserved")

    def test_cli_byte_utf8_duplicate_and_nonfinite_bounds(self):
        for raw in (b"x" * (MAX_BYTES + 1), b"\xff", b'[{"episode_id":"x","episode_id":"y","score":0,"error":false,"capability_valid":true}]', b'[{"episode_id":"x","score":NaN,"error":false,"capability_valid":true}]'):
            self.cal.write_bytes(raw)
            with self.subTest(raw=raw[:80]), self.assertRaises(ValueError):
                run_cli(self.cal, self.output)
            self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
