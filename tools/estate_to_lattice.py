#!/usr/bin/env python3
"""Convert read-only GitHub/Hugging Face inventories into a public lattice snapshot.

The converter is intentionally conservative.  It records what provider APIs
and direct HTTP witnesses actually exposed; it does not turn file names,
downloads, tags, signatures, or a RUNNING stage into model qualification.
Private asset names are excluded from the public snapshot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from compose.evidence_lattice import (  # noqa: E402
    SNAPSHOT_SCHEMA,
    _load_json,
    _write_json_atomic,
    validate_snapshot,
)

WEIGHT_SUFFIXES = (
    ".safetensors",
    ".gguf",
    ".bin",
    ".pt",
    ".pth",
    ".ckpt",
    ".npz",
    ".onnx",
)
FAIL_STAGES = frozenset({"RUNTIME_ERROR", "BUILD_ERROR", "CONFIG_ERROR", "ERROR"})
BLOCKED_STAGES = frozenset({"BUILDING", "STARTING", "APP_STARTING", "RUNNING_BUILDING"})
UNAVAILABLE_STAGES = frozenset({"PAUSED", "SLEEPING", "STOPPED"})
MAX_INPUT_BYTES = 64 * 1024 * 1024


def _affirmatively_public(row: dict[str, Any]) -> bool:
    """Export only rows whose provider inventory explicitly says public."""
    return row.get("private") is False


def _public_http_uri(value: Any) -> str | None:
    """Return a query-free public HTTP(S) URI without credentials or fragments."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if port is not None:
        host = f"{host}:{port}"
    # The witness performed a root request. Publish only the origin; redirect
    # paths can contain transient or credential-like material.
    return urlunsplit((parsed.scheme, host, "/", "", ""))


def _load(path: Path) -> Any:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{path}: expected a regular, non-symlink file")
    if path.stat().st_size > MAX_INPUT_BYTES:
        raise ValueError(f"{path}: input exceeds {MAX_INPUT_BYTES} bytes")
    return _load_json(path)


