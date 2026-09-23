#!/usr/bin/env python3
"""Fail-closed validation for SZL estate registry entries."""
from __future__ import annotations
import json, re, sys
from datetime import datetime
from pathlib import Path

ALLOWED_STATUS = {"MEASURED", "REPRODUCIBLE", "SOURCE_BACKED", "SOFTWARE", "EXPERIMENTAL", "ADVISORY", "PROPOSAL_ONLY", "REFERENCE", "SYNTHETIC", "BLOCKED", "DEPRECATED", "ARCHIVED", "UNAVAILABLE"}
ALLOWED_AUDIT = {"UNREVIEWED", "ALIGNED_ACTIVE", "ALIGNED_REFERENCE", "ALIGNED_ARCHIVED", "ALIGNED_PRIVATE", "NEEDS_SOURCE_FIX", "NEEDS_CARD_REWRITE", "NEEDS_LINK_REPAIR", "NEEDS_STATUS_CORRECTION", "NEEDS_LICENSE_REVIEW", "NEEDS_CANONICAL_MAPPING", "UNAVAILABLE_WITH_REASON"}
URL = re.compile(r"^https://[^\s]+$")
def fail(message): print(f"FAIL: {message}", file=sys.stderr); raise SystemExit(1)
def require_url(value, label):
    if not isinstance(value, str) or not URL.fullmatch(value): fail(f"{label} must be an https URL")
def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/estate_registry.json")
    if not path.is_file(): fail(f"registry not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw: fail("registry must be a non-empty JSON array")
    seen = set()
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict): fail(f"entry {index} is not an object")
        artifact_id = entry.get("id")
        if not isinstance(artifact_id, str) or not artifact_id or artifact_id in seen: fail(f"entry {index} has missing or duplicate id")
        seen.add(artifact_id)
        if entry.get("status") not in ALLOWED_STATUS: fail(f"{artifact_id}: invalid truth status")
        audit = entry.get("audit")
        if not isinstance(audit, dict) or audit.get("status") not in ALLOWED_AUDIT: fail(f"{artifact_id}: invalid audit status")
        try: datetime.fromisoformat(str(audit.get("last_checked", "")).replace("Z", "+00:00"))
        except ValueError: fail(f"{artifact_id}: audit.last_checked must be ISO-8601")
        canonical = entry.get("canonical")
        if not isinstance(canonical, dict): fail(f"{artifact_id}: canonical object required")
        require_url(canonical.get("url"), f"{artifact_id}.canonical.url")
        links = entry.get("links")
        if not isinstance(links, dict): fail(f"{artifact_id}: links object required")
        for name, value in links.items(): require_url(value, f"{artifact_id}.links.{name}")
        if entry.get("status") in {"ARCHIVED", "DEPRECATED"} and "successor" not in links: fail(f"{artifact_id}: archived/deprecated artifacts require links.successor")
        if entry.get("artifact_class") == "kernel" and entry.get("surface") == "huggingface-model" and "github" not in links: fail(f"{artifact_id}: kernel mirror requires canonical GitHub link")
    print(f"PASS: {len(raw)} registry entries validated")
if __name__ == "__main__": main()
