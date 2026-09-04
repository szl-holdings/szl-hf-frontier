#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest
from pathlib import Path

from compose.tournament import LEDGER, select_winner


class TournamentTests(unittest.TestCase):
    def test_winner_is_null(self) -> None:
        report = select_winner()
        self.assertIsNone(report["winner"])
        self.assertEqual(report["reason"], "NO_SAMPLE_LOGS")

    def test_v3_is_not_selected(self) -> None:
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        v3 = next(c for c in ledger["candidates"] if c["id"].endswith("-v3"))
        self.assertFalse(v3["selected"])

    def test_logs_file_does_not_invent_a_winner(self) -> None:
        path = Path(__file__).with_name("_tmp_logs.json")
        path.write_text("{}", encoding="utf-8")
        try:
            with self.assertRaises(SystemExit):
                select_winner(sample_logs=path)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
