import unittest

from compose.waves import close


class WaveCloserTests(unittest.TestCase):
    def test_estate_not_ready(self) -> None:
        report = close()
        self.assertEqual(report["estate"], "NOT READY")
        self.assertFalse(report["ready"])
        self.assertIsNone(report["winner"])
        self.assertFalse(report["flagship"])
        by_id = {row["id"]: row for row in report["waves"]}
        self.assertEqual(by_id[0]["status"], "DONE")
        self.assertEqual(by_id[1]["status"], "DONE")
        self.assertEqual(by_id[2]["status"], "IN MOTION")
        self.assertEqual(by_id[2]["source"], "COMPLETE")
        self.assertEqual(by_id[5]["status"], "LATER")
        self.assertEqual(by_id[3]["l2"]["operating_point"], None)


if __name__ == "__main__":
    unittest.main()
