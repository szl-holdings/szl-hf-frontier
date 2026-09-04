#!/usr/bin/env python3
"""Classify owner-home path leaks. Does not rewrite historical proofs."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "data" / "owner_home_leaks.json"


def load() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8"))


def main() -> int:
    data = load()
    assert data["schema"] == "szl.owner-home-leaks/v1"
    assert data["winner"] is None
    live = [row for row in data["findings"] if row["class"] == "LIVE"]
    print(json.dumps({
        "schema": data["schema"],
        "scanned_repos": data["scanned_repos"],
        "live": len(live),
        "historical": sum(1 for row in data["findings"] if row["class"] == "HISTORICAL"),
        "fixture": sum(1 for row in data["findings"] if row["class"] == "FIXTURE"),
        "note": data["note"],
    }, indent=2))
    # LIVE findings on this ledger must already be closed by a PR.
    open_live = [row for row in live if row.get("state") != "CLOSED"]
    if open_live:
        print("OPEN LIVE", [row["path"] for row in open_live])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
