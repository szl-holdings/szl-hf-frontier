#!/usr/bin/env python3
"""Fail-closed validation for SZL estate registry entries."""
from __future__ import annotations
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ALLOWED_STATUS = {"MEASURED", "REPRODUCIBLE", "SOURCE_BACKED", "SOFTWARE", "EXPERIMENTAL", "ADVISORY", "PROPOSAL_ONLY", "REFERENCE", "SYNTHETIC", "BLOCKED", "DEPRECATED", "ARCHIVED", "UNAVAILABLE"}
ALLOWED_AUDIT = {"UNREVIEWED", "ALIGNED_ACTIVE", "ALIGNED_REFERENCE", "ALIGNED_ARCHIVED", "ALIGNED_PRIVATE", "NEEDS_SOURCE_FIX", "NEEDS_CARD_REWRITE", "NEEDS_LINK_REPAIR", "NEEDS_STATUS_CORRECTION", "NEEDS_LICENSE_REVIEW", "NEEDS_CANONICAL_MAPPING", "UNAVAILABLE_WITH_REASON"}
INACTIVE = {"ARCHIVED", "DEPRECATED"}
URL = re.compile(r"^https://[^\s]+$")


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def require_url(value: object, label: str) -> str:
    if not isinstance(value, str) or not URL.fullmatch(value):
        fail(f"{label} must be an https URL")
    return value.rstrip("/")


def normalize_identity(entry: dict) -> str:
    return "|".join((
        str(entry.get("surface", "")).casefold(),
        str(entry.get("artifact_class", "")).casefold(),
        str(entry.get("canonical", {}).get("url", "")).rstrip("/").casefold(),
    ))


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/estate_registry.json")
    if not path.is_file():
        fail(f"registry not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list) or not raw:
        fail("registry must be a non-empty JSON array")

    ids: set[str] = set()
    canonical_urls: dict[str, str] = {}
    public_urls: dict[str, str] = {}
    live_identities: dict[str, str] = {}
    mirror_pairs: dict[tuple[str, str], str] = {}

    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            fail(f"entry {index} is not an object")
        artifact_id = entry.get("id")
        if not isinstance(artifact_id, str) or not artifact_id or artifact_id in ids:
            fail(f"entry {index} has missing or duplicate id")
        ids.add(artifact_id)

        status = entry.get("status")
        if status not in ALLOWED_STATUS:
            fail(f"{artifact_id}: invalid truth status")
        audit = entry.get("audit")
        if not isinstance(audit, dict) or audit.get("status") not in ALLOWED_AUDIT:
            fail(f"{artifact_id}: invalid audit status")
        try:
            datetime.fromisoformat(str(audit.get("last_checked", "")).replace("Z", "+00:00"))
        except ValueError:
            fail(f"{artifact_id}: audit.last_checked must be ISO-8601")

        canonical = entry.get("canonical")
        if not isinstance(canonical, dict):
            fail(f"{artifact_id}: canonical object required")
        canonical_url = require_url(canonical.get("url"), f"{artifact_id}.canonical.url")
        prior_canonical = canonical_urls.get(canonical_url)
        if prior_canonical:
            fail(f"duplicate canonical URL: {artifact_id} and {prior_canonical} -> {canonical_url}")
        canonical_urls[canonical_url] = artifact_id

        links = entry.get("links")
        if not isinstance(links, dict):
            fail(f"{artifact_id}: links object required")
        normalized_links: dict[str, str] = {}
        for name, value in links.items():
            url = require_url(value, f"{artifact_id}.links.{name}")
            normalized_links[name] = url
            prior_public = public_urls.get(url)
            if prior_public and prior_public != artifact_id:
                fail(f"duplicate public URL: {artifact_id} and {prior_public} -> {url}")
            public_urls[url] = artifact_id

        if status in INACTIVE and "successor" not in normalized_links:
            fail(f"{artifact_id}: archived/deprecated artifacts require links.successor")
        if entry.get("artifact_class") == "kernel" and entry.get("surface") == "huggingface-model" and "github" not in normalized_links:
            fail(f"{artifact_id}: kernel mirror requires canonical GitHub link")

        if status not in INACTIVE:
            identity = normalize_identity(entry)
            prior_identity = live_identities.get(identity)
            if prior_identity:
                fail(f"duplicate active identity: {artifact_id} and {prior_identity}")
            live_identities[identity] = artifact_id

        if "github" in normalized_links and "huggingface" in normalized_links:
            pair = (normalized_links["github"], normalized_links["huggingface"])
            prior_pair = mirror_pairs.get(pair)
            if prior_pair:
                fail(f"duplicate GitHub/Hub mirror pair: {artifact_id} and {prior_pair}")
            mirror_pairs[pair] = artifact_id

    print(f"PASS: {len(raw)} registry entries validated; duplicate identities rejected")


if __name__ == "__main__":
    main()
