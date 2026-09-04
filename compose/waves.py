#!/usr/bin/env python3
"""All-wave closer.

Investor read:
    Waves 0 and 1 are done. Waves 2-4 and 6 have finished their
    source work. They stay IN MOTION because metal, Hub writes, and
    a promoted winner do not exist. Wave 5 stays LATER.

    This script will not print READY. Winner stays null.

Developer run:
    python3 -m compose.waves
"""
from __future__ import annotations

import json
from pathlib import Path

from compose.lanes import pulse as lane_pulse

ROOT = Path(__file__).resolve().parents[1]


def _lanes() -> dict:
    return lane_pulse()


def close() -> dict:
    lanes = _lanes()
    waves = [
        {
            "id": 0,
            "name": "Truth and inventory",
            "source": "COMPLETE",
            "metal": "NOT_REQUIRED",
            "status": "DONE",
            "note": "Auditor, ledgers, owner-home classification.",
        },
        {
            "id": 1,
            "name": "Benchmark and data",
            "source": "COMPLETE",
            "metal": "NOT_REQUIRED",
            "status": "DONE",
            "note": "GMB schema, 20-case gold, exact/span/token leakage CLEAN.",
        },
        {
            "id": 2,
            "name": "ReceiptAgent tournament",
            "source": "COMPLETE",
            "metal": "BLOCKED_NO_METAL",
            "status": "IN MOTION",
            "note": "Rule baseline 20/20. No sample logs. Winner null.",
            "l1": lanes["l1"],
        },
        {
            "id": 3,
            "name": "Khipu abstention",
            "source": "COMPLETE",
            "metal": "BLOCKED_NO_METAL",
            "status": "IN MOTION",
            "note": "Controller coverage-risk curve recorded. Operating point null.",
            "l2": {"operating_point": lanes["l2"]["operating_point"], "promotion": lanes["l2"]["promotion"]},
        },
        {
            "id": 4,
            "name": "Kernel correctness",
            "source": "COMPLETE",
            "metal": "BLOCKED_NO_METAL",
            "status": "IN MOTION",
            "note": "Witness schema HOLD. Honesty matrix denies acceleration. Hub CI stays failed until republish.",
        },
        {
            "id": 5,
            "name": "GPU and serving",
            "source": "HOLD",
            "metal": "BLOCKED_NO_METAL",
            "status": "LATER",
            "note": "Triton/CuTe after reference correctness. No unnamed hardware.",
        },
        {
            "id": 6,
            "name": "Independent verification",
            "source": "COMPLETE",
            "metal": "BLOCKED_NO_TOKEN",
            "status": "IN MOTION",
            "note": "Collection rebuild dry-run. Flagship empty. No Hub PUT.",
        },
    ]
    if lanes.get("winner") is not None or lanes.get("ready"):
        raise SystemExit("REFUSED: lane pulse invented a winner or ready")
    return {
        "schema": "szl.wave-closer/v1",
        "estate": "NOT READY",
        "ready": False,
        "winner": None,
        "flagship": False,
        "source_complete": [0, 1, 2, 3, 4, 6],
        "metal_blocked": [2, 3, 4, 5, 6],
        "later": [5],
        "waves": waves,
    }


def main() -> int:
    print(json.dumps(close(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
