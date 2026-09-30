"""Fixed-grid calibration for error among accepted proposals.

This utility does not invent confidence scores or grant tool permissions. The
scorer and policy must be frozen before independent calibration data is opened.
The bound requires IID episodes and binary errors; it does not cover distribution
shift or certify individual actions. No observations means no certificate.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

from evidence_lab import MAX_BYTES, canonical, digest, strict_json

GRID = tuple(i / 20 for i in range(21))


def validate_episodes(episodes):
    if not isinstance(episodes, list) or len(episodes) > 100_000:
        raise ValueError("episodes must be a bounded list")
    seen = set()
    for episode in episodes:
        if not isinstance(episode, dict) or set(episode) != {"episode_id", "score", "capability_valid", "error"}:
            raise ValueError("episode keys must be exact")
        identity, score = episode["episode_id"], episode["score"]
        if not isinstance(identity, str) or not identity or identity in seen:
            raise ValueError("episode identities must be nonempty and unique")
        seen.add(identity)
        if type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("score must be finite and in [0,1]")
        if type(episode["capability_valid"]) is not bool or type(episode["error"]) is not bool:
            raise ValueError("capability/error labels must be booleans")


def calibrate(episodes, *, alpha=.05, delta=.05, grid=GRID):
    validate_episodes(episodes)
    for value in (alpha, delta):
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value < 1:
            raise ValueError("alpha/delta must be finite and in (0,1)")
    if not isinstance(grid, tuple) or not grid or len(grid) > 1000 or len(set(grid)) != len(grid):
        raise ValueError("threshold grid must be a predeclared unique nonempty tuple")
    if any(type(t) not in (int, float) or not math.isfinite(t) or not 0 <= t <= 1 for t in grid):
        raise ValueError("thresholds must be finite and in [0,1]")
    candidates = []
    for threshold in sorted(grid):
        accepted = [e for e in episodes if e["capability_valid"] and e["score"] >= threshold]
        count = len(accepted)
        errors = sum(e["error"] for e in accepted)
        bound = min(1., errors / count + math.sqrt(math.log(len(grid) / delta) / (2 * count))) if count else None
        candidates.append({"threshold": threshold, "accepted": count, "errors": errors, "upper_bound": bound, "qualifies": bound is not None and bound <= alpha})
    choices = [c for c in candidates if c["qualifies"]]
    selected = max(choices, key=lambda c: (c["accepted"], c["threshold"])) if choices else None
    result = {
        "schema": "szl.selective-calibration.v1",
        "bound": "SIMULTANEOUS_HOEFFDING_DELTA_OVER_FIXED_GRID",
        "evidence_level": "CONDITIONAL_ON_FIXED_SCORER_POLICY_AND_IID_CALIBRATION",
        "alpha": alpha, "delta": delta, "grid": list(grid),
        "calibration_sha256": digest(episodes), "episodes": len(episodes),
        "candidates": candidates, "selection": selected,
        "decision": "SELECT_THRESHOLD" if selected else "ABSTAIN_ALL",
        "reason": "QUALIFYING_FIXED_THRESHOLD" if selected else "INSUFFICIENT_CALIBRATION",
    }
    result["payload_sha256"] = digest(result)
    return result


def evaluate(episodes, calibration, calibration_episodes):
    """Evaluate the frozen threshold once; do not choose it using test labels."""
    validate_episodes(episodes)
    rebuilt = calibrate(calibration_episodes, alpha=calibration["alpha"], delta=calibration["delta"], grid=tuple(calibration["grid"]))
    if canonical(rebuilt) != canonical(calibration):
        raise ValueError("calibration artifact does not replay")
    overlap = {e["episode_id"] for e in episodes} & {e["episode_id"] for e in calibration_episodes}
    if overlap:
        raise ValueError("calibration and test episode identities overlap")
    threshold = calibration["selection"]["threshold"] if calibration["selection"] else None
    accepted = [e for e in episodes if threshold is not None and e["capability_valid"] and e["score"] >= threshold]
    errors = sum(e["error"] for e in accepted)
    return {"episodes": len(episodes), "accepted": len(accepted), "errors": errors,
            "coverage": len(accepted) / len(episodes) if episodes else None,
            "selective_error": errors / len(accepted) if accepted else None,
            "joint_error": errors / len(episodes) if episodes else None,
            "test_sha256": digest(episodes), "calibration_sha256": calibration["payload_sha256"]}


def read_episodes(path):
    """Read a bounded strict UTF-8 JSON list, not executable dataset code."""
    with Path(path).open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("episode file exceeds the one-MiB CLI byte bound")
    episodes = strict_json(raw.decode("utf-8", errors="strict"))
    validate_episodes(episodes)
    return episodes, hashlib.sha256(raw).hexdigest()


def run_cli(calibration_path, output_path, *, test_path=None, alpha=.05, delta=.05):
    """Offline calibration only; never train, publish, or execute a model/tool."""
    episodes, raw_digest = read_episodes(calibration_path)
    calibration = calibrate(episodes, alpha=alpha, delta=delta)
    test_result, test_digest = None, None
    if test_path is not None:
        test_episodes, test_digest = read_episodes(test_path)
        test_result = evaluate(test_episodes, calibration, episodes)
    report = {
        "schema": "szl.offline-selective-evaluation.v1",
        "evidence_level": "OFFLINE_LABELLED_DATA_CONDITIONAL_ON_IID_ASSUMPTIONS",
        "model_inference_performed": False,
        "publication_status": "LOCAL_UNPUBLISHED", "signed": False,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "calibration_file_sha256": raw_digest, "test_file_sha256": test_digest,
        "calibration": calibration, "test": test_result,
    }
    report["payload_sha256"] = digest(report)
    # Complete validation before creating anything; existing evidence is never
    # replaced, including after a validation or split-overlap failure.
    with Path(output_path).open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write("\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration", required=True, help="Strict JSON list of calibration episodes, at most one MiB")
    parser.add_argument("--test", help="Disjoint sealed test episodes; never used to select the threshold")
    parser.add_argument("--output", required=True, help="New local JSON report; refuses overwrite")
    parser.add_argument("--alpha", type=float, default=.05)
    parser.add_argument("--delta", type=float, default=.05)
    args = parser.parse_args()
    try:
        report = run_cli(args.calibration, args.output, test_path=args.test, alpha=args.alpha, delta=args.delta)
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        parser.error(str(exc))
    print(json.dumps({"output": args.output, "decision": report["calibration"]["decision"], "model_inference_performed": False, "payload_sha256": report["payload_sha256"]}))
