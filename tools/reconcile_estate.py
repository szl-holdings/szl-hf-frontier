#!/usr/bin/env python3
"""Compile source review decisions without erasing the original audit or promoting assets.

This verifies evidence integrity and the recorded review scope. It is not an
independent semantic review, a model qualification, or a release authorization.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
CLASSES = {"canonical_source", "mirror_distribution", "successor_deprecated",
           "archived_provenance", "experimental_blocked", "operational_runtime_surface", "support_artifact"}
GATES = {"canonical-route", "source-classification", "source-review", "alignment-review", "license"}
SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def timestamp(value):
    if not isinstance(value, str) or datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is None:
        raise ValueError("Review time requires a timezone")
    return value


def retained(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise ValueError("Evidence path must be a relative POSIX path")
    raw = Path(relative)
    if raw.is_absolute() or any(part in {".", ".."} for part in relative.split("/")):
        raise ValueError("Unsafe evidence path")
    current = root
    for part in raw.parts:
        current = current / part
        if current.is_symlink() or getattr(current.stat(follow_symlinks=False), "st_file_attributes", 0) & 1024:
            raise ValueError("Evidence must not traverse a symlink or reparse point")
    if not current.resolve().is_relative_to(root.resolve()) or not current.is_file():
        raise ValueError("Evidence escapes repository")
    return current


def identity_url(identity: str) -> str:
    prefixes = {"github/": "https://github.com/", "huggingface-model/": "https://huggingface.co/",
                "huggingface-dataset/": "https://huggingface.co/datasets/",
                "huggingface-space/": "https://huggingface.co/spaces/"}
    for prefix, url in prefixes.items():
        if identity.startswith(prefix):
            return url + identity[len(prefix):]
    if identity.startswith("https://"):
        return identity.rstrip("/")
    raise ValueError("Evidence source identity must name an artifact or its canonical URL")


def verify_evidence(root: Path, record: dict, census: dict) -> None:
    if not isinstance(record, dict) or not DIGEST.fullmatch(str(record.get("sha256", ""))):
        raise ValueError("Evidence requires a SHA256 digest")
    target = retained(root, record.get("path"))
    if digest(target) != record["sha256"]:
        raise ValueError("Retained evidence digest mismatch")
    revision = record.get("revision")
    if not isinstance(revision, str) or not SHA.fullmatch(revision):
        raise ValueError("Evidence requires an immutable source revision")
    identity = record.get("source_identity")
    if not isinstance(identity, str):
        raise ValueError("Evidence source identity missing")
    if identity not in census or census[identity].get("visibility") != "public":
        raise ValueError("Evidence source must belong to the public census")
    origin = identity_url(identity)
    url = record.get("url", "")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Evidence URL requires a plain public HTTPS source")
    if record.get("kind") == "source_tree":
        if not origin.startswith("https://github.com/"):
            raise ValueError("Source tree requires a GitHub repository identity")
        expected = "https://api.github.com/repos/" + origin.removeprefix("https://github.com/") + f"/git/trees/{revision}?recursive=1"
        if url.casefold() != expected.casefold():
            raise ValueError("Source tree URL must bind the exact repository and commit")
        tree = load(target)
        if tree.get("truncated") is not False or not isinstance(tree.get("tree"), list):
            raise ValueError("Source tree evidence is incomplete")
        return
    if parsed.query:
        raise ValueError("Source file evidence URL cannot contain query parameters")
    if record.get("kind") == "census_snapshot":
        if identity not in census or census[identity].get("revision") != revision:
            raise ValueError("Snapshot evidence revision or identity differs from census")
        if url.rstrip("/").casefold() != origin.casefold():
            raise ValueError("Snapshot URL identity mismatch")
        receipt = load(root / "data/snapshots/snapshot_receipt.json")
        relative = record["path"]
        if relative != "data/snapshots/" + target.name or receipt["files"].get(target.name, {}).get("sha256") != record["sha256"]:
            raise ValueError("Snapshot evidence is not bound by the authenticated projection receipt")
        return
    if record.get("kind") not in {"source_card", "source_file", "license_file", "publisher_manifest", "migration_provenance"}:
        raise ValueError("Unsupported source evidence kind")
    parsed_origin = urlsplit(origin)
    if parsed_origin.netloc not in {"github.com", "huggingface.co"}:
        raise ValueError("Source evidence must originate from GitHub or Hugging Face")
    route = "blob" if parsed_origin.netloc == "github.com" else "resolve"
    prefix = f"{origin}/{route}/{revision}/"
    source_path = record.get("source_path")
    if (not isinstance(source_path, str) or not source_path or "\\" in source_path
            or any(part in {"", ".", ".."} for part in source_path.split("/"))
            or not url.casefold().startswith(prefix.casefold()) or unquote(url[len(prefix):]) != source_path):
        raise ValueError("Evidence URL must bind source identity, revision, and file path")


def validate_route(route: dict, active: set[str], evidence: list[dict], self_url: str, root: Path) -> None:
    if not isinstance(route, dict):
        raise ValueError("A resolved route requires an explicit implementation route")
    repository = route.get("repository", "").rstrip("/").casefold()
    if repository not in active or repository == self_url.casefold().rstrip("/"):
        raise ValueError("Successor/implementation route must identify an active non-self GitHub source")
    revision = route.get("revision", "")
    if not SHA.fullmatch(revision):
        raise ValueError("Resolved implementation route requires an immutable revision")
    if not any(identity_url(ref["source_identity"]).casefold() == repository and ref["revision"] == revision
               and ref["kind"] != "census_snapshot" for ref in evidence):
        raise ValueError("Implementation route lacks retained target-source evidence")
    path = route.get("path", "")
    if not isinstance(path, str) or path.startswith("/") or "\\" in path or any(part in {".", ".."} for part in path.split("/")):
        raise ValueError("Invalid implementation path")
    if path:
        found = False
        for ref in evidence:
            if identity_url(ref["source_identity"]).casefold() != repository or ref["revision"] != revision:
                continue
            if ref["kind"] == "source_tree":
                found |= any(row.get("path") == path or str(row.get("path", "")).startswith(path.rstrip("/") + "/")
                             for row in load(retained(root, ref["path"]))["tree"])
            else:
                found |= ref.get("source_path") == path or str(ref.get("source_path", "")).startswith(path.rstrip("/") + "/")
        if not found:
            raise ValueError("Declared implementation path is absent from retained target evidence")


def reconcile(root: Path = ROOT, decisions_path: Path | None = None) -> tuple[dict, list[dict]]:
    decisions_path = decisions_path or root / "data/reconciliation/source_decisions.json"
    baseline = load(root / "data/estate_registry.json")
    original = load(root / "reports/unresolved_gaps.json")
    ledger = load(decisions_path)
    if ledger.get("schema") != "szl.source-reconciliation/v1":
        raise ValueError("Unsupported source reconciliation schema")
    checked = timestamp(ledger.get("generated_at"))
    if ledger.get("census_receipt_sha256") != digest(root / "data/snapshots/snapshot_receipt.json"):
        raise ValueError("Decisions do not bind this census receipt")
    census = {row["id"]: row for row in baseline}
    active = {row["canonical"]["url"].casefold().rstrip("/") for row in baseline
              if row["surface"] == "github" and row["status"] not in {"ARCHIVED", "DEPRECATED"}}
    gaps = {(row["id"], row["gate"]): row for row in original["unresolved_gaps"]}
    closed, seen = {}, set()
    result = copy.deepcopy(census)
    for decision in ledger.get("decisions", []):
        key = decision.get("id")
        if key not in census or key in seen:
            raise ValueError("Duplicate or unknown review identity")
        seen.add(key)
        entry = census[key]
        if decision.get("observed_revision") != entry.get("revision"):
            raise ValueError("Decision revision differs from the observed census")
        canonical = decision.get("canonical", {})
        if canonical.get("url", "").rstrip("/").casefold() != entry["canonical"]["url"].rstrip("/").casefold():
            raise ValueError("Reconciliation cannot transfer canonical ownership")
        if canonical.get("role") not in {"source", "mirror", "runtime", "record", "successor", "none"}:
            raise ValueError("Unsupported canonical role")
        classification = decision.get("classification")
        if classification not in CLASSES:
            raise ValueError("Review requires a supported source classification")
        findings = decision.get("findings", [])
        seen_gates = set()
        for finding in findings:
            gate = finding.get("gate")
            if gate not in GATES or gate in seen_gates:
                raise ValueError("Unsupported or duplicate review gate")
            seen_gates.add(gate)
            disposition = finding.get("disposition")
            if disposition not in {"resolved", "remaining"}:
                raise ValueError("Unknown finding disposition")
            if not isinstance(finding.get("reason"), str) or not finding["reason"].strip():
                raise ValueError("Finding requires a concrete rationale")
            refs = finding.get("evidence_refs", [])
            for ref in refs:
                verify_evidence(root, ref, census)
            if disposition != "resolved":
                continue
            if not refs or not finding.get("supported_facts"):
                raise ValueError("Resolved findings require retained evidence and supported facts")
            if not any(ref["source_identity"] == key and ref["revision"] == entry["revision"] for ref in refs):
                raise ValueError("Finding requires evidence from the reviewed artifact's exact revision")
            if gate in {"source-review", "alignment-review"}:
                raise ValueError("Source reconciliation cannot close public-card or operational alignment review")
            if gate == "canonical-route":
                lifecycle = decision.get("lifecycle", {})
                primary = decision.get("implementation_route")
                multiple = decision.get("implementation_routes", [])
                if not isinstance(multiple, list) or multiple and primary != multiple[0]:
                    raise ValueError("Implementation primary and plural routes disagree")
                routes = [*multiple]
                if primary is not None:
                    routes.append(primary)
                if lifecycle.get("successor_route") is not None:
                    routes.append(lifecycle["successor_route"])
                successors = lifecycle.get("successor_routes", [])
                if not isinstance(successors, list):
                    raise ValueError("Successor routes must be an array")
                routes.extend(successors)
                for route in routes:
                    validate_route(route, active, refs, entry["canonical"]["url"], root)
                if lifecycle.get("disposition") == "terminal_provenance":
                    if (entry["status"] != "ARCHIVED" or classification != "archived_provenance"
                            or lifecycle.get("status") != "ARCHIVED" or not lifecycle.get("reason")
                            or not lifecycle.get("terminal_purpose")
                            or decision["canonical"].get("role") != "record"):
                        raise ValueError("Terminal provenance requires an explicitly archived canonical record")
                    if not any(ref["kind"] == "source_card" and ref["source_identity"] == key for ref in refs):
                        raise ValueError("Terminal provenance requires its own source card, not just an archive flag")
                else:
                    if not routes:
                        raise ValueError("A resolved relationship requires at least one route")
            if gate == "license":
                license_record = decision.get("license", {})
                identifier = license_record.get("identifier")
                if not isinstance(identifier, str) or identifier in {"", "UNKNOWN", "NOASSERTION", "NONE"}:
                    raise ValueError("License finding lacks an observed grant")
                if license_record.get("scope") not in {"artifact", "repository", "distribution"}:
                    raise ValueError("License evidence must apply to the artifact, not just an upstream dependency")
                if not any(ref["kind"] in {"license_file", "source_card"} for ref in refs):
                    raise ValueError("License resolution requires retained license/card bytes")
                result[key]["license"] = identifier
            if (key, gate) in gaps:
                closed[(key, gate)] = {**gaps[(key, gate)], "resolution": finding, "reviewed_at": checked}
        if ("source-classification" in seen_gates and any(f["gate"] == "source-classification" and f["disposition"] == "resolved" for f in findings)):
            result[key]["classification"] = classification
            result[key]["canonical"] = canonical
        elif classification != entry.get("classification"):
            raise ValueError("Changing classification requires its own resolved evidence-backed finding")
        elif canonical != entry["canonical"]:
            raise ValueError("Changing canonical role requires evidence-backed classification")
        if (decision.get("implementation_route") or decision.get("implementation_routes")
                or decision.get("lifecycle", {}).get("successor_route") or decision.get("lifecycle", {}).get("successor_routes")):
            if not any(f["gate"] == "canonical-route" and f["disposition"] == "resolved" for f in findings):
                raise ValueError("Declared routes require a resolved, evidence-backed relationship finding")
        result[key]["reconciliation"] = decision
    remaining = [row for key, row in gaps.items() if key not in closed]
    report = {"schema": "szl.reconciliation-report/v1", "generated_at": checked,
              "baseline_gap_sha256": digest(root / "reports/unresolved_gaps.json"),
              "baseline_registry_sha256": digest(root / "data/estate_registry.json"),
              "decision_ledger_sha256": digest(decisions_path),
              "scope": "SOURCE_RELATIONSHIP_REVIEW", "publication_authorized": False,
              "signature_status": "UNSIGNED", "semantic_review_independently_verified": False,
              "artifact_count": len(census), "reviewed_artifacts": len(seen),
              "baseline_gap_count": len(gaps), "resolved_gap_count": len(closed),
              "remaining_gap_count": len(remaining),
              "resolved_by_gate": dict(sorted(Counter(row["gate"] for row in closed.values()).items())),
              "remaining_by_gate": dict(sorted(Counter(row["gate"] for row in remaining).items())),
              "resolved_gaps": list(closed.values()), "remaining_gaps": remaining}
    return report, list(result.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report, registry = reconcile(args.root)
    for relative, value in (("reports/estate_reconciliation.json", report), ("data/estate_registry.reconciled.json", registry)):
        path = args.root / relative
        if args.check:
            if load(path) != value:
                raise ValueError(f"{relative}: reconciliation output is not reproducible")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({key: value for key, value in report.items() if not isinstance(value, list)}, sort_keys=True))


if __name__ == "__main__":
    main()
