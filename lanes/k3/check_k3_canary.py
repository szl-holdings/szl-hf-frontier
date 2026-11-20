"""Fail-closed validator for K3 non-publishing canary evidence.

Schema szl.k3-canary/v1. Admits only ordered complete marker sets
with heartbeat cadence <= 70s and a terminal DONE (complete
schema) or FAILED.json (valid failure phase). Every other evidence
set raises ValidationError. The canary itself stays DISABLED BY
DEFAULT; execution authority lives in STATUS.json, not here.
"""

import hashlib
import json

SCHEMA = "szl.k3-canary/v1"
CADENCE_MAX = 70

MARKERS = (
    "ENTRY_STARTED",
    "ENTRY_BOOT",
    "ENV_VERIFIED",
    "DATASET_BOUND",
    "KERNELS_READY",
    "TRAIN_LOOP_ENTERED",
    "CHECKPOINT_WRITTEN",
    "CHECKPOINT_VERIFIED",
)

FAIL_PHASES = (
    "ENTRY",
    "ENV",
    "DATASET",
    "KERNELS",
    "TRAIN_LOOP",
    "CHECKPOINT",
    "UPLOAD",
)

DONE_FIELDS = (
    "run_id",
    "image_digest_sha256",
    "config_hash",
    "metrics_hash",
    "marker_log_hash",
)


class ValidationError(Exception):
    """Fail-closed evidence rejection."""


def validate_json(text):
    """Parse JSON; any parse failure is a rejection."""
    try:
        return json.loads(text)
    except ValueError as exc:
        raise ValidationError("malformed json: %s" % exc)


def _require(condition, message):
    if not condition:
        raise ValidationError(message)


def validate_marker_log(records):
    """Admit only the exact ordered marker sequence, fail closed."""
    _require(isinstance(records, list), "marker log must be a list")
    _require(len(records) > 0, "empty marker log rejected (fail closed)")
    names = []
    previous_ts = None
    for record in records:
        _require(isinstance(record, dict), "marker record must be object")
        name = record.get("marker")
        _require(isinstance(name, str), "marker name must be string")
        _require(name in MARKERS, "unknown marker: %r" % name)
        ts = record.get("ts")
        _require(isinstance(ts, (int, float)), "marker ts must be numeric")
        _require(not isinstance(ts, bool), "marker ts must be numeric")
        if previous_ts is not None:
            _require(ts > previous_ts, "marker ts must strictly increase")
        previous_ts = ts
        names.append(name)
    _require(tuple(names) == MARKERS, "markers must match ordered set")
    return names


def validate_heartbeats(records, cadence_max=CADENCE_MAX):
    """Consecutive heartbeat gaps must stay within cadence_max."""
    _require(isinstance(records, list), "heartbeats must be a list")
    _require(len(records) > 0, "heartbeat log required")
    previous_ts = None
    for record in records:
        _require(isinstance(record, dict), "heartbeat record must be object")
        ts = record.get("ts")
        _require(isinstance(ts, (int, float)), "heartbeat ts must numeric")
        _require(not isinstance(ts, bool), "heartbeat ts must be numeric")
        if previous_ts is not None:
            _require(ts - previous_ts <= cadence_max,
                     "heartbeat gap exceeds cadence bound")
        previous_ts = ts
    return len(records)


def validate_done(done):
    """DONE must carry the complete schema with a sha256 digest."""
    _require(isinstance(done, dict), "DONE must be an object")
    for field in DONE_FIELDS:
        _require(field in done, "DONE missing field: %s" % field)
    run_id = done["run_id"]
    _require(isinstance(run_id, str) and run_id, "run_id must be nonempty")
    digest = done["image_digest_sha256"]
    _require(isinstance(digest, str), "digest must be a string")
    _require(len(digest) == 64, "digest must be 64 hex chars")
    _require(all(c in "0123456789abcdef" for c in digest),
             "digest must be lowercase hex")
    for field in ("config_hash", "metrics_hash", "marker_log_hash"):
        value = done[field]
        _require(isinstance(value, str) and value,
                 "%s must be nonempty string" % field)


def validate_done_against_markers(done, records):
    """marker_log_hash must equal sha256 of canonical marker json."""
    canonical = json.dumps(records, sort_keys=True,
                           separators=(",", ":"))
    computed = hashlib.sha256(canonical.encode("ascii")).hexdigest()
    _require(done["marker_log_hash"] == computed,
             "marker log hash mismatch")


def validate_failed(failed):
    """FAILED must carry a valid failure phase."""
    _require(isinstance(failed, dict), "FAILED must be an object")
    phase = failed.get("phase")
    _require(phase in FAIL_PHASES, "invalid failure phase: %r" % phase)


def validate_zero_public_writes(proof):
    """Before/after snapshots equal and token denial confirmed."""
    _require(isinstance(proof, dict), "zero-write proof must be object")
    _require(proof.get("public_before") == proof.get("public_after"),
             "public snapshot drifted")
    _require(proof.get("token_denial_test") is True,
             "token denial test not satisfied")


def verify_zero_mutations(actions):
    """Reject any non-read action in a mutation-free zone."""
    _require(isinstance(actions, list), "actions must be a list")
    for action in actions:
        _require(isinstance(action, dict), "action must be an object")
        _require(action.get("method") in ("GET", "HEAD"),
                 "non-read action rejected: %r" % action.get("method"))


def admit_evidence(evidence):
    """Top-level verdict. Raises ValidationError on any defect."""
    _require(isinstance(evidence, dict), "evidence must be an object")
    _require(evidence.get("schema") == SCHEMA, "wrong schema")
    records = evidence.get("markers")
    validate_marker_log(records)
    validate_heartbeats(evidence.get("heartbeats"))
    validate_zero_public_writes(evidence.get("zero_public_writes"))
    if "done" in evidence:
        _require("failed" not in evidence, "DONE and FAILED both present")
        validate_done(evidence["done"])
        validate_done_against_markers(evidence["done"], records)
        return "COMPLETE_SET_ADMITTED"
    if "failed" in evidence:
        validate_failed(evidence["failed"])
        return "FAIL_CLOSED_ADMITTED"
    raise ValidationError("no terminal evidence: DONE or FAILED missing")


def write_failed_atomic(path, phase):
    """Atomic FAILED.json write; invalid phase fails closed."""
    _require(phase in FAIL_PHASES, "invalid failure phase: %r" % phase)
    import os

    payload = json.dumps({"schema": SCHEMA, "phase": phase},
                         sort_keys=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="ascii") as handle:
        handle.write(payload)
        handle.flush()
    os.replace(tmp_path, path)
