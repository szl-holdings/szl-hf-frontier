#!/usr/bin/env python3
"""L1 ledger. Winner stays null unless sample logs exist on disk."""
from __future__ import annotations

import json
from pathlib import Path

from compose.gate import compose_allow

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data" / "l1_candidates.json"


def load() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def select_winner(ledger: dict | None = None, *, sample_logs: Path | None = None) -> dict:
    ledger = ledger or load()
    lambda_gate = compose_allow("lambda_aggregate")
    if lambda_gate["status"] != "BLOCKED":
        raise SystemExit("lambda_aggregate must stay BLOCKED")
    if sample_logs is None or not sample_logs.is_file():
        return {
            "winner": None,
            "reason": "NO_SAMPLE_LOGS",
            "lambda": lambda_gate,
            "candidates": ledger["candidates"],
        }
    raise SystemExit("sample logs present but no selector is implemented — do not invent a winner")


def main() -> int:
    report = select_winner()
    print(json.dumps({"winner": report["winner"], "reason": report["reason"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
