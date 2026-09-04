#!/usr/bin/env python3
"""L1 / L2 / L3 lane pulse.

Investor read:
    L1 ReceiptAgent  — rule baseline is 20/20. No weight winner.
    L2 Khipu         — controller curve exists. Operating point is not frozen.
    L3 Chaski        — named-N integers exist. Collection stays research-only.

Developer run:
    python3 -m compose.lanes
"""
from __future__ import annotations

import json
from pathlib import Path

from compose.tournament import select_winner

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str) -> dict:
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


def l1() -> dict:
    report = select_winner()
    ledger = _load("l1_candidates.json")
    if report["winner"] is not None or ledger.get("winner") is not None:
        raise SystemExit("REFUSED: L1 invented a winner")
    return {
        "lane": "L1",
        "winner": None,
        "reason": report["reason"],
        "rule_baseline": ledger.get("rule_baseline"),
        "metal": "BLOCKED_NO_METAL",
    }


def l2() -> dict:
    ledger = _load("l2_khipu.json")
    if ledger.get("operating_point") is not None or ledger.get("winner") is not None:
        raise SystemExit("REFUSED: L2 invented an operating point or winner")
    curve = ledger.get("coverage_risk_curve") or []
    if not curve:
        raise SystemExit("REFUSED: L2 missing coverage-risk curve")
    return {
        "lane": "L2",
        "winner": None,
        "operating_point": None,
        "promotion": ledger.get("promotion"),
        "controller_only": ledger.get("controller_only"),
        "coverage_risk_curve": curve,
        "metal": "BLOCKED_NO_METAL",
    }


def l3() -> dict:
    ledger = _load("l3_chaski.json")
    if ledger.get("winner") is not None:
        raise SystemExit("REFUSED: L3 invented a winner")
    if ledger.get("collection") != "research-only":
        raise SystemExit("REFUSED: L3 collection is not research-only")
    gate = ledger.get("held_out_gate") or {}
    if gate.get("publication_eligible") is True:
        raise SystemExit("REFUSED: L3 publication_eligible flipped true")
    if not gate:
        raise SystemExit("REFUSED: L3 held-out gate missing")
    selected = [row for row in ledger["candidates"] if row.get("selected")]
    if selected:
        raise SystemExit("REFUSED: L3 selected a candidate")
    return {
        "lane": "L3",
        "winner": None,
        "collection": "research-only",
        "held_out_gate": gate,
        "candidates": ledger["candidates"],
    }


def pulse() -> dict:
    return {
        "schema": "szl.lane-pulse/v1",
        "ready": False,
        "winner": None,
        "l1": l1(),
        "l2": l2(),
        "l3": l3(),
    }


def main() -> int:
    report = pulse()
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
