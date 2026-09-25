#!/usr/bin/env python3
"""Checks Markdown cards for minimum SZL public-surface contract markers."""
from __future__ import annotations
import sys
from pathlib import Path
REQUIRED_MARKERS = ("## What it does", "## What it does not do", "## Source of truth")
FORBIDDEN = ("proven trust", "safe autonomous action", "fully deployed control plane")
def main():
    paths = [Path(value) for value in sys.argv[1:]]
    if not paths: raise SystemExit("usage: validate_card_contract.py CARD.md [CARD.md ...]")
    failed = False
    for path in paths:
        text = path.read_text(encoding="utf-8")
        missing = [marker for marker in REQUIRED_MARKERS if marker not in text]
        forbidden = [phrase for phrase in FORBIDDEN if phrase.casefold() in text.casefold()]
        if missing or forbidden:
            failed = True; print(f"FAIL: {path}")
            if missing: print("  missing: " + ", ".join(missing))
            if forbidden: print("  forbidden: " + ", ".join(forbidden))
        else: print(f"PASS: {path}")
    raise SystemExit(1 if failed else 0)
if __name__ == "__main__": main()
