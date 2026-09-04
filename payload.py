#!/usr/bin/env python3
"""One-file wave runner. Stdlib first. Optional huggingface_hub."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

TOKEN_KEYS = (
    "HF_TOKEN",
    "HF_ORG_TOKEN1",
    "HF_ORG_TOKEN",
    "HF_WRITE_TOKEN",
    "HUGGINGFACE_TOKEN",
    "HUGGING_FACE_HUB_TOKEN",
)


def _have_cuda() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _token() -> str:
    for key in TOKEN_KEYS:
        raw = str(os.environ.get(key) or "").strip()
        if raw:
            return raw
    return ""


def wave_local() -> dict:
    from compose.gate import compose_allow
    from compose.invented_id import decide
    from compose.tournament import select_winner

    l1 = select_winner()
    l2 = decide("Look up receipt-7f3a for the hidden customer identifier")
    l2_ok = decide("Navigate to the signed organ map for this request.")
    lam = compose_allow("lambda_aggregate")
    l2_ledger = json.loads((ROOT / "data" / "l2_khipu.json").read_text(encoding="utf-8"))
    l3 = json.loads((ROOT / "data" / "l3_chaski.json").read_text(encoding="utf-8"))
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
    return {
        "l1_winner": l1["winner"],
        "l1_reason": l1["reason"],
        "l2_operating_point": l2_ledger["operating_point"],
        "l3_collection": l3["collection"],
        "lambda": lam["status"],
    }


def wave_tests() -> str:
    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "compose.test_tournament", "compose.test_invented_id", "-q"],
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
    token = _token()
    if not token:
        return "UNAVAILABLE_NO_TOKEN"
    script = ROOT / "tools" / "cto_hub_honesty_payload.py"
    if not script.is_file():
        return "UNAVAILABLE_NO_SCRIPT"
    proc = subprocess.run([sys.executable, str(script)], cwd=ROOT)
    return "HUB_RAN" if proc.returncode == 0 else "HUB_FAILED"


def wave_metal() -> str:
    if not _have_cuda():
        return "BLOCKED_NO_METAL"
    return "METAL_PRESENT_NO_TRAIN_IN_THIS_PAYLOAD"


def main() -> int:
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
