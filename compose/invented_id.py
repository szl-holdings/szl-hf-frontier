#!/usr/bin/env python3
"""L2 invented-identifier refuse. No coverage-risk curve claimed."""
from __future__ import annotations

import re

INVENTED = re.compile(
    r"\b(receipt-[0-9a-f]{4,}|hid-[0-9a-f]{6,}|customer-[0-9]{5,}|"
    r"made-up handle|invented identifier|no handle is supplied)\b",
    re.I,
)


def decide(prompt: str) -> dict:
    text = str(prompt or "")
    hit = bool(INVENTED.search(text))
    return {
        "action": "ABSTAIN" if hit else "ASK_CONTROLLER",
        "invented_identifier": hit,
        "operating_point": None,
        "note": "ASK_CONTROLLER is not ALLOW. No frozen Khipu point yet.",
    }
