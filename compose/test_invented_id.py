#!/usr/bin/env python3
from __future__ import annotations

import unittest

from compose.invented_id import decide


class InventedIdTests(unittest.TestCase):
    def test_invented_receipt_abstains(self) -> None:
        out = decide("Look up receipt-7f3a for the hidden customer identifier")
        self.assertTrue(out["invented_identifier"])
        self.assertEqual(out["action"], "ABSTAIN")
        self.assertIsNone(out["operating_point"])

    def test_grounded_prompt_asks_controller(self) -> None:
        out = decide("Navigate to the signed organ map for this request.")
        self.assertFalse(out["invented_identifier"])
        self.assertEqual(out["action"], "ASK_CONTROLLER")


if __name__ == "__main__":
    unittest.main()
