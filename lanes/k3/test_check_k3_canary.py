"""Tests for check_k3_canary: fail-closed, offline, no sleeps.

Every fixture rejections path must raise ValidationError. Valid
DONE and FAILED evidence are admitted. Lazy imports, no ambient
credential reliance (env vars are explicitly dropped).
"""

import copy
import hashlib
import json

import pytest


def _mod():
    import check_k3_canary as mod

    return mod


def make_markers():
    return [
        {"marker": "ENTRY_STARTED", "ts": 0},
        {"marker": "ENTRY_BOOT", "ts": 15},
        {"marker": "ENV_VERIFIED", "ts": 30},
        {"marker": "DATASET_BOUND", "ts": 45},
        {"marker": "KERNELS_READY", "ts": 60},
        {"marker": "TRAIN_LOOP_ENTERED", "ts": 75},
        {"marker": "CHECKPOINT_WRITTEN", "ts": 90},
        {"marker": "CHECKPOINT_VERIFIED", "ts": 105},
    ]


def marker_hash(records):
    canonical = json.dumps(records, sort_keys=True,
                           separators=(",", ":"))
    return hashlib.sha256(canonical.encode("ascii")).hexdigest()


def base_evidence():
    markers = make_markers()
    return {
        "schema": "szl.k3-canary/v1",
        "markers": markers,
        "heartbeats": [
            {"ts": 0},
            {"ts": 60},
            {"ts": 120},
            {"ts": 180},
        ],
        "zero_public_writes": {
            "public_before": {"repos": ["a", "b"]},
            "public_after": {"repos": ["a", "b"]},
            "token_denial_test": True,
        },
        "done": {
            "run_id": "k3-canary-001",
            "image_digest_sha256": "ab" * 32,
            "config_hash": "cfg-hash-001",
            "metrics_hash": "metrics-hash-001",
            "marker_log_hash": marker_hash(markers),
        },
    }


def failed_evidence():
    evidence = base_evidence()
    del evidence["done"]
    evidence["failed"] = {"phase": "DATASET"}
    return evidence


def test_valid_done_admitted():
    mod = _mod()
    verdict = mod.admit_evidence(base_evidence())
    assert verdict == "COMPLETE_SET_ADMITTED"


def test_valid_failed_admitted():
    mod = _mod()
    verdict = mod.admit_evidence(failed_evidence())
    assert verdict == "FAIL_CLOSED_ADMITTED"


def test_out_of_order_markers_rejected():
    mod = _mod()
    evidence = base_evidence()
    evidence["markers"][2], evidence["markers"][3] = (
        evidence["markers"][3],
        evidence["markers"][2],
    )
    with pytest.raises(mod.ValidationError):
        mod.admit_evidence(evidence)


def test_unknown_marker_rejected():
    mod = _mod()
    evidence = base_evidence()
    evidence["markers"][0]["marker"] = "MYSTERY_STARTED"
    with pytest.raises(mod.ValidationError):
        mod.admit_evidence(evidence)


def test_incomplete_marker_set_rejected():
    mod = _mod()
    evidence = base_evidence()
    evidence["markers"] = evidence["markers"][:7]
    with pytest.raises(mod.ValidationError):
        mod.admit_evidence(evidence)


def test_empty_marker_log_rejected():
    mod = _mod()
    evidence = base_evidence()
    evidence["markers"] = []
    with pytest.raises(mod.ValidationError):
        mod.admit_evidence(evidence)


def test_duplicate_marker_rejected():
    mod = _mod()
    evidence = base_evidence()
    evidence["markers"][1] = dict(evidence["markers"][0])
    evidence["markers"][1]["ts"] = 20
    with pytest.raises(mod.ValidationError):
        mod.admit_evidence(evidence)


def test_cadence_violation_rejected():
    mod = _mod()
    evidence = base_evidence()
    evidence["heartbeats"][2]["ts"] = 200
    with pytest.raises(mod.ValidationError):
        mod.admit_evidence(evidence)


def test_public_drift_rejected(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    mod = _mod()
    evidence = base_evidence()
    evidence["zero_public_writes"]["public_after"]["repos"] = ["a"]
    with pytest.raises(mod.ValidationError):
        mod.admit_evidence(evidence)


def test_token_denial_missing_rejected():
    mod = _mod()
    evidence = base_evidence()
    evidence["zero_public_writes"]["token_denial_test"] = False
    with pytest.raises(mod.ValidationError):
        mod.admit_evidence(evidence)


def test_done_and_failed_both_rejected():
    mod = _mod()
    evidence = base_evidence()
    evidence["failed"] = {"phase": "UPLOAD"}
    with pytest.raises(mod.ValidationError):
        mod.admit_evidence(evidence)


def test_no_terminal_rejected():
    mod = _mod()
    evidence = base_evidence()
    del evidence["done"]
    with pytest.raises(mod.ValidationError):
        mod.admit_evidence(evidence)


def test_marker_log_hash_mismatch_rejected():
    mod = _mod()
    evidence = base_evidence()
    evidence["done"]["marker_log_hash"] = "00" * 32
    with pytest.raises(mod.ValidationError):
        mod.admit_evidence(evidence)


def test_malformed_json_rejected():
    mod = _mod()
    with pytest.raises(mod.ValidationError):
        mod.validate_json("{not json")


def test_invalid_failure_phase_rejected():
    mod = _mod()
    with pytest.raises(mod.ValidationError):
        mod.validate_failed({"phase": "UNKNOWN"})


def test_non_read_action_rejected():
    mod = _mod()
    actions = [{"method": "GET"}, {"method": "POST"}]
    with pytest.raises(mod.ValidationError):
        mod.verify_zero_mutations(actions)


def test_read_actions_admitted():
    mod = _mod()
    mod.verify_zero_mutations([{"method": "GET"}, {"method": "HEAD"}])


def test_atomic_failed_write(tmp_path):
    mod = _mod()
    target = str(tmp_path / "FAILED.json")
    mod.write_failed_atomic(target, "KERNELS")
    with open(target, "r", encoding="ascii") as handle:
        payload = json.load(handle)
    assert payload == {"schema": "szl.k3-canary/v1", "phase": "KERNELS"}


def test_atomic_failed_write_invalid_phase(tmp_path):
    mod = _mod()
    target = str(tmp_path / "FAILED.json")
    with pytest.raises(mod.ValidationError):
        mod.write_failed_atomic(target, "UNKNOWN")


def test_ambient_creds_dropped_still_admits(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    mod = _mod()
    evidence = copy.deepcopy(base_evidence())
    assert mod.admit_evidence(evidence) == "COMPLETE_SET_ADMITTED"
