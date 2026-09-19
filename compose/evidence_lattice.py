#!/usr/bin/env python3
"""Evidence-completeness kernel for the SZL model and software estate.

The kernel deliberately treats source, artifact, evaluation, deployment,
runtime, provenance, and controller evidence as independent axes.  Evidence on
one axis never upgrades another axis.  A model listing is not trained weights;
green CI is not a deployment; HTTP 200 is not qualification; a digest is not a
signature.

The implementation is dependency-free so the same receipt can be recomputed in
GitHub Actions, on an operator workstation, or by an offline reviewer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import tempfile
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit

SNAPSHOT_SCHEMA = "szl.evidence-lattice-snapshot/v2"
RECEIPT_SCHEMA = "szl.evidence-lattice-receipt/v2"

KINDS = frozenset({"repository", "model", "dataset", "space", "kernel"})
DISPOSITIONS = frozenset(
    {
        "ACTIVE",
        "CANDIDATE",
        "RESEARCH_ONLY",
        "QUARANTINED",
        "DEPRECATED",
        "PLACEHOLDER",
        "HISTORICAL",
    }
)
NON_ADMISSIBLE_DISPOSITIONS = frozenset(
    {"RESEARCH_ONLY", "QUARANTINED", "DEPRECATED", "PLACEHOLDER", "HISTORICAL"}
)
LAYER_NAMES = frozenset(
    {
        "metadata",
        "source",
        "ci",
        "artifact",
        "evaluation",
        "deployment",
        "runtime",
        "provenance",
        "controller",
    }
)
LAYER_STATES = frozenset(
    {
        "PASS",
        "MEASURED",
        "FAIL",
        "BLOCKED",
        "UNKNOWN",
        "UNAVAILABLE",
        "NOT_APPLICABLE",
    }
)
PASS_STATES = frozenset({"PASS", "MEASURED"})
OBSERVATION_MODES = frozenset(
    {
        "CALLER_DECLARED",
        "DERIVED",
        "PROVIDER_OBSERVED",
        "DIRECT_OBSERVATION",
        "INDEPENDENT_WITNESS",
    }
)
QUALIFYING_OBSERVATIONS: dict[str, frozenset[str]] = {
    "metadata": frozenset(
        {"PROVIDER_OBSERVED", "DIRECT_OBSERVATION", "INDEPENDENT_WITNESS"}
    ),
    "source": frozenset(
        {"PROVIDER_OBSERVED", "DIRECT_OBSERVATION", "INDEPENDENT_WITNESS"}
    ),
    "ci": frozenset(
        {"PROVIDER_OBSERVED", "DIRECT_OBSERVATION", "INDEPENDENT_WITNESS"}
    ),
    "artifact": frozenset(
        {"PROVIDER_OBSERVED", "DIRECT_OBSERVATION", "INDEPENDENT_WITNESS"}
    ),
    "evaluation": frozenset({"DIRECT_OBSERVATION", "INDEPENDENT_WITNESS"}),
    "deployment": frozenset(
        {"PROVIDER_OBSERVED", "DIRECT_OBSERVATION", "INDEPENDENT_WITNESS"}
    ),
    # A provider stage is deployment evidence, not an application response.
    "runtime": frozenset({"DIRECT_OBSERVATION", "INDEPENDENT_WITNESS"}),
    "provenance": frozenset({"DIRECT_OBSERVATION", "INDEPENDENT_WITNESS"}),
    "controller": frozenset({"DIRECT_OBSERVATION", "INDEPENDENT_WITNESS"}),
}
GOALS = frozenset({"publish", "operate", "promote"})

# Each tuple is a conjunction.  No required layer can be inferred from another.
GOAL_REQUIREMENTS: dict[str, dict[str, tuple[str, ...]]] = {
    "publish": {
        "repository": ("source", "ci", "provenance", "controller"),
        "model": ("source", "artifact", "evaluation", "provenance", "controller"),
        "dataset": ("source", "artifact", "provenance", "controller"),
        "space": ("source", "deployment", "provenance", "controller"),
        "kernel": ("source", "artifact", "evaluation", "provenance", "controller"),
    },
    "operate": {
        "repository": (
            "source",
            "ci",
            "deployment",
            "runtime",
            "provenance",
            "controller",
        ),
        "model": (
            "source",
            "artifact",
            "evaluation",
            "deployment",
            "runtime",
            "provenance",
            "controller",
        ),
        "dataset": ("source", "artifact", "runtime", "provenance", "controller"),
        "space": ("source", "deployment", "runtime", "provenance", "controller"),
        "kernel": (
            "source",
            "artifact",
            "evaluation",
            "runtime",
            "provenance",
            "controller",
        ),
    },
    "promote": {
        "repository": ("source", "ci", "provenance", "controller"),
        "model": ("source", "artifact", "evaluation", "provenance", "controller"),
        "dataset": (
            "source",
            "artifact",
            "evaluation",
            "provenance",
            "controller",
        ),
        "space": (
            "source",
            "deployment",
            "runtime",
            "provenance",
            "controller",
        ),
        "kernel": ("source", "artifact", "evaluation", "provenance", "controller"),
    },
}

_HEX_REVISION = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ASSET_ID = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(?:hf|ghp|gho|ghs|ghu)_[A-Za-z0-9]{20,}\b"),
    re.compile(r"(?i)\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"(?i)\b(?:authorization\s*:\s*bearer|bearer)\s+[A-Za-z0-9._-]{16,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
)
_SNAPSHOT_KEYS = frozenset(
    {
        "schema",
        "generated_at",
        "observer",
        "max_evidence_age_seconds",
        "assets",
        "previous_receipt_sha256",
        "notes",
    }
)
_ASSET_KEYS = frozenset({"id", "kind", "revision", "disposition", "layers", "notes"})
_LAYER_KEYS = frozenset({"state", "subject_revision", "evidence", "note"})
_EVIDENCE_KEYS = frozenset(
    {
        "uri",
        "observation",
        "subject_revision",
        "observed_at",
        "observer",
        "sha256",
        "note",
    }
)
_MAX_JSON_BYTES = 32 * 1024 * 1024
_SENSITIVE_QUERY_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "authorization",
        "key",
        "password",
        "secret",
        "token",
    }
)


class EvidenceError(ValueError):
    """The snapshot or receipt violates the kernel contract."""


def _parse_utc_second(value: Any, path: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value
    ):
        raise EvidenceError(f"{path}: expected second-precision UTC Z time")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise EvidenceError(f"{path}: invalid UTC calendar time") from exc


def _reject_bool_number(value: Any, path: str) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise EvidenceError(f"{path}: non-finite numbers are forbidden")


def _walk_json(value: Any, path: str = "$") -> None:
    """Validate JSON-domain values and refuse likely credentials."""
    if value is None or isinstance(value, (bool, int)):
        return
    if isinstance(value, float):
        _reject_bool_number(value, path)
        return
    if isinstance(value, str):
        if "\x00" in value or "\r" in value:
            raise EvidenceError(f"{path}: control characters are forbidden")
        decoded = value
        for _ in range(3):
            for pattern in _SECRET_PATTERNS:
                if pattern.search(decoded):
                    raise EvidenceError(
                        f"{path}: credential-like material is forbidden"
                    )
            expanded = unquote(decoded)
            if expanded == decoded:
                break
            decoded = expanded
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _walk_json(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for index, (key, item) in enumerate(value.items()):
            if not isinstance(key, str):
                raise EvidenceError(f"{path}: object keys must be strings")
            # Scan keys as data, but never copy an untrusted key into an error
            # path where it could disclose credential-shaped material.
            _walk_json(key, f"{path}.<key:{index}>")
            _walk_json(item, f"{path}.<value:{index}>")
        return
    raise EvidenceError(f"{path}: value is outside the JSON domain")


def canonical_json(value: Any) -> bytes:
    """Return the sole byte representation used for every digest."""
    _walk_json(value)
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise EvidenceError(f"value is not canonical JSON: {exc}") from exc
    return encoded.encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _require_exact_keys(
    value: Mapping[str, Any], allowed: frozenset[str], required: frozenset[str], path: str
) -> None:
    unknown = set(value) - allowed
    missing = sorted(required - set(value))
    if unknown:
        raise EvidenceError(f"{path}: unknown key count: {len(unknown)}")
    if missing:
        raise EvidenceError(f"{path}: missing keys: {', '.join(missing)}")


def _validate_revision(value: Any, path: str, *, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise EvidenceError(f"{path}: immutable revision is required")
        return None
    if not isinstance(value, str) or not _HEX_REVISION.fullmatch(value):
        raise EvidenceError(f"{path}: expected lowercase 40- or 64-hex revision")
    return value


def _validate_evidence(value: Any, path: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise EvidenceError(f"{path}: evidence must be a list")
    result: list[dict[str, Any]] = []
    for index, row in enumerate(value):
        row_path = f"{path}[{index}]"
        if not isinstance(row, dict):
            raise EvidenceError(f"{row_path}: evidence row must be an object")
        _require_exact_keys(
            row,
            _EVIDENCE_KEYS,
            frozenset({"uri", "observation", "observed_at", "observer"}),
            row_path,
        )
        uri = row["uri"]
        if not isinstance(uri, str) or not uri or len(uri) > 2048:
            raise EvidenceError(f"{row_path}.uri: expected a non-empty bounded string")
        if any(ch in uri for ch in ("\n", "\t")):
            raise EvidenceError(f"{row_path}.uri: whitespace controls are forbidden")
        try:
            parsed = urlsplit(uri)
        except ValueError as exc:
            raise EvidenceError(f"{row_path}.uri: malformed URL") from exc
        if parsed.username is not None or parsed.password is not None:
            raise EvidenceError(f"{row_path}.uri: URL userinfo is forbidden")
        for key, item in parse_qsl(parsed.query, keep_blank_values=True):
            if key.strip().lower() in _SENSITIVE_QUERY_KEYS and item:
                raise EvidenceError(
                    f"{row_path}.uri: credential-bearing query parameter is forbidden"
                )
        observation = row["observation"]
        if not isinstance(observation, str) or observation not in OBSERVATION_MODES:
            raise EvidenceError(
                f"{row_path}.observation: unsupported mode {observation!r}"
            )
        subject_revision = _validate_revision(
            row.get("subject_revision"), f"{row_path}.subject_revision"
        )
        observed_at = row["observed_at"]
        _parse_utc_second(observed_at, f"{row_path}.observed_at")
        observer = row["observer"]
        if not isinstance(observer, str) or not observer or len(observer) > 200:
            raise EvidenceError(
                f"{row_path}.observer: expected a non-empty bounded string"
            )
        digest = row.get("sha256")
        if digest is not None and (
            not isinstance(digest, str) or not _SHA256.fullmatch(digest)
        ):
            raise EvidenceError(f"{row_path}.sha256: expected lowercase sha256")
        note = row.get("note")
        if note is not None and (not isinstance(note, str) or len(note) > 1000):
            raise EvidenceError(f"{row_path}.note: expected a bounded string")
        result.append(
            {
                "uri": uri,
                "observation": observation,
                "subject_revision": subject_revision,
                "observed_at": observed_at,
                "observer": observer,
                **({"sha256": digest} if digest is not None else {}),
                **({"note": note} if note is not None else {}),
            }
        )
    return sorted(
        result,
        key=lambda row: (
            row["uri"],
            row["observation"],
            row.get("subject_revision") or "",
            row["observed_at"],
            row["observer"],
            row.get("sha256") or "",
            row.get("note") or "",
        ),
    )


def _validate_layer(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvidenceError(f"{path}: layer must be an object")
    _require_exact_keys(value, _LAYER_KEYS, frozenset({"state", "evidence"}), path)
    state = value["state"]
    if not isinstance(state, str) or state not in LAYER_STATES:
        raise EvidenceError(f"{path}.state: unsupported state {state!r}")
    subject_revision = _validate_revision(
        value.get("subject_revision"), f"{path}.subject_revision"
    )
    evidence = _validate_evidence(value["evidence"], f"{path}.evidence")
    note = value.get("note")
    if note is not None and (not isinstance(note, str) or len(note) > 2000):
        raise EvidenceError(f"{path}.note: expected a bounded string")
    if state in PASS_STATES and not evidence:
        raise EvidenceError(f"{path}: {state} requires at least one evidence reference")
    return {
        "state": state,
        "subject_revision": subject_revision,
        "evidence": evidence,
        **({"note": note} if note is not None else {}),
    }


def _validate_asset(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvidenceError(f"{path}: asset must be an object")
    _require_exact_keys(
        value,
        _ASSET_KEYS,
        frozenset({"id", "kind", "revision", "disposition", "layers"}),
        path,
    )
    asset_id = value["id"]
    if not isinstance(asset_id, str) or not _ASSET_ID.fullmatch(asset_id):
        raise EvidenceError(f"{path}.id: expected namespace/name")
    kind = value["kind"]
    if not isinstance(kind, str) or kind not in KINDS:
        raise EvidenceError(f"{path}.kind: unsupported kind {kind!r}")
    revision = _validate_revision(value["revision"], f"{path}.revision")
    disposition = value["disposition"]
    if not isinstance(disposition, str) or disposition not in DISPOSITIONS:
        raise EvidenceError(
            f"{path}.disposition: unsupported disposition {disposition!r}"
        )
    layers = value["layers"]
    if not isinstance(layers, dict):
        raise EvidenceError(f"{path}.layers: expected an object")
    unknown_layers = sorted(set(layers) - LAYER_NAMES)
    if unknown_layers:
        raise EvidenceError(
            f"{path}.layers: unknown layers: {', '.join(unknown_layers)}"
        )
    validated_layers = {
        name: _validate_layer(layer, f"{path}.layers.{name}")
        for name, layer in layers.items()
    }
    notes = value.get("notes")
    if notes is not None and (not isinstance(notes, str) or len(notes) > 4000):
        raise EvidenceError(f"{path}.notes: expected a bounded string")
    return {
        "id": asset_id,
        "kind": kind,
        "revision": revision,
        "disposition": disposition,
        "layers": validated_layers,
        **({"notes": notes} if notes is not None else {}),
    }


def validate_snapshot(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvidenceError("snapshot: expected an object")
    _walk_json(value)
    _require_exact_keys(
        value,
        _SNAPSHOT_KEYS,
        frozenset(
            {
                "schema",
                "generated_at",
                "observer",
                "max_evidence_age_seconds",
                "assets",
            }
        ),
        "snapshot",
    )
    if value["schema"] != SNAPSHOT_SCHEMA:
        raise EvidenceError(f"snapshot.schema: expected {SNAPSHOT_SCHEMA}")
    generated_at = value["generated_at"]
    generated_time = _parse_utc_second(generated_at, "snapshot.generated_at")
    observer = value["observer"]
    if not isinstance(observer, str) or not observer or len(observer) > 200:
        raise EvidenceError("snapshot.observer: expected a non-empty bounded string")
    max_evidence_age_seconds = value["max_evidence_age_seconds"]
    if (
        isinstance(max_evidence_age_seconds, bool)
        or not isinstance(max_evidence_age_seconds, int)
        or not 1 <= max_evidence_age_seconds <= 604800
    ):
        raise EvidenceError(
            "snapshot.max_evidence_age_seconds: expected 1..604800"
        )
    assets_raw = value["assets"]
    if not isinstance(assets_raw, list):
        raise EvidenceError("snapshot.assets: expected a list")
    assets = [
        _validate_asset(asset, f"snapshot.assets[{index}]")
        for index, asset in enumerate(assets_raw)
    ]
    for asset in assets:
        for layer in asset["layers"].values():
            for evidence in layer["evidence"]:
                evidence_time = _parse_utc_second(
                    evidence["observed_at"], "snapshot evidence observed_at"
                )
                if evidence_time > generated_time:
                    raise EvidenceError(
                        "snapshot evidence observed_at cannot be after generated_at"
                    )
    # Providers can legitimately expose the same namespace/name under multiple
    # asset kinds (for example, a Hugging Face model and Space).  Identity is
    # therefore the pair (kind, id), never the display id alone.
    seen: set[tuple[str, str]] = set()
    duplicates: set[tuple[str, str]] = set()
    for asset in assets:
        identity = (asset["kind"], asset["id"])
        if identity in seen:
            duplicates.add(identity)
        seen.add(identity)
    if duplicates:
        rendered = ", ".join(
            f"{kind}:{asset_id}" for kind, asset_id in sorted(duplicates)
        )
        raise EvidenceError(
            f"snapshot.assets: duplicate ids within kind: {rendered}"
        )
    previous = value.get("previous_receipt_sha256")
    if previous is not None and (
        not isinstance(previous, str) or not _SHA256.fullmatch(previous)
    ):
        raise EvidenceError(
            "snapshot.previous_receipt_sha256: expected lowercase sha256"
        )
    notes = value.get("notes")
    if notes is not None and (not isinstance(notes, str) or len(notes) > 8000):
        raise EvidenceError("snapshot.notes: expected a bounded string")
    return {
        "schema": SNAPSHOT_SCHEMA,
        "generated_at": generated_at,
        "observer": observer,
        "max_evidence_age_seconds": max_evidence_age_seconds,
        "assets": sorted(assets, key=lambda asset: (asset["id"], asset["kind"])),
        **({"previous_receipt_sha256": previous} if previous is not None else {}),
        **({"notes": notes} if notes is not None else {}),
    }


def _selected_assets(
    snapshot: Mapping[str, Any], selection: Sequence[str] | None
) -> list[dict[str, Any]]:
    assets = list(snapshot["assets"])
    if selection is None:
        return assets
    if isinstance(selection, (str, bytes)):
        raise EvidenceError("selection: expected a sequence of asset ids")
    requested = list(selection)
    if not all(isinstance(item, str) and item for item in requested):
        raise EvidenceError("selection: every selector must be a non-empty string")
    if len(set(requested)) != len(requested):
        raise EvidenceError("selection: duplicate selectors are forbidden")

    by_typed = {f'{asset["kind"]}:{asset["id"]}': asset for asset in assets}
    by_id: dict[str, list[dict[str, Any]]] = {}
    for asset in assets:
        by_id.setdefault(asset["id"], []).append(asset)

    resolved: list[dict[str, Any]] = []
    unknown: list[str] = []
    for selector in requested:
        if selector in by_typed:
            resolved.append(by_typed[selector])
            continue
        matches = by_id.get(selector, [])
        if len(matches) == 1:
            resolved.append(matches[0])
            continue
        if len(matches) > 1:
            kinds = ", ".join(sorted(asset["kind"] for asset in matches))
            raise EvidenceError(
                f"selection: ambiguous asset id {selector!r}; use kind:id "
                f"(available kinds: {kinds})"
            )
        unknown.append(selector)
    if unknown:
        raise EvidenceError(f"selection: unknown asset ids: {', '.join(sorted(unknown))}")

    identities = [(asset["kind"], asset["id"]) for asset in resolved]
    if len(set(identities)) != len(identities):
        raise EvidenceError("selection: selectors resolve to the same asset")
    return sorted(resolved, key=lambda asset: (asset["id"], asset["kind"]))


def assess_asset(
    asset: Mapping[str, Any],
    goal: str,
    *,
    generated_time: datetime,
    max_evidence_age_seconds: int,
) -> dict[str, Any]:
    """Assess one already-validated asset without evidence transitivity."""
    if not isinstance(goal, str) or goal not in GOALS:
        raise EvidenceError(f"goal: unsupported goal {goal!r}")
    kind = asset["kind"]
    required_layers = GOAL_REQUIREMENTS[goal][kind]
    blockers: list[dict[str, Any]] = []
    revision = asset["revision"]
    disposition = asset["disposition"]

    if disposition in NON_ADMISSIBLE_DISPOSITIONS:
        blockers.append(
            {
                "code": "DISPOSITION_BLOCKS_ADMISSION",
                "disposition": disposition,
            }
        )
    if revision is None:
        blockers.append({"code": "IMMUTABLE_REVISION_MISSING"})

    layers = asset["layers"]
    layer_states: dict[str, str] = {}
    for layer_name in required_layers:
        layer = layers.get(layer_name)
        if layer is None:
            layer_states[layer_name] = "UNKNOWN"
            blockers.append(
                {"code": "REQUIRED_LAYER_MISSING", "layer": layer_name}
            )
            continue
        state = layer["state"]
        layer_states[layer_name] = state
        if state not in PASS_STATES:
            blockers.append(
                {
                    "code": "REQUIRED_LAYER_NOT_PASSING",
                    "layer": layer_name,
                    "state": state,
                }
            )
            continue
        subject_revision = layer.get("subject_revision")
        if revision is None or subject_revision != revision:
            blockers.append(
                {
                    "code": "LAYER_NOT_BOUND_TO_ASSET_REVISION",
                    "layer": layer_name,
                    "asset_revision": revision,
                    "subject_revision": subject_revision,
                }
            )
        qualifying = QUALIFYING_OBSERVATIONS[layer_name]
        evidence_rows = layer.get("evidence", [])
        observed_modes = sorted({row["observation"] for row in evidence_rows})
        qualifying_rows = [
            row for row in evidence_rows if row["observation"] in qualifying
        ]
        if not qualifying_rows:
            blockers.append(
                {
                    "code": "NO_QUALIFYING_OBSERVATION",
                    "layer": layer_name,
                    "observed_modes": observed_modes,
                    "qualifying_modes": sorted(qualifying),
                }
            )
        elif revision is None or not any(
            row.get("subject_revision") == revision for row in qualifying_rows
        ):
            blockers.append(
                {
                    "code": "NO_REVISION_BOUND_QUALIFYING_EVIDENCE",
                    "layer": layer_name,
                    "asset_revision": revision,
                    "evidence_revisions": sorted(
                        {
                            row.get("subject_revision")
                            for row in qualifying_rows
                            if row.get("subject_revision") is not None
                        }
                    ),
                }
            )
        else:
            revision_bound_rows = [
                row
                for row in qualifying_rows
                if row.get("subject_revision") == revision
            ]
            fresh_rows = [
                row
                for row in revision_bound_rows
                if (
                    generated_time
                    - _parse_utc_second(row["observed_at"], "evidence.observed_at")
                ).total_seconds()
                <= max_evidence_age_seconds
            ]
            if not fresh_rows:
                blockers.append(
                    {
                        "code": "NO_FRESH_REVISION_BOUND_QUALIFYING_EVIDENCE",
                        "layer": layer_name,
                        "max_evidence_age_seconds": max_evidence_age_seconds,
                        "observed_at": sorted(
                            row["observed_at"] for row in revision_bound_rows
                        ),
                    }
                )

    admitted = not blockers
    return {
        "id": asset["id"],
        "kind": kind,
        "selector": f'{kind}:{asset["id"]}',
        "goal": goal,
        "disposition": disposition,
        "revision": revision,
        "required_layers": list(required_layers),
        "layer_states": layer_states,
        "evidence_complete": admitted,
        "authorized": False,
        "trust": "UNVERIFIED_INPUT_ASSERTIONS",
        "decision": "EVIDENCE_COMPLETE_UNTRUSTED" if admitted else "BLOCK",
        "blockers": blockers,
    }


def assess_snapshot(
    snapshot_value: Any,
    goal: str,
    selection: Sequence[str] | None = None,
) -> dict[str, Any]:
    snapshot = validate_snapshot(snapshot_value)
    selected = _selected_assets(snapshot, selection)
    generated_time = _parse_utc_second(
        snapshot["generated_at"], "snapshot.generated_at"
    )
    decisions = [
        assess_asset(
            asset,
            goal,
            generated_time=generated_time,
            max_evidence_age_seconds=snapshot["max_evidence_age_seconds"],
        )
        for asset in selected
    ]
    admitted = sum(1 for decision in decisions if decision["evidence_complete"])
    return {
        "schema": "szl.evidence-lattice-assessment/v2",
        "authorized": False,
        "trust": "UNVERIFIED_INPUT_ASSERTIONS",
        "snapshot_sha256": sha256_json(snapshot),
        "goal": goal,
        "asset_count": len(decisions),
        "complete_count": admitted,
        "blocked_count": len(decisions) - admitted,
        "all_evidence_complete": bool(decisions) and admitted == len(decisions),
        "decisions": decisions,
    }


def make_receipt(
    snapshot_value: Any,
    goal: str,
    selection: Sequence[str] | None = None,
    *,
    previous_receipt_sha256: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (assessment, hash-only receipt) for an exact snapshot."""
    snapshot = validate_snapshot(snapshot_value)
    snapshot_previous = snapshot.get("previous_receipt_sha256")
    if (
        previous_receipt_sha256 is not None
        and snapshot_previous is not None
        and previous_receipt_sha256 != snapshot_previous
    ):
        raise EvidenceError(
            "previous_receipt_sha256: explicit value conflicts with snapshot chain"
        )
    if previous_receipt_sha256 is None:
        previous_receipt_sha256 = snapshot_previous
    if previous_receipt_sha256 is not None and (
        not isinstance(previous_receipt_sha256, str)
        or not _SHA256.fullmatch(previous_receipt_sha256)
    ):
        raise EvidenceError("previous_receipt_sha256: expected lowercase sha256")
    assessment = assess_snapshot(snapshot, goal, selection)
    body = {
        "schema": RECEIPT_SCHEMA,
        "integrity": "HASH_ONLY_UNSIGNED",
        "generated_at": snapshot["generated_at"],
        "observer": snapshot["observer"],
        "max_evidence_age_seconds": snapshot["max_evidence_age_seconds"],
        "snapshot_sha256": assessment["snapshot_sha256"],
        "assessment_sha256": sha256_json(assessment),
        "goal": goal,
        "asset_count": assessment["asset_count"],
        "complete_count": assessment["complete_count"],
        "blocked_count": assessment["blocked_count"],
        # Typed selectors make a subset receipt self-describing and avoid
        # ambiguity when providers reuse namespace/name across asset kinds.
        "selectors": [decision["selector"] for decision in assessment["decisions"]],
        "previous_receipt_sha256": previous_receipt_sha256,
        "boundary": (
            "Digest proves deterministic byte integrity only; it does not prove "
            "correctness, independence, identity, qualification, or authorization."
        ),
    }
    receipt = {**body, "receipt_sha256": sha256_json(body)}
    return assessment, receipt


