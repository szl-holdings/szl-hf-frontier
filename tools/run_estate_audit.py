#!/usr/bin/env python3
"""Run the read-only SZL estate audit pipeline from a local checkout."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(*args: str) -> None:
    subprocess.run([PYTHON, *args], cwd=ROOT, check=True)


def main() -> None:
    run("tools/capture_estate_snapshots.py", "data/snapshots")
    run("tools/build_estate_registry.py", "--input", "data/snapshots", "--registry", "data/estate_registry.json", "--gaps", "reports/unresolved_gaps.json")
    run("validators/validate_estate_registry.py", "data/estate_registry.json")
    run("-m", "unittest", "tests/test_build_estate_registry.py")
    print("PASS: snapshot, registry, duplicate, and gap-report stages completed")


if __name__ == "__main__":
    main()
