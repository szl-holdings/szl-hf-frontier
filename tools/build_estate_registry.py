#!/usr/bin/env python3
"""Build a deterministic SZL estate registry from connector snapshots.

Inputs are JSON snapshots produced by approved inventory collectors. This tool makes
no network calls and performs no mutation outside its explicit output paths.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HF_SURFACES = {
    "models": "huggingface-model",
    "datasets": "huggingface-dataset",
    "spaces": "huggingface-space",
}
ARCHIVE_WORDS = ("archived", "deprecated", "historical", "frozen", "terminal")
URL = re.compile(r"https://[^\s)]+")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def artifact_id(surface: str, name: str) -> str:
    normalized = re.sub(r"[^a-z0-9._/-]+", "-", name.casefold()).strip("-")
    return f"{surface}/{normalized}"


def classify_github(item: dict[str, Any]) -> tuple[str, str, str, dict[str, str], list[str]]:
    description = str(item.get("description") or "")
    lower = description.casefold()
    archived = bool(item.get("archived"))
    urls = URL.findall(description)
    links: dict[str, str] = {}
    notes: list[str] = []
    if archived or any(word in lower for word in ARCHIVE_WORDS):
        status = "ARCHIVED" if "deprecated" not in lower else "DEPRECATED"
        klass = "archive"
        successor = next((url for url in urls if "github.com/szl-holdings/" in url), None)
        if successor:
            links["successor"] = successor
        else:
            notes.append("Terminal/archive artifact; successor must be reviewed explicitly.")
    else:
        status = "SOURCE_BACKED"
        klass = "repository"
    canonical_role = "successor" if status in {"ARCHIVED", "DEPRECATED"} and links.get("successor") else "source"
    canonical_url = links.get("successor") or str(item["html_url"])
    return klass, status, canonical_role, links, notes


def classify_hf(kind: str, item: dict[str, Any]) -> tuple[str, str, str, list[str]]:
    name = str(item["path"])
    lower = name.casefold()
    notes: list[str] = []
    if kind == "models":
        klass = "kernel" if any(token in lower for token in ("kernel", "lambda", "formulas", "invariants", "govsign", "provctl", "blocked", "ouroboros")) else "model"
        status = "SOFTWARE" if klass == "kernel" else "SOURCE_BACKED"
    elif kind == "datasets":
        klass, status = "dataset", "SOURCE_BACKED"
    else:
        klass, status = "space", "SOFTWARE"
    if bool(item.get("private")):
        notes.append("Private artifact: audit metadata only; do not disclose contents.")
    if item.get("gated"):
        notes.append(f"Hub access is gated: {item['gated']}.")
    return klass, status, "runtime" if kind == "spaces" else "mirror", notes


def hf_url(kind: str, path: str) -> str:
    prefix = "" if kind == "models" else f"{kind}/"
    return f"https://huggingface.co/{prefix}{path}"


def build_registry(root: Path) -> list[dict[str, Any]]:
    checked = utc_now()
    registry: list[dict[str, Any]] = []
    github_path = root / "github_repositories.json"
    if github_path.is_file():
        for item in load_json(github_path):
            klass, status, role, links, notes = classify_github(item)
            url = str(item["html_url"])
            registry.append({
                "id": artifact_id("github", str(item["full_name"])),
                "surface": "github",
                "artifact_class": klass,
                "visibility": "private" if item.get("private") else "public",
                "status": status,
                "canonical": {"role": role, "url": url if role == "source" else links["successor"]},
                "links": {"github": url, **links},
                "license": str((item.get("license") or {}).get("spdx_id") or "UNKNOWN"),
                "audit": {"status": "UNREVIEWED", "last_checked": checked, "notes": notes},
            })
    for kind, surface in HF_SURFACES.items():
        path = root / f"huggingface_{kind}.json"
        if not path.is_file():
            continue
        for item in load_json(path):
            name = str(item["path"])
            klass, status, role, notes = classify_hf(kind, item)
            url = hf_url(kind, name)
            links = {"huggingface": url}
            if kind == "spaces":
                links["space"] = url
            registry.append({
                "id": artifact_id(surface, name),
                "surface": surface,
                "artifact_class": klass,
                "visibility": "private" if item.get("private") else "public",
                "status": status,
                "canonical": {"role": role, "url": url},
                "links": links,
                "license": "UNKNOWN",
                "audit": {"status": "UNREVIEWED", "last_checked": checked, "notes": notes},
            })
    return sorted(registry, key=lambda entry: entry["id"])


def gap_report(registry: list[dict[str, Any]]) -> dict[str, Any]:
    gaps: list[dict[str, str]] = []
    for entry in registry:
        if entry["license"] == "UNKNOWN":
            gaps.append({"id": entry["id"], "severity": "medium", "gate": "license", "reason": "License requires source-level review."})
        if entry["status"] in {"ARCHIVED", "DEPRECATED"} and "successor" not in entry["links"]:
            gaps.append({"id": entry["id"], "severity": "high", "gate": "canonical-route", "reason": "Archive/deprecation lacks explicit successor."})
        if entry["surface"] == "huggingface-model" and entry["artifact_class"] == "kernel":
            gaps.append({"id": entry["id"], "severity": "medium", "gate": "mirror-link", "reason": "Canonical GitHub link requires source-level mapping."})
    return {"generated_at": utc_now(), "artifact_count": len(registry), "unresolved_gaps": gaps}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/snapshots")
    parser.add_argument("--registry", default="data/estate_registry.json")
    parser.add_argument("--gaps", default="reports/unresolved_gaps.json")
    args = parser.parse_args()
    registry = build_registry(Path(args.input))
    if not registry:
        raise SystemExit("No snapshots found; registry was not written.")
    write_json(Path(args.registry), registry)
    write_json(Path(args.gaps), gap_report(registry))
    print(f"Wrote {len(registry)} registry entries to {args.registry}")


if __name__ == "__main__":
    main()
