#!/usr/bin/env python3
"""Offline verification of committed public census, source reviews and draft outputs.

A passing result establishes reproducibility and integrity only. It does not
clear the separately retained release gate or verify receipt signer identity.
"""
from __future__ import annotations

import json
import hashlib
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_estate_registry import build_registry, gap_report
from tools.capture_estate_snapshots import FILES, verify_snapshot_set
from tools.classify_estate_sources import classify, load_observation, public_items
from tools.report_model_evidence import build_report
from tools.probe_estate_runtime import assess_runtime


def verify(root: Path = ROOT) -> dict:
    snapshots = root / "data/snapshots"
    receipt = verify_snapshot_set(snapshots)
    if receipt["scope"] != "PUBLIC_PROJECTION_OF_AUTHENTICATED_CENSUS":
        raise ValueError("Committed census must be the public projection of an authenticated capture")
    if set(receipt["files"]) != set(FILES.values()):
        raise ValueError("Snapshot receipt contains unexpected file paths")
    for filename in receipt["files"]:
        rows = json.loads((snapshots / filename).read_text(encoding="utf-8"))
        if any(row.get("private") is not False for row in rows):
            raise ValueError("Committed snapshot contains a non-public row")
    reviews_path = root / "data/source_reviews.json"
    expected_reviews = json.loads(reviews_path.read_text(encoding="utf-8"))
    items = public_items(snapshots)
    public_github = {row["name"].casefold() for row in items if row["kind"] == "github"}
    rebuilt_reviews = [classify(item, load_observation(root / "data/source-evidence", item), public_github) for item in items]
    if rebuilt_reviews != expected_reviews:
        raise ValueError("Source reviews differ from retained immutable observations")
    registry = build_registry(snapshots, reviews_path)
    gaps = gap_report(registry)
    for relative, actual in (("data/estate_registry.json", registry), ("reports/unresolved_gaps.json", gaps)):
        if json.loads((root / relative).read_text(encoding="utf-8")) != actual:
            raise ValueError(f"{relative}: committed output is not reproducible")
    if json.loads((root / "reports/model_evidence_inventory.json").read_text(encoding="utf-8")) != build_report(root):
        raise ValueError("Model file-evidence report is not reproducible")
    audit = json.loads((root / "reports/estate_audit_receipt.json").read_text(encoding="utf-8"))
    if audit.get("publication_authorized") is not False or audit.get("signature_status") != "UNSIGNED":
        raise ValueError("Audit receipt must preserve its unsigned, non-authorizing boundary")
    if gaps["unresolved_gaps"] and audit.get("status") != "BLOCKED_GAPS":
        raise ValueError("Audit receipt incorrectly clears unresolved gates")
    output_paths = {"registry": "data/estate_registry.json", "gaps": "reports/unresolved_gaps.json",
                    "build_log": "reports/estate_audit_receipt.build.log", "validation_log": "reports/estate_audit_receipt.validation.log"}
    for name, relative in output_paths.items():
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != audit["outputs"][name]["sha256"]:
            raise ValueError("Audit output hash differs from retained receipt")
    runtime = json.loads((root / "reports/runtime_witness.json").read_text(encoding="utf-8"))
    spaces = {"huggingface-space/" + row["path"].casefold(): row["sha"] for row in json.loads((snapshots / "huggingface_spaces.json").read_text(encoding="utf-8"))}
    if len(runtime["artifacts"]) != len(spaces) or {row["id"] for row in runtime["artifacts"]} != set(spaces):
        raise ValueError("Runtime witness does not cover the public Space census")
    for row in runtime["artifacts"]:
        if row["expected_hf_revision"] != spaces[row["id"]] or row["runtime"] != assess_runtime(row) or row.get("functional_inference_verified") is not False:
            raise ValueError("Runtime assessment does not match retained observations or scope")
    if runtime["by_runtime"] != dict(Counter(row["runtime"] for row in runtime["artifacts"])):
        raise ValueError("Runtime summary count mismatch")
    validated = subprocess.run([sys.executable, str(root / "validators/validate_estate_registry.py"), str(root / "data/estate_registry.json"), "--structure-only"], capture_output=True, text=True)
    if validated.returncode:
        raise ValueError("Registry structural integrity check failed")
    return {"artifact_count": len(registry), "reproducible": True,
            "signature_status": "UNSIGNED", "publication_authorized": False,
            "unresolved_gap_count": len(gaps["unresolved_gaps"])}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