def _capture_time(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("capture time must include a timezone")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("capture time must include a timezone")
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _record_digest(row: dict[str, Any]) -> str:
    raw = json.dumps(row, sort_keys=True, ensure_ascii=False, allow_nan=False,
                     separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _revision(row: dict[str, Any]) -> str | None:
    value = row.get("sha")
    if isinstance(value, str) and len(value) in {40, 64}:
        return value.lower()
    return None


def _siblings(row: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in row.get("siblings") or []:
        if isinstance(item, dict) and isinstance(item.get("rfilename"), str):
            names.append(item["rfilename"])
    return names


def _explicit_disposition(row: dict[str, Any], default: str) -> str:
    tags = {str(tag).strip().lower() for tag in (row.get("tags") or [])}
    card = row.get("card_data") if isinstance(row.get("card_data"), dict) else {}
    if row.get("disabled") is True:
        return "QUARANTINED"
    if "deprecated" in tags or card.get("deprecated") is True:
        return "DEPRECATED"
    if (
        "quarantined" in tags
        or "quarantine" in tags
        or card.get("quarantined") is True
    ):
        return "QUARANTINED"
    if (
        "research-only" in tags
        or "proposal-only" in tags
        or card.get("publication_eligible") is False
    ):
        return "RESEARCH_ONLY"
    return default


def _provider_layer(
    state: str,
    revision: str | None,
    uri: str,
    note: str | None = None,
) -> dict[str, Any]:
    evidence = [{"uri": uri, "observation": "PROVIDER_OBSERVED"}]
    evidence[0]["subject_revision"] = revision
    if note:
        evidence[0]["note"] = note
    return {
        "state": state,
        "subject_revision": revision,
        "evidence": evidence,
    }


def _direct_layer(
    state: str,
    layer_revision: str | None,
    uri: str,
    note: str | None = None,
    *,
    evidence_revision: str | None = None,
) -> dict[str, Any]:
    evidence = [
        {
            "uri": uri,
            "observation": "DIRECT_OBSERVATION",
            "subject_revision": evidence_revision,
        }
    ]
    if note:
        evidence[0]["note"] = note
    return {
        "state": state,
        "subject_revision": layer_revision,
        "evidence": evidence,
    }


def _model_assets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for row in rows:
        if not _affirmatively_public(row):
            continue
        asset_id = row.get("id")
        if not isinstance(asset_id, str):
            continue
        revision = _revision(row)
        tags = {str(tag).strip().lower() for tag in (row.get("tags") or [])}
        kind = "kernel" if "kernel" in tags or row.get("library_name") == "kernels" else "model"
        layers: dict[str, Any] = {
            "metadata": _provider_layer(
                "MEASURED",
                revision,
                f"https://huggingface.co/{asset_id}",
                "Hub repository metadata only; not qualification.",
            )
        }
        weights = sorted(
            name for name in _siblings(row) if name.lower().endswith(WEIGHT_SUFFIXES)
        )
        if revision and weights:
            layers["artifact"] = _provider_layer(
                "UNKNOWN",
                revision,
                f"https://huggingface.co/{asset_id}/tree/{revision}",
                f"Observed {len(weights)} weight-like file name(s), but no byte digest or manifest; artifact identity and quality are not inferred.",
            )
        assets.append(
            {
                "id": asset_id,
                "kind": kind,
                "revision": revision,
                "disposition": _explicit_disposition(row, "CANDIDATE"),
                "layers": layers,
            }
        )
    return assets


def _dataset_assets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for row in rows:
        if not _affirmatively_public(row):
            continue
        asset_id = row.get("id")
        if not isinstance(asset_id, str):
            continue
        revision = _revision(row)
        layers: dict[str, Any] = {
            "metadata": _provider_layer(
                "MEASURED",
                revision,
                f"https://huggingface.co/datasets/{asset_id}",
                "Hub dataset metadata only.",
            )
        }
        data_files = [
            name
            for name in _siblings(row)
            if name not in {".gitattributes", "README.md"} and not name.endswith("/")
        ]
        if revision and data_files:
            layers["artifact"] = _provider_layer(
                "UNKNOWN",
                revision,
                f"https://huggingface.co/datasets/{asset_id}/tree/{revision}",
                f"Observed {len(data_files)} non-card file name(s), but no byte digest or manifest; artifact identity and data quality are not inferred.",
            )
        assets.append(
            {
                "id": asset_id,
                "kind": "dataset",
                "revision": revision,
                "disposition": _explicit_disposition(row, "ACTIVE"),
                "layers": layers,
            }
        )
    return assets


def _deployment_state(stage: str | None) -> str:
    if stage == "RUNNING":
        return "MEASURED"
    if stage in FAIL_STAGES:
        return "FAIL"
    if stage in BLOCKED_STAGES:
        return "BLOCKED"
    if stage in UNAVAILABLE_STAGES:
        return "UNAVAILABLE"
    return "UNKNOWN"


def _space_assets(
    rows: list[dict[str, Any]],
    witnesses: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for row in rows:
        if not _affirmatively_public(row):
            continue
        asset_id = row.get("id")
        if not isinstance(asset_id, str):
            continue
        revision = _revision(row)
        runtime = row.get("runtime") if isinstance(row.get("runtime"), dict) else {}
        stage = runtime.get("stage") if isinstance(runtime.get("stage"), str) else None
        raw_runtime = (
            runtime.get("raw") if isinstance(runtime.get("raw"), dict) else {}
        )
        deployed_revision = _revision({"sha": raw_runtime.get("sha")})
        deployment_state = _deployment_state(stage)
        if deployed_revision is None:
            deployment_state = "UNKNOWN"
        elif revision is None or deployed_revision != revision:
            deployment_state = "FAIL"
        layers: dict[str, Any] = {
            "metadata": _provider_layer(
                "MEASURED",
                revision,
                f"https://huggingface.co/spaces/{asset_id}",
                "Hub Space metadata only.",
            ),
            "deployment": _provider_layer(
                deployment_state,
                deployed_revision,
                f"https://huggingface.co/api/spaces/{asset_id}",
                (
                    f"Provider stage observed as {stage or 'UNKNOWN'}; "
                    f"deployed_revision_matches_repo={str(deployed_revision == revision and revision is not None).lower()}; "
                    "runtime health is separate."
                ),
            ),
        }
        witness = witnesses.get(asset_id)
        if witness is not None:
            witness_revision = witness.get("sha")
            status = witness.get("http_status")
            matches = revision is not None and witness_revision == revision
            passed = isinstance(status, int) and 200 <= status < 400 and matches
            host = _public_http_uri(witness.get("final_uri")) or _public_http_uri(
                witness.get("host")
            )
            if host is not None:
                layers["runtime"] = _direct_layer(
                    "MEASURED" if passed else "FAIL",
                    None,
                    host,
                    (
                        f"Direct HTTP status {status}; revision_match={str(matches).lower()}. "
                        "The root HTTP response did not attest a revision; reachability "
                        "is not revision-bound runtime or product qualification."
                    ),
                    evidence_revision=None,
                )
        assets.append(
            {
                "id": asset_id,
                "kind": "space",
                "revision": revision,
                "disposition": _explicit_disposition(row, "ACTIVE"),
                "layers": layers,
            }
        )
    return assets


def _github_assets(audit: dict[str, Any]) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for row in audit.get("repositories") or []:
        if not isinstance(row, dict) or not _affirmatively_public(row):
            continue
        asset_id = row.get("full_name")
        if not isinstance(asset_id, str):
            continue
        head = row.get("default_branch_head")
        target = head.get("target") if isinstance(head, dict) else None
        revision = target.get("oid") if isinstance(target, dict) else None
        if not isinstance(revision, str) or len(revision) not in {40, 64}:
            revision = None
        layers: dict[str, Any] = {
            "metadata": _provider_layer(
                "MEASURED",
                revision,
                f"https://github.com/{asset_id}",
                "GitHub repository metadata only.",
            )
        }
        if revision is not None:
            signature = target.get("signature") if isinstance(target, dict) else None
            signature_state = (
                signature.get("state") if isinstance(signature, dict) else "UNAVAILABLE"
            )
            layers["source"] = _provider_layer(
                "MEASURED",
                revision,
                f"https://github.com/{asset_id}/commit/{revision}",
                f"Default-branch source observed; signature_state={signature_state}. Signature is not provenance qualification.",
            )
            rollup = (
                target.get("statusCheckRollup") if isinstance(target, dict) else None
            )
            rollup_state = (
                rollup.get("state") if isinstance(rollup, dict) else None
            )
            ci_state = {
                "SUCCESS": "PASS",
                "FAILURE": "FAIL",
                "ERROR": "FAIL",
                "PENDING": "BLOCKED",
                "EXPECTED": "BLOCKED",
            }.get(rollup_state, "UNKNOWN")
            if rollup_state is not None:
                layers["ci"] = _provider_layer(
                    ci_state,
                    revision,
                    f"https://github.com/{asset_id}/commit/{revision}/checks",
                    f"GitHub status rollup observed as {rollup_state}.",
                )
        assets.append(
            {
                "id": asset_id,
                "kind": "repository",
                "revision": revision,
                "disposition": "HISTORICAL" if row.get("archived") is True else "ACTIVE",
                "layers": layers,
            }
        )
    return assets


def build_snapshot(
    *,
    models: list[dict[str, Any]],
    datasets: list[dict[str, Any]],
    spaces: list[dict[str, Any]],
    github: dict[str, Any],
    space_witness: list[dict[str, Any]],
    observed_at: str,
    hf_observed_at: str,
    max_evidence_age_seconds: int = 86400,
) -> dict[str, Any]:
    named_inputs = {
        "models": models,
        "datasets": datasets,
        "spaces": spaces,
        "space_witness": space_witness,
    }
    for name, rows in named_inputs.items():
        if not isinstance(rows, list) or not all(
            isinstance(row, dict) for row in rows
        ):
            raise ValueError(f"{name}: expected a list of objects")
    if not isinstance(github, dict):
        raise ValueError("github: expected an object")

    witness_by_id: dict[str, dict[str, Any]] = {}
    for row in space_witness:
        witness_id = row.get("id")
        if not _affirmatively_public(row) or not isinstance(witness_id, str):
            continue
        if witness_id in witness_by_id:
            raise ValueError(f"space_witness: duplicate id {witness_id}")
        witness_by_id[witness_id] = row
    assets = (
        _model_assets(models)
        + _dataset_assets(datasets)
        + _space_assets(spaces, witness_by_id)
        + _github_assets(github)
    )
    hf_time = _capture_time(hf_observed_at)
    github_time = _capture_time(github["captured_at_utc"])
    source_rows: dict[tuple[str, str], dict[str, Any]] = {}
    for kind, rows in (("model", models), ("dataset", datasets), ("space", spaces)):
        for row in rows:
            if _affirmatively_public(row) and isinstance(row.get("id"), str):
                source_rows[(kind, row["id"])] = row
    for row in github.get("repositories", []):
        if _affirmatively_public(row) and isinstance(row.get("full_name"), str):
            source_rows[("repository", row["full_name"])] = row
    for asset in assets:
        kind = "model" if asset["kind"] == "kernel" else asset["kind"]
        record = source_rows[(kind, asset["id"])]
        for name, layer in asset["layers"].items():
            witness = witness_by_id.get(asset["id"]) if name == "runtime" else None
            captured = (
                _capture_time(witness["observed_at"]) if witness is not None
                else github_time if kind == "repository" else hf_time
            )
            if witness is None and kind != "repository":
                field = (
                    "audit_live_runtime_observed_at" if name == "deployment"
                    else "audit_observed_at"
                )
                if record.get(field) is not None:
                    captured = _capture_time(record[field])
            digest = _record_digest(witness if witness is not None else record)
            for evidence in layer["evidence"]:
                evidence["observed_at"] = captured
                evidence["observer"] = (
                    "direct-http-audit" if witness is not None
                    else "gh-provider-audit" if kind == "repository"
                    else "hf-cli-provider-audit"
                )
                evidence["sha256"] = digest
    return validate_snapshot(
        {
            "schema": SNAPSHOT_SCHEMA,
            "generated_at": observed_at,
            "observer": "szl-hf-frontier/tools/estate_to_lattice.py",
            "max_evidence_age_seconds": max_evidence_age_seconds,
            "assets": assets,
            "notes": (
                "Public-only read snapshot. Private asset names are excluded. "
                "Provider metadata and direct HTTP reachability are observations, "
                "not training, quality, deployment authorization, or readiness."
            ),
        }
    )


def _write_new(path: Path, value: Any) -> None:
    # Use the receipt publisher's atomic no-overwrite guarantee for snapshots too.
    _write_json_atomic(path, value)


def _utc_second() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--datasets", type=Path, required=True)
    parser.add_argument("--spaces", type=Path, required=True)
    parser.add_argument("--github", type=Path, required=True)
    parser.add_argument("--space-witness", type=Path, required=True)
    parser.add_argument("--generated-at", default=_utc_second())
    parser.add_argument("--hf-observed-at", required=True,
                        help="Actual HF capture time, never the conversion time")
    parser.add_argument("--max-evidence-age-seconds", type=int, default=86400)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    snapshot = build_snapshot(
        models=_load(args.models),
        datasets=_load(args.datasets),
        spaces=_load(args.spaces),
        github=_load(args.github),
        space_witness=_load(args.space_witness),
        observed_at=args.generated_at,
        hf_observed_at=args.hf_observed_at,
        max_evidence_age_seconds=args.max_evidence_age_seconds,
    )
    _write_new(args.out, snapshot)
    counts: dict[str, int] = {}
    for asset in snapshot["assets"]:
        counts[asset["kind"]] = counts.get(asset["kind"], 0) + 1
    print(
        json.dumps(
            {
                "output": str(args.out.resolve()),
                "asset_count": len(snapshot["assets"]),
                "counts": counts,
                "private_names_published": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
