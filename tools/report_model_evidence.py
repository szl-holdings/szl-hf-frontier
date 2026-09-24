#!/usr/bin/env python3
"""Reproduce a public model-file evidence inventory from local retained inputs.

No provider requests are made. Filenames are observations and candidate pointers;
they cannot establish the contents, integrity, training or qualification of weights.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.capture_estate_snapshots import FILES, SHA, sha256, verify_snapshot_set, write_json
from tools.classify_estate_sources import classify, observation_path, public_items

LABEL = "FILE_LIST_OBSERVATION_ONLY"
WEIGHT_SUFFIXES = (".safetensors", ".gguf", ".bin", ".pt", ".pth", ".onnx")
DIGEST = re.compile(r"[a-f0-9]{64}\Z")
TRAINING_NAME = re.compile(r"(?:^|[/_.-])(?:train(?:ing|er)?|finetun(?:e|ing)|sft|dpo)(?:$|[/_.-])")
TRAINING_RECORD = re.compile(r"(?:log|receipt|state|history|metrics|manifest|run|result)")
EVALUATION_NAME = re.compile(r"(?:^|[/_.-])(?:eval(?:uation)?|evaluations|bench(?:mark)?|results?|scores?)(?:$|[/_.-])")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def retained_path(root: Path, value: Any) -> Path:
    """Committed references must be portable and confined to retained evidence."""
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("Nonportable retained evidence path")
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValueError("Unsafe retained evidence path")
    target = (root / relative).resolve()
    if not target.is_relative_to((root / "data/source-evidence").resolve()):
        raise ValueError("Retained evidence escaped its directory")
    return target


def validate_files(files: Any) -> list[str]:
    if not isinstance(files, list) or any(not isinstance(name, str) or not name for name in files):
        raise ValueError("Malformed retained file inventory")
    for name in files:
        if ("\\" in name or ":" in name or name.startswith("/")
                or any(part in {"", ".", ".."} for part in name.split("/"))):
            raise ValueError("Invalid repository file path")
    if len(files) != len(set(files)) or files != sorted(files):
        raise ValueError("Retained file inventory must be unique and sorted")
    return files


def verify_observation(root: Path, item: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    observation = load_json(observation_path(root / "data/source-evidence", item))
    if not isinstance(observation, dict) or observation.get("id") != item["id"]:
        raise ValueError("Model observation identity mismatch")
    revision = item["inventory"].get("sha")
    if revision is not None and (not isinstance(revision, str) or not SHA.fullmatch(revision)):
        raise ValueError("Model census revision is not immutable")
    if observation.get("observed_revision") != revision:
        raise ValueError("Model observation revision differs from census")
    evidence = observation.get("evidence")
    if not isinstance(evidence, list):
        raise ValueError("Malformed model observation evidence")
    inventory = None
    for record in evidence:
        if (not isinstance(record, dict) or not revision or record.get("revision") != revision
                or not isinstance(record.get("sha256"), str) or not DIGEST.fullmatch(record["sha256"])):
            raise ValueError("Model evidence revision or digest is invalid")
        raw = retained_path(root, record.get("path")).read_bytes()
        if hashlib.sha256(raw).hexdigest() != record["sha256"]:
            raise ValueError("Model retained evidence hash mismatch")
        if record.get("kind") == "file_inventory":
            if inventory is not None:
                raise ValueError("Ambiguous duplicate model file inventory")
            expected_url = f"https://huggingface.co/api/models/{item['name']}/revision/{revision}"
            if record.get("url") != expected_url:
                raise ValueError("File inventory URL does not bind model and revision")
            payload = json.loads(raw)
            if not isinstance(payload, dict) or payload.get("revision") != revision:
                raise ValueError("File inventory payload revision mismatch")
            files = validate_files(payload.get("files"))
            if observation.get("files") != files:
                raise ValueError("Observation filenames differ from hash-bound inventory")
            inventory = record
        elif record.get("kind") == "source_card":
            source_path = record.get("source_path")
            if not isinstance(source_path, str):
                raise ValueError("Source card path is missing")
            validate_files([source_path])
            expected_url = f"{item['url']}/resolve/{revision}/{quote(source_path, safe='/')}"
            if record.get("url") != expected_url:
                raise ValueError("Source card URL does not bind model and revision")
            if observation.get("card") != raw.decode("utf-8", errors="replace"):
                raise ValueError("Observation card differs from hash-bound source")
        else:
            raise ValueError("Unexpected model evidence kind")
    if inventory is None and observation.get("files"):
        raise ValueError("Observed filenames lack hash-bound inventory evidence")
    return observation, inventory


def filename_findings(files: list[str]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[str]] = {name: [] for name in (
        "weight_candidates", "configuration_candidates", "adapter_configuration_candidates",
        "adapter_weight_candidates", "training_log_or_receipt_candidates", "evaluation_or_result_candidates")}
    for filename in files:
        lower = filename.casefold()
        name = PurePosixPath(lower).name
        weight = lower.endswith(WEIGHT_SUFFIXES)
        if weight:
            groups["weight_candidates"].append(filename)
        if name in {"config.json", "config.yaml", "config.yml", "params.json", "generation_config.json"} or name.endswith("_config.json"):
            groups["configuration_candidates"].append(filename)
        if name == "adapter_config.json":
            groups["adapter_configuration_candidates"].append(filename)
        if weight and (name.startswith(("adapter", "lora")) or any(part in {"adapter", "adapters", "lora"} for part in PurePosixPath(lower).parts[:-1])):
            groups["adapter_weight_candidates"].append(filename)
        if TRAINING_NAME.search(lower) and (TRAINING_RECORD.search(lower) or lower.endswith((".log", ".jsonl", ".csv"))):
            groups["training_log_or_receipt_candidates"].append(filename)
        if EVALUATION_NAME.search(lower):
            groups["evaluation_or_result_candidates"].append(filename)
    return {name: {"evidence_label": LABEL, "candidate_files": values, "count": len(values)}
            for name, values in groups.items()}


def next_evidence(review: dict[str, Any], findings: dict[str, Any], available: bool) -> list[dict[str, str]]:
    steps = []
    if not available:
        steps.append({"gate": "immutable_file_inventory", "required": "Recover provider file-list evidence at the exact census revision."})
    if not review.get("links", {}).get("github"):
        steps.append({"gate": "canonical_source_mapping", "required": "Resolve an explicit canonical implementation or support source from retained source evidence."})
    else:
        steps.append({"gate": "source_revision_binding", "required": "Verify the relationship between the mapped implementation revision and Hub artifact bytes."})
    steps.append({"gate": "artifact_contract", "required": "Review whether this model-namespace repository contains a checkpoint, software, a record, or another artifact type."})
    if review.get("artifact_class") == "kernel" and review.get("status") == "SOFTWARE":
        steps.append({"gate": "software_verification", "required": "Verify executable source, dependencies and retained test results before software operation claims; do not assume a checkpoint is required."})
    else:
        steps.extend([
            {"gate": "weight_bytes_and_integrity", "required": "Inspect actual checkpoint bytes and verify their format, immutable content manifest and integrity; filenames alone do not prove weights."},
            {"gate": "training_or_derivation_lineage", "required": "Bind training, adaptation or conversion records to the actual checkpoint digest and declared parent/data/code revisions."},
            {"gate": "evaluation_qualification", "required": "Verify the evaluation protocol, held-out samples, baselines and sample-level results for those exact checkpoint bytes."},
        ])
    steps.extend([
        {"gate": "license_review", "required": "Verify applicable source, data and artifact license terms against retained source material."},
        {"gate": "serving_verification", "required": "Before serving claims, retain a functional runtime probe bound to the exact deployed artifact and source revisions."},
    ])
    return steps


def build_report(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    snapshots = root / "data/snapshots"
    receipt = verify_snapshot_set(snapshots)
    if (receipt.get("scope") != "PUBLIC_PROJECTION_OF_AUTHENTICATED_CENSUS"
            or set(receipt["files"]) != set(FILES.values())):
        raise ValueError("Model report requires the complete authenticated public projection")
    for filename in FILES.values():
        if any(not isinstance(row, dict) or row.get("private") is not False for row in load_json(snapshots / filename)):
            raise ValueError("Model report refuses non-public inventory rows")
    items = public_items(snapshots)
    public_github = {item["name"].casefold() for item in items if item["kind"] == "github"}
    reviews_path = root / "data/source_reviews.json"
    reviews = load_json(reviews_path)
    if not isinstance(reviews, list):
        raise ValueError("Source reviews must be an array")
    by_id = {}
    for review in reviews:
        if not isinstance(review, dict) or not isinstance(review.get("id"), str) or review["id"] in by_id:
            raise ValueError("Malformed or duplicate source review identity")
        by_id[review["id"]] = review
    models = []
    for item in (item for item in items if item["kind"] == "models"):
        review = by_id.get(item["id"])
        if review is None:
            raise ValueError("Model source review is missing")
        observation, inventory = verify_observation(root, item)
        if review != classify(item, observation, public_github):
            raise ValueError("Model source review differs from retained observation")
        findings = filename_findings(observation.get("files", []) if inventory else [])
        models.append({
            "id": item["id"], "repository": item["name"], "url": item["url"],
            "visibility": "public", "revision": item["inventory"].get("sha"),
            "evidence_label": LABEL, "observed_at": observation["observed_at"],
            "file_inventory_available": inventory is not None,
            "file_inventory_evidence": inventory,
            "listed_file_count": len(observation["files"]) if inventory else None,
            "source_classification": {key: review[key] for key in ("artifact_class", "status", "classification")},
            "source_audit_status": review["audit"]["status"],
            "canonical_source_mapping": review.get("links", {}).get("github"),
            "license_metadata": item["inventory"].get("license"),
            "findings": findings,
            "weight_bytes_verified": False, "weight_integrity_verified": False,
            "training_verified": False, "evaluation_verified": False, "serving_verified": False,
            "qualification_status": "UNKNOWN", "promotion_eligible": False,
            "required_next_evidence": next_evidence(review, findings, inventory is not None),
            "observation_errors": observation.get("errors", []),
        })
    models.sort(key=lambda model: model["id"])
    coverage = {"model_repository_count": len(models), "file_inventory_observed_count": sum(model["file_inventory_available"] for model in models),
                "file_inventory_unavailable_count": sum(not model["file_inventory_available"] for model in models),
                "source_mapping_observed_count": sum(bool(model["canonical_source_mapping"]) for model in models),
                "qualified_model_count": 0, "weight_bytes_verified_count": 0, "training_verified_count": 0,
                "evaluation_verified_count": 0, "serving_verified_count": 0,
                "by_source_classification": dict(sorted(Counter(model["source_classification"]["classification"] for model in models).items()))}
    for category in filename_findings([]):
        coverage[category + "_model_count"] = sum(bool(model["findings"][category]["candidate_files"]) for model in models)
        coverage[category + "_file_count"] = sum(model["findings"][category]["count"] for model in models)
    coverage["no_weight_candidates_in_observed_inventory_count"] = sum(model["file_inventory_available"] and not model["findings"]["weight_candidates"]["candidate_files"] for model in models)
    return {"schema": "szl.model-evidence-inventory/v1", "evidence_label": LABEL,
            "generated_at": max([receipt["completed_at"], *(model["observed_at"] for model in models)]),
            "signature_status": "UNSIGNED", "publication_authorized": False,
            "qualification_status": "UNKNOWN", "coverage": coverage,
            "input_bindings": {"snapshot_receipt_sha256": sha256(snapshots / "snapshot_receipt.json"),
                               "model_snapshot_sha256": sha256(snapshots / "huggingface_models.json"),
                               "source_reviews_sha256": sha256(reviews_path)},
            "limits": ["Candidate names are taken only from retained provider file lists; file bodies and weight integrity were not inspected.",
                       "A matching suffix may name an unrelated binary, optimizer state, fixture or placeholder.",
                       "Training/evaluation candidate filenames do not verify their contents, correctness, held-out status or binding to model bytes.",
                       "Source classification is reproduced from retained reviews and grants no qualification or serving authority."],
            "models": models}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository containing retained public evidence; no network access.")
    parser.add_argument("--output", type=Path, help="Defaults to ROOT/reports/model_evidence_inventory.json.")
    args = parser.parse_args(argv)
    report = build_report(args.root)
    output = args.output or args.root / "reports/model_evidence_inventory.json"
    write_json(output, report)
    print(json.dumps({"evidence_label": LABEL, "coverage": report["coverage"], "qualification_status": "UNKNOWN", "publication_authorized": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
