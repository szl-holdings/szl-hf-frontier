#!/usr/bin/env python3
"""Compile an evidence-bounded draft; a provider listing never grants readiness."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

HF_SURFACES = {"models": "huggingface-model", "datasets": "huggingface-dataset", "spaces": "huggingface-space"}
SNAPSHOTS = ("github_repositories.json", *(f"huggingface_{kind}.json" for kind in HF_SURFACES))
REVIEW_STATUS = {"UNREVIEWED", "NEEDS_SOURCE_FIX", "NEEDS_CARD_REWRITE", "NEEDS_LINK_REPAIR", "NEEDS_STATUS_CORRECTION", "NEEDS_LICENSE_REVIEW", "NEEDS_CANONICAL_MAPPING", "UNAVAILABLE_WITH_REASON"}
TRUTH_STATUS = {"SOURCE_BACKED", "SOFTWARE", "EXPERIMENTAL", "ADVISORY", "PROPOSAL_ONLY", "REFERENCE", "SYNTHETIC", "BLOCKED", "DEPRECATED", "ARCHIVED", "UNAVAILABLE"}
SHA = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")

def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")

def artifact_id(surface: str, name: str) -> str:
    normalized = re.sub(r"[^a-z0-9._/-]+", "-", name.casefold()).strip("-")
    return f"{surface}/{normalized}"

def hf_url(kind: str, path: str) -> str:
    return f"https://huggingface.co/{'' if kind == 'models' else kind + '/'}{path}"

def _time(value: Any) -> str:
    if not isinstance(value, str) or datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is None:
        raise ValueError("Snapshot completion time must include a timezone")
    return value

def _license(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("spdx_id")
    if not isinstance(value, str) or value in {"", "NOASSERTION", "NONE"}:
        return "UNKNOWN"
    return value

def _source_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value)
    return parsed.scheme == "https" and parsed.netloc == "github.com" and parsed.path.startswith("/szl-holdings/")

def _repo_url(value: Any) -> str:
    if not _source_url(value):
        return ""
    parts = urlsplit(value).path.strip("/").split("/")
    return "https://github.com/" + "/".join(parts[:2]).casefold()

def classify_github(item: dict[str, Any]) -> tuple[str, str, str, dict[str, str], list[str]]:
    description = str(item.get("description") or "")
    deprecated = bool(re.match(r"^\s*(?:\[)?deprecated\b", description, re.I))
    inactive = item.get("archived") is True or deprecated
    status = "DEPRECATED" if deprecated else "ARCHIVED" if inactive else "REFERENCE"
    links = {}
    if inactive:
        match = re.search(r"(?:canonical|successor|replaced by|moved to)\s*[:=-]?\s*(https://[^\s)]+)", description, re.I)
        if match and _source_url(match[1]):
            links["successor"] = match[1].rstrip("./")
    return "archive" if inactive else "repository", status, "record" if inactive else "source", links, ["Provider metadata observed; implementation and public claims still require review."]

def classify_hf(kind: str, item: dict[str, Any]) -> tuple[str, str, str, list[str]]:
    name = str(item["path"]).casefold()
    klass = {"models": "model", "datasets": "dataset", "spaces": "space"}[kind]
    notes = ["Hub listing establishes artifact existence only; training, qualification and runtime functionality are unverified."]
    if kind == "models" and any(token in name for token in ("kernel", "lambda", "formulas", "invariants", "govsign", "provctl", "blocked", "ouroboros")):
        klass = "kernel"
        notes.append("Kernel class is a name-based candidate until source review; it does not establish executable software.")
    return klass, "REFERENCE" if kind == "datasets" else "EXPERIMENTAL", "runtime" if kind == "spaces" else "mirror", notes

def apply_reviews(registry: list[dict[str, Any]], reviews: list[dict[str, Any]], evidence_root: Path) -> None:
    by_id = {row["id"]: row for row in registry}
    seen = set()
    for review in reviews:
        key = review.get("id")
        if key not in by_id or key in seen:
            raise ValueError("Review contains an unknown or duplicate artifact identity")
        seen.add(key)
        entry = by_id[key]
        revision = review.get("observed_revision")
        if revision != entry.get("revision"):
            raise ValueError(f"{key}: review revision differs from census revision")
        if not revision and review.get("evidence"):
            raise ValueError(f"{key}: source evidence requires an immutable revision")
        audit = review.get("audit", {})
        if audit.get("status") not in REVIEW_STATUS:
            raise ValueError(f"{key}: automated review cannot grant alignment or release authorization")
        _time(audit.get("last_checked"))
        valid = []
        for record in review.get("evidence", []):
            digest, relative = record.get("sha256"), record.get("path")
            if not digest or not relative:
                continue
            target = (evidence_root / relative).resolve()
            if not target.is_relative_to(evidence_root.resolve()) or target.is_symlink():
                raise ValueError(f"{key}: unsafe evidence path")
            if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError(f"{key}: source evidence bytes do not match digest")
            if record.get("revision") != revision:
                raise ValueError(f"{key}: evidence revision differs from census revision")
            if record.get("kind") == "source_card":
                identity = entry["links"].get("huggingface") or entry["links"]["github"]
                route = "blob" if entry["surface"] == "github" else "resolve"
                prefix = f"{identity}/{route}/{revision}/"
                url = record.get("url", "")
                parsed = urlsplit(url)
                source_path = record.get("source_path")
                if (not isinstance(url, str) or not url.startswith(prefix) or parsed.query or parsed.fragment
                        or not isinstance(source_path, str) or not source_path
                        or unquote(url[len(prefix):]) != source_path
                        or any(part in {"", ".", ".."} for part in source_path.split("/"))):
                    raise ValueError(f"{key}: source card URL does not bind artifact, revision and path")
            valid.append(record)
        if any(record.get("kind") == "source_card" for record in valid):
            if review.get("status") not in TRUTH_STATUS:
                raise ValueError(f"{key}: unsupported automated truth promotion")
            prior_status = entry["status"]
            entry["status"] = review["status"]
            entry["artifact_class"] = review.get("artifact_class", entry["artifact_class"])
            if review.get("canonical"):
                if review["canonical"].get("url", "").rstrip("/") != entry["canonical"]["url"].rstrip("/"):
                    raise ValueError(f"{key}: review must preserve the artifact's canonical ownership URL")
                entry["canonical"] = review["canonical"]
            entry["links"].pop("successor", None)
            entry["links"].update(review.get("links", {}))
            entry["audit"] = audit
            entry["classification"] = review.get("classification", "unresolved")
            entry["evidence"] = valid
            if prior_status in {"ARCHIVED", "DEPRECATED"} and review["status"] not in {"ARCHIVED", "DEPRECATED"}:
                entry["status"] = prior_status
                entry["artifact_class"] = "archive"
                entry["canonical"]["role"] = "record"
                entry["classification"] = "archived_provenance" if prior_status == "ARCHIVED" else "successor_deprecated"
                entry["audit"] = {**audit, "status": "NEEDS_CANONICAL_MAPPING", "notes": [*audit.get("notes", []), "Automated card extraction cannot reactivate archived/deprecated inventory; explicit lifecycle review is required."]}
        else:
            entry["audit"]["status"] = "UNAVAILABLE_WITH_REASON"
            entry["audit"]["notes"].extend(audit.get("notes", []))
            entry["audit"]["notes"].append("No hash-verified source card evidence was available at the observed revision.")
        entry["source_claims"] = review.get("source_claims", [])
        entry["candidate_recommendations"] = review.get("candidate_recommendations", [])

def build_registry(root: Path, reviews: Path | None = None) -> list[dict[str, Any]]:
    receipt = load_json(root / "snapshot_receipt.json")
    if receipt.get("complete") is not True:
        raise ValueError("Snapshot receipt is incomplete")
    checked = _time(receipt.get("completed_at"))
    snapshots = {}
    for filename in SNAPSHOTS:
        path = root / filename
        expected = receipt.get("files", {}).get(filename, {})
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected.get("sha256"):
            raise ValueError(f"{filename}: snapshot hash mismatch")
        values = load_json(path)
        if not isinstance(values, list) or expected.get("count") != len(values):
            raise ValueError(f"{filename}: invalid snapshot count")
        snapshots[filename] = values
    registry = []
    for filename, values in snapshots.items():
        kind = None if filename.startswith("github_") else filename.removeprefix("huggingface_").removesuffix(".json")
        for item in values:
            if not isinstance(item.get("private"), bool):
                raise ValueError("Snapshot visibility must be explicitly boolean")
            if kind is None:
                surface, name = "github", item["full_name"]
                klass, status, role, links, notes = classify_github(item)
                url = item["html_url"]
                links = {"github": url, **links}
                revision = item.get("source_revision") or item.get("sha")
            else:
                surface, name = HF_SURFACES[kind], item["path"]
                klass, status, role, notes = classify_hf(kind, item)
                url = hf_url(kind, name)
                links = {"huggingface": url, **({"space": url} if kind == "spaces" else {})}
                revision = item.get("sha")
            entry = {
                "id": artifact_id(surface, name), "surface": surface, "artifact_class": klass,
                "visibility": "private" if item["private"] else "public", "status": status,
                "canonical": {"role": role, "url": url}, "links": links,
                "license": _license(item.get("license")),
                "audit": {"status": "UNREVIEWED", "last_checked": checked, "notes": notes},
                "classification": "unresolved", "evidence": [],
                "observed": {key: item.get(key) for key in ("pushed_at", "updated_at", "archived", "gated", "downloads", "runtime") if key in item},
            }
            if isinstance(revision, str) and SHA.fullmatch(revision):
                entry["revision"] = revision
            registry.append(entry)
    registry.sort(key=lambda entry: entry["id"])
    if len({row["id"] for row in registry}) != len(registry):
        raise ValueError("Snapshot contains duplicate artifact identities")
    if reviews:
        raw = load_json(reviews)
        if not isinstance(raw, list):
            raise ValueError("Source reviews must be an array")
        apply_reviews(registry, raw, reviews.parent.parent)
    return registry

def gap_report(registry: list[dict[str, Any]]) -> dict[str, Any]:
    gaps = []
    active_sources = {_repo_url(row["links"].get("github")) for row in registry if row["surface"] == "github" and row["status"] not in {"ARCHIVED", "DEPRECATED"}}
    active_sources.discard("")
    def gap(entry, severity, gate, reason):
        gaps.append({"id": entry["id"], "severity": severity, "gate": gate, "reason": reason, "owner": "szl-holdings"})
    for entry in registry:
        if entry["license"] == "UNKNOWN":
            gap(entry, "medium", "license", "License requires source-level review.")
        if not entry.get("revision"):
            gap(entry, "high", "source-revision", "Immutable source revision was not observed.")
        if entry["status"] in {"ARCHIVED", "DEPRECATED"} and (_repo_url(entry["links"].get("successor")) not in active_sources or _repo_url(entry["links"].get("successor")) == _repo_url(entry["canonical"]["url"])):
            gap(entry, "high", "canonical-route", "Archive/deprecation lacks an explicit non-self successor present in the active GitHub census.")
        if entry["surface"].startswith("huggingface-") and _repo_url(entry["links"].get("github")) not in active_sources:
            gap(entry, "high", "canonical-route", "Canonical GitHub implementation or support source remains unresolved.")
        if entry.get("classification", "unresolved") == "unresolved":
            gap(entry, "high", "source-classification", "Source-level relationship classification remains unresolved.")
        audit = entry.get("audit", {}).get("status", "UNREVIEWED")
        if audit != "UNREVIEWED" and not audit.startswith("ALIGNED_"):
            gap(entry, "high", "source-review", f"Source review disposition: {audit}.")
        elif audit == "UNREVIEWED":
            gap(entry, "medium", "alignment-review", "Extracted source relationships do not complete the public card and operational evidence gates.")
        runtime = entry.get("observed", {}).get("runtime") or {}
        if isinstance(runtime, dict) and runtime.get("stage") in {"RUNTIME_ERROR", "BUILD_ERROR", "CONFIG_ERROR", "ERROR"}:
            gap(entry, "high", "runtime", f"Provider reports {runtime['stage']}; functional operation is not established.")
    gaps.sort(key=lambda row: (0 if row["severity"] == "high" else 1, row["id"], row["gate"]))
    return {"generated_at": max((row.get("audit", {}).get("last_checked", "") for row in registry), default=""),
            "artifact_count": len(registry), "promotion_eligible": False, "signature_status": "UNSIGNED",
            "summary": dict(sorted(Counter(row["gate"] for row in gaps).items())), "unresolved_gaps": gaps}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="data/snapshots")
    parser.add_argument("--registry", default="data/estate_registry.json")
    parser.add_argument("--gaps", default="reports/unresolved_gaps.json")
    parser.add_argument("--reviews", type=Path)
    args = parser.parse_args()
    registry = build_registry(Path(args.input), args.reviews)
    if not registry:
        raise SystemExit("No artifacts found; registry was not written.")
    write_json(Path(args.registry), registry)
    write_json(Path(args.gaps), gap_report(registry))
    print(f"Wrote {len(registry)} draft entries; promotion remains blocked pending all gates.")

if __name__ == "__main__":
    main()