def verify_receipt(
    snapshot_value: Any,
    receipt_value: Any,
    selection: Sequence[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(receipt_value, dict):
        raise EvidenceError("receipt: expected an object")
    _walk_json(receipt_value)
    required = frozenset(
        {
            "schema",
            "integrity",
            "generated_at",
            "observer",
            "max_evidence_age_seconds",
            "snapshot_sha256",
            "assessment_sha256",
            "goal",
            "asset_count",
            "complete_count",
            "blocked_count",
            "selectors",
            "previous_receipt_sha256",
            "boundary",
            "receipt_sha256",
        }
    )
    _require_exact_keys(receipt_value, required, required, "receipt")
    if receipt_value["schema"] != RECEIPT_SCHEMA:
        raise EvidenceError(f"receipt.schema: expected {RECEIPT_SCHEMA}")
    if receipt_value["integrity"] != "HASH_ONLY_UNSIGNED":
        raise EvidenceError("receipt.integrity: unsupported integrity tier")
    goal = receipt_value["goal"]
    if not isinstance(goal, str) or goal not in GOALS:
        raise EvidenceError(f"receipt.goal: unsupported goal {goal!r}")
    previous = receipt_value["previous_receipt_sha256"]
    if previous is not None and (
        not isinstance(previous, str) or not _SHA256.fullmatch(previous)
    ):
        raise EvidenceError("receipt.previous_receipt_sha256: expected lowercase sha256")
    for name in ("snapshot_sha256", "assessment_sha256", "receipt_sha256"):
        digest = receipt_value[name]
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise EvidenceError(f"receipt.{name}: expected lowercase sha256")
    for name in ("asset_count", "complete_count", "blocked_count"):
        count = receipt_value[name]
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise EvidenceError(f"receipt.{name}: expected a non-negative integer")
    age_limit = receipt_value["max_evidence_age_seconds"]
    if isinstance(age_limit, bool) or not isinstance(age_limit, int) or not 1 <= age_limit <= 604800:
        raise EvidenceError("receipt.max_evidence_age_seconds: expected integer in 1..604800")
    receipt_selectors = receipt_value["selectors"]
    if (
        not isinstance(receipt_selectors, list)
        or not all(isinstance(item, str) and item for item in receipt_selectors)
        or len(set(receipt_selectors)) != len(receipt_selectors)
    ):
        raise EvidenceError("receipt.selectors: expected unique typed selector strings")
    verification_selection = selection if selection is not None else receipt_selectors
    assessment, expected = make_receipt(
        snapshot_value,
        goal,
        verification_selection,
        previous_receipt_sha256=previous,
    )
    mismatches = sorted(
        key for key in required if receipt_value.get(key) != expected.get(key)
    )
    # Python numeric equality alone is not canonical JSON integrity (1 == 1.0).
    # Check the actual supplied body, not only a recomputed expected receipt.
    supplied_body = dict(receipt_value)
    supplied_digest = supplied_body.pop("receipt_sha256")
    if sha256_json(supplied_body) != supplied_digest:
        mismatches = sorted(set(mismatches) | {"receipt_sha256"})
    return {
        "valid": not mismatches,
        "mismatches": mismatches,
        "expected_receipt_sha256": expected["receipt_sha256"],
        "actual_receipt_sha256": receipt_value.get("receipt_sha256"),
        "assessment": assessment,
    }


def _load_json(path: Path) -> Any:
    if path.is_symlink():
        raise EvidenceError(f"{path}: symlink inputs are forbidden")
    if not path.is_file():
        raise EvidenceError(f"{path}: expected a regular file")
    if path.stat().st_size > _MAX_JSON_BYTES:
        raise EvidenceError(f"{path}: exceeds {_MAX_JSON_BYTES} bytes")

    def no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise EvidenceError("JSON object contains a duplicate key")
            result[key] = value
        return result

    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=no_duplicate_keys,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"{path}: cannot load JSON: {exc}") from exc


def _write_json_atomic(path: Path, value: Any) -> None:
    requested = path.absolute()
    if requested.exists() or requested.is_symlink():
        raise EvidenceError(f"{requested}: refusing to overwrite an existing receipt")
    parent = requested.parent.resolve()
    if not parent.is_dir():
        raise EvidenceError(f"{parent}: output parent does not exist")
    path = parent / requested.name
    payload = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=parent)
    temp = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        # Link creation is atomic and refuses an existing destination. A
        # concurrent writer cannot be overwritten after the preflight check.
        os.link(temp, path)
    except OSError as exc:
        raise EvidenceError("cannot publish receipt without overwriting") from exc
    finally:
        if temp.exists():
            temp.unlink()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--goal", choices=sorted(GOALS), default="promote")
    parser.add_argument(
        "--select",
        action="append",
        default=None,
        help="namespace/name when unique, otherwise kind:namespace/name; repeatable",
    )
    parser.add_argument("--previous-receipt-hash")
    parser.add_argument("--receipt-out", type=Path)
    parser.add_argument("--verify-receipt", type=Path)
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="exit 2 unless evidence is complete and snapshot is current; never authorizes release",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        snapshot = _load_json(args.snapshot)
        if args.verify_receipt is not None:
            if args.require_complete or args.receipt_out is not None or args.previous_receipt_hash:
                raise EvidenceError(
                    "historical receipt verification cannot be combined with current "
                    "completeness checks, receipt output, or a new chain pointer"
                )
            verification = verify_receipt(
                snapshot, _load_json(args.verify_receipt), args.select
            )
            print(json.dumps(verification, indent=2, sort_keys=True))
            return 0 if verification["valid"] else 3
        assessment, receipt = make_receipt(
            snapshot,
            args.goal,
            args.select,
            previous_receipt_sha256=args.previous_receipt_hash,
        )
        result = {"assessment": assessment, "receipt": receipt}
        current_complete = False
        if args.require_complete:
            now = datetime.now(timezone.utc).replace(microsecond=0)
            generated = _parse_utc_second(snapshot["generated_at"], "generated_at")
            age = (now - generated).total_seconds()
            snapshot_fresh = 0 <= age <= snapshot["max_evidence_age_seconds"]
            # A fresh snapshot can contain evidence near expiry. Reassess each
            # qualifying observation at the current clock, without changing the
            # deterministic historical receipt or its original snapshot hash.
            if snapshot_fresh:
                current_snapshot = dict(snapshot)
                current_snapshot["generated_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
                current_complete = assess_snapshot(
                    current_snapshot, args.goal, args.select
                )["all_evidence_complete"]
            result["current_check"] = {
                "checked_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "snapshot_fresh": snapshot_fresh,
                "all_evidence_complete": current_complete,
                "authorized": False,
            }
        if args.receipt_out is not None:
            _write_json_atomic(args.receipt_out, receipt)
        print(json.dumps(result, indent=2, sort_keys=True))
        if args.require_complete and not current_complete:
            return 2
        return 0
    except EvidenceError as exc:
        print(json.dumps({"error": str(exc), "status": "BLOCKED"}), file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
