import unittest

from compose.lanes import pulse


class LanePulseTests(unittest.TestCase):
    def test_no_lane_names_a_winner(self) -> None:
        report = pulse()
        self.assertFalse(report["ready"])
        self.assertIsNone(report["winner"])
        self.assertIsNone(report["l1"]["winner"])
        self.assertIsNone(report["l2"]["winner"])
        self.assertIsNone(report["l2"]["operating_point"])
        self.assertEqual(report["l3"]["collection"], "research-only")
        self.assertTrue(report["l3"]["held_out_gate"]["path_redacted"])
        self.assertIs(report["l3"]["held_out_gate"]["publication_eligible"], False)
        self.assertGreaterEqual(len(report["l2"]["coverage_risk_curve"]), 3)


if __name__ == "__main__":
    unittest.main()
