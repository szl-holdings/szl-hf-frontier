#!/usr/bin/env python3
"""Offline wave contract runner. No credential, Hub or GPU activation path."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

def wave_local() -> dict:
    from compose.gate import compose_allow
    from compose.invented_id import decide
    from compose.lanes import pulse
    from compose.waves import close as close_waves
    from compose.tournament import select_winner

    l1 = select_winner()
    l2 = decide("Look up receipt-7f3a for the hidden customer identifier")
    l2_ok = decide("Navigate to the signed organ map for this request.")
    lam = compose_allow("lambda_aggregate")
    l2_ledger = json.loads((ROOT / "data" / "l2_khipu.json").read_text(encoding="utf-8"))
    l3 = json.loads((ROOT / "data" / "l3_chaski.json").read_text(encoding="utf-8"))
    lanes = pulse()
    waves = close_waves()
    if l1["winner"] is not None:
        raise SystemExit("REFUSED: L1 invented a winner")
    if l2_ledger.get("operating_point") is not None:
        raise SystemExit("REFUSED: L2 invented an operating point")
    if l3.get("winner") is not None:
        raise SystemExit("REFUSED: L3 invented a winner")
    if lam["status"] != "BLOCKED":
        raise SystemExit("REFUSED: lambda_aggregate must stay BLOCKED")
    if l2["action"] != "ABSTAIN" or l2_ok["action"] != "ASK_CONTROLLER":
        raise SystemExit("REFUSED: invented-id gate broken")
    if lanes.get("ready") or lanes.get("winner") is not None:
        raise SystemExit("REFUSED: lane pulse claimed ready or a winner")
    if not (l3.get("held_out_gate") or {}).get("path_redacted"):
        raise SystemExit("REFUSED: L3 path_redacted missing")
    if waves.get("ready") or waves.get("winner") is not None or waves.get("estate") != "NOT READY":
        raise SystemExit("REFUSED: wave closer claimed ready")
    return {
        "l1_winner": l1["winner"],
        "l1_reason": l1["reason"],
        "l2_operating_point": l2_ledger["operating_point"],
        "l3_collection": l3["collection"],
        "l3_held_out_gate": True,
        "lambda": lam["status"],
        "estate": waves["estate"],
        "source_complete": waves["source_complete"],
        "later": waves["later"],
    }


def wave_tests() -> str:
    tests = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "compose.test_tournament",
            "compose.test_invented_id",
            "compose.test_lanes",
            "compose.test_waves",
            "compose.test_evidence_lattice",
            "compose.test_estate_to_lattice",
            "-q",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    check = subprocess.run(
        [sys.executable, "-c", "from compose.selfcheck import main; raise SystemExit(main())"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if tests.returncode != 0 or check.returncode != 0:
        sys.stderr.write(tests.stdout + tests.stderr + check.stdout + check.stderr)
        raise SystemExit("REFUSED: unit tests failed")
    return "PASS"


def wave_hub() -> str:
    # Credentials in a developer shell or CI environment never authorize a write.
    return "DISABLED_OFFLINE_NO_OWNER_AUTHORIZATION"


def wave_metal() -> str:
    return "NOT_PROBED_OFFLINE"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="explicit CI mode; offline is also the default")
    parser.parse_args()
    local = wave_local()
    tests = wave_tests()
    hub = wave_hub()
    metal = wave_metal()
    report = {
        "schema": "szl.wave-payload/v1",
        "local": local,
        "tests": tests,
        "hub": hub,
        "metal": metal,
        "winner": None,
        "flagship": False,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
