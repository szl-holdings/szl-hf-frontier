"""Offline Frontier-1 observation planner. No provider, credential or compute client.

Default: print a plan. --record explicitly writes an immutable local run.
DONE describes only the dated observation named in done_scope, never a release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import stat
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

SCHEMA = "szl.frontier1.public-observations/v1"
VERSION = "szl.frontier1.offline-receipt/v1"
WOS = tuple(f"WO-{i}" for i in range(1, 8))
TERMINAL = {"DONE", "UNAVAILABLE", "FAIL-CLOSED", "OWNER-PENDING"}
MODELS = (
    "szl-receiptagent-qwen35-0.8b-v2", "szl-receiptagent-qwen35-0.8b-v3",
    "khipu-r3", "chaski-r2", "chaski-5050", "brain-navigator-r2", "KHIPU-R2", "WILLAY",
)
PROFILES = (("model", "SZLHOLDINGS/SZLHOLDINGS"),
            ("dataset", "SZLHOLDINGS/SZLHOLDINGS"), ("space", "SZLHOLDINGS/README"))
LIMIT = 1_048_576


class Refused(ValueError):
    """Fixed public error code, never raw provider/input exception text."""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True,
                       allow_nan=False) + "\n").encode("utf-8")


def exact_hash(value, length=64):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{%d}" % length, value):
        raise Refused("INVALID_DIGEST")
    return value


def fields(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise Refused("INVALID_FIELDS")


def identity(kind, repo):
    if kind not in {"model", "dataset", "space", "github"}:
        raise Refused("INVALID_REPO_TYPE")
    if not isinstance(repo, str) or not re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+", repo):
        raise Refused("INVALID_REPO_ID")
    if any(part in {".", ".."} for part in repo.split("/")):
        raise Refused("INVALID_REPO_ID")
    return f"{kind}:{repo}"


def bind_revision(expected, observed):
    """Offline comparison only: does not issue or authorize a provider CAS."""
    exact_hash(expected, 40)
    exact_hash(observed, 40)
    if expected != observed:
        raise Refused("REVISION_CONFLICT")


def repo_item(item, expected, extra=()):
    fields(item, {"repo_type", "repo_id", "revision", "private", "files", *extra},
           {"repo_type", "repo_id", "revision", "private"})
    key = identity(item["repo_type"], item["repo_id"])
    if item["private"] is not False:
        raise Refused("PUBLIC_METADATA_REQUIRED")
    bind_revision(expected.get(key), item["revision"])
    return key


def inventory(files):
    if not isinstance(files, list) or len(files) > 500:
        raise Refused("INVALID_FILE_INVENTORY")
    seen, result = set(), []
    for entry in files:
        fields(entry, {"path", "bytes"}, {"path", "bytes"})
        name, size = entry["path"], entry["bytes"]
        if (not isinstance(name, str) or not name or "\\" in name or ":" in name
                or name.startswith("/") or any(p in {"", ".", ".."} for p in name.split("/"))
                or any(ord(c) < 32 for c in name) or name in seen):
            raise Refused("INVALID_FILE_PATH")
        if size is not None and (type(size) is not int or size < 0):
            raise Refused("INVALID_FILE_SIZE")
        seen.add(name)
        result.append({"path": name, "bytes": size, "content_hash_status": "NOT_READ"})
    return result


def outcome(status, note, **extra):
    return {"status": status, "note": note, **extra}


def item_outcomes(raw, targets, expected, assess, extra=()):
    """Keep each declared identity, including missing/failed items, separate."""
    keyed, invalid, errors = {}, set(), []
    if not isinstance(raw, list):
        raw = []
        errors.append(outcome("FAIL-CLOSED", "INVALID_ITEMS"))
    for item in raw:
        try:
            if not isinstance(item, dict):
                raise Refused("INVALID_ITEM")
            key = identity(item.get("repo_type"), item.get("repo_id"))
            if key not in targets:
                raise Refused("UNEXPECTED_IDENTITY")
            if key in keyed:
                invalid.add(key)
            else:
                keyed[key] = item
        except Exception:
            errors.append(outcome("FAIL-CLOSED", "INVALID_OR_UNEXPECTED_IDENTITY"))
    results = []
    for key in targets:
        if key in invalid:
            results.append(outcome("FAIL-CLOSED", "DUPLICATE_IDENTITY", identity=key))
            continue
        item = keyed.get(key)
        if item is None:
            results.append(outcome("OWNER-PENDING", "OBSERVATION_NOT_SUPPLIED", identity=key))
            continue
        try:
            repo_item(item, expected, extra)
            result = assess(item)
            results.append({"identity": key, "revision": item["revision"], **result})
        except Exception as exc:
            code = str(exc) if isinstance(exc, Refused) else "ITEM_FAILED"
            results.append(outcome("FAIL-CLOSED", code, identity=key))
    return outcome("FAIL-CLOSED" if errors or any(r["status"] == "FAIL-CLOSED" for r in results)
                   else "OWNER-PENDING", "OBSERVATIONS_ONLY_NO_REMOTE_CHANGES", items=results, input_errors=errors)


def wo1(snapshot):
    def assess(item):
        files = inventory(item.get("files"))
        # Inspect every path. This is presence metadata, NOT tensor qualification.
        candidates = [f for f in files if re.fullmatch(
            r"model(?:-\d{5}-of-\d{5})?\.safetensors", PurePosixPath(f["path"]).name)]
        if not candidates:
            raise Refused("FULL_CHECKPOINT_NOT_EVIDENCED")
        return outcome("OWNER-PENDING", "STAGED_METADATA_REQUIRES_ARTIFACT_OWNER",
                       checkpoint_candidates=candidates, qualification="NOT_ESTABLISHED",
                       card_mutation="NONE", expected_parent=item["revision"])
    return item_outcomes(snapshot.get("models", []),
                         [identity("model", "SZLHOLDINGS/" + n) for n in MODELS],
                         snapshot["expected_heads"], assess)


def wo2(snapshot):
    def assess(item):
        files = inventory(item.get("files"))
        if any(f["bytes"] is None for f in files):
            raise Refused("UNKNOWN_FILE_SIZE")
        if any(f["bytes"] > 50_000_000 for f in files):
            raise Refused("LARGE_FILE_OWNER_REVIEW")
        if item.get("purpose") not in {"HISTORICAL_PROFILE", "INFORMATIONAL_METADATA", "ORG_NAVIGATION"}:
            raise Refused("PURPOSE_NOT_RECONCILED")
        return outcome("OWNER-PENDING", "PRESERVE_EXISTING_INFORMATIONAL_PURPOSE",
                       purpose=item["purpose"], files=files, annotation="NOT_WRITTEN",
                       content_hashes="NOT_READ", deletion="FORBIDDEN")
    return item_outcomes(snapshot.get("profiles", []), [identity(*r) for r in PROFILES],
                         snapshot["expected_heads"], assess, extra={"purpose"})


def wo3(_snapshot):
    return outcome("UNAVAILABLE", "COMPUTE_EXECUTION_EXCLUDED_FROM_THIS_RUNNER",
                   hardware="NOT_PROBED", scheduled_job="NONE", training="NOT_RUN",
                   held_out_evaluation="NOT_RUN", publication_eligible=False)


def canonical_targets(description):
    if not isinstance(description, str) or "Canonical:" not in description:
        raise Refused("CANONICAL_DESCRIPTION_REQUIRED")
    section = description.split("Canonical:", 1)[1]
    targets = list(dict.fromkeys(m.rstrip(".") for m in re.findall(
        r"https://github\.com/([A-Za-z0-9_-]+/[A-Za-z0-9_.-]+)(?=[\s)\],;]|$)", section)))
    if not targets:
        raise Refused("CANONICAL_TARGET_UNRESOLVED")
    for target in targets:
        identity("github", target)
    return targets


def wo4(snapshot):
    data = snapshot.get("pointers")
    if data is None:
        return outcome("OWNER-PENDING", "POINTER_OBSERVATIONS_NOT_SUPPLIED")
    fields(data, {"complete", "repository_count", "archived_count", "source_count", "edge_count", "sources"},
           {"complete", "repository_count", "archived_count", "source_count", "edge_count", "sources"})
    if (data["complete"] is not True or type(data["repository_count"]) is not int
            or type(data["archived_count"]) is not int
            or not 0 < data["archived_count"] <= data["repository_count"]
            or type(data["source_count"]) is not int or type(data["edge_count"]) is not int
            or not isinstance(data["sources"], list) or not data["sources"]
            or len(data["sources"]) != data["source_count"]
            or not 0 < data["source_count"] <= data["archived_count"]):
        raise Refused("INCOMPLETE_POINTER_CENSUS")
    rows, seen = [], set()
    for source in data["sources"]:
        try:
            fields(source, {"repo_id", "archived", "description", "targets"},
                   {"repo_id", "archived", "description", "targets"})
            key = identity("github", source["repo_id"])
            if key in seen or source["archived"] is not True:
                raise Refused("INVALID_POINTER_SOURCE")
            seen.add(key)
            targets = canonical_targets(source["description"])
            if not isinstance(source["targets"], dict) or set(targets) != set(source["targets"]):
                raise Refused("INCOMPLETE_TARGET_OBSERVATIONS")
            for target in targets:
                state = source["targets"][target]
                fields(state, {"exists", "archived", "disabled"}, {"exists", "archived", "disabled"})
                if any(type(value) is not bool for value in state.values()):
                    raise Refused("UNKNOWN_TARGET_STATE")
                ok = state == {"exists": True, "archived": False, "disabled": False}
                rows.append(outcome("DONE" if ok else "FAIL-CLOSED",
                                    "DATED_TARGET_EXISTS_UNARCHIVED" if ok else "TARGET_REQUIRES_OWNER_REVIEW",
                                    source=key, target=identity("github", target)))
        except Exception:
            # Do not reflect an unvalidated source identifier or description.
            rows.append(outcome("FAIL-CLOSED", "INVALID_POINTER_OBSERVATION"))
    if len(rows) != data["edge_count"]:
        rows.append(outcome("FAIL-CLOSED", "EDGE_COUNT_MISMATCH"))
    return outcome("FAIL-CLOSED" if any(r["status"] != "DONE" for r in rows) else "DONE",
                   "DATED_PUBLIC_METADATA_OBSERVATION", items=rows,
                   done_scope="canonical_target_existence_and_unarchived_status_at_observed_at",
                   issues_created=0)


def wo5(_snapshot):
    return outcome("OWNER-PENDING", "PRIVATE_METADATA_EXCLUDED_USE_OWNER_CONTROLLED_CHANNEL",
                   private_metadata="NOT_READ", visibility_changes="NONE")


def wo6(_snapshot):
    # No confirmation parameter, marker-file reader, token reader or gate opener.
    return outcome("OWNER-PENDING", "AUTHENTIC_OWNER_EVIDENCE_NOT_VERIFIED",
                   publish_gate="CLOSED", credential_operations="NONE")


def wo7(snapshot):
    item = snapshot.get("deprecation")
    if item is None:
        return outcome("OWNER-PENDING", "DEPRECATION_OBSERVATION_NOT_SUPPLIED")
    key = repo_item(item, snapshot["expected_heads"], extra={"readme", "readme_sha256"})
    if key != "model:SZLHOLDINGS/governed-inference-meter":
        raise Refused("DEPRECATION_IDENTITY_MISMATCH")
    text = item.get("readme")
    if not isinstance(text, str) or digest(text.encode("utf-8")) != exact_hash(item.get("readme_sha256")):
        raise Refused("README_DIGEST_MISMATCH")
    lines = text.splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        raise Refused("FRONTMATTER_BOUNDARY_MISSING")
    body = lines[lines[1:].index("---") + 2:]
    deprecated = any(line.startswith(">") and "DEPRECATED" in line for line in body)
    canonical = any(line.startswith(">") and re.search(r"canonical|successor|superseded|consolidated", line, re.I)
                    and re.search(r"https://github\.com/szl-holdings/szl-energy-attest(?:[)/\s]|$)", line)
                    for line in body)
    if not deprecated or not canonical:
        raise Refused("SPECIFIC_DEPRECATION_BANNER_NOT_EVIDENCED")
    return outcome("DONE", "EXISTING_BANNER_PRESERVED_NO_EDIT", identity=key,
                   revision=item["revision"], readme_sha256=item["readme_sha256"],
                   done_scope="dated_existing_deprecation_banner_with_specific_canonical_target")


def snapshot_check(snapshot):
    fields(snapshot, {"schema", "observed_at", "source_commit", "expected_heads", "models",
                      "profiles", "pointers", "deprecation"},
           {"schema", "observed_at", "source_commit", "expected_heads"})
    if snapshot["schema"] != SCHEMA:
        raise Refused("INVALID_SCHEMA")
    stamp = snapshot["observed_at"]
    if not isinstance(stamp, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", stamp):
        raise Refused("INVALID_OBSERVATION_TIME")
    datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    exact_hash(snapshot["source_commit"], 40)
    heads = snapshot["expected_heads"]
    if not isinstance(heads, dict):
        raise Refused("INVALID_EXPECTED_HEADS")
    allowed = {identity("model", "SZLHOLDINGS/" + n) for n in MODELS}
    allowed.update(identity(*r) for r in PROFILES)
    allowed.add("model:SZLHOLDINGS/governed-inference-meter")
    if set(heads) - allowed:
        raise Refused("UNEXPECTED_REPO_IDENTITY")
    for revision in heads.values():
        exact_hash(revision, 40)


def plan(snapshot=None, *, handlers=None, input_error=False):
    report = {"schema": VERSION, "mode": "PLAN" if snapshot is None else "OBSERVATION_REPLAY",
              "publish_gate": "CLOSED", "publication_eligible": False, "autonomy_eligible": False,
              "owner_evidence": "NOT_VERIFIED", "remote_mutations": "NONE", "statuses": {}}
    valid = not input_error
    if snapshot is not None:
        try:
            snapshot_check(snapshot)
            report.update(observed_at=snapshot["observed_at"], source_commit=snapshot["source_commit"])
        except Exception:
            valid = False
    calls = handlers or dict(zip(WOS, (wo1, wo2, wo3, wo4, wo5, wo6, wo7)))
    for wo in WOS:
        try:
            if not valid:
                raise Refused("INVALID_PUBLIC_OBSERVATION_INPUT")
            result = calls[wo](snapshot or {"expected_heads": {}})
            if not isinstance(result, dict) or result.get("status") not in TERMINAL:
                raise Refused("INVALID_HANDLER_RESULT")
            encode(result)
            report["statuses"][wo] = result
        except BaseException as exc:
            report["statuses"][wo] = outcome("FAIL-CLOSED", str(exc) if isinstance(exc, Refused) else "HANDLER_FAILED")
    report["statuses"]["WO-6"] = wo6({})
    return report


def no_links(path):
    """Reject symlinks and Windows junction/reparse points in existing ancestors."""
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise Refused("LINK_OR_REPARSE_PATH")


def read_small(path):
    no_links(path)
    with path.open("rb") as handle:
        data = handle.read(LIMIT + 1)
    if len(data) > LIMIT:
        raise Refused("INPUT_TOO_LARGE")
    return data


def write_new(path, data):
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def verify_run(directory):
    no_links(directory)
    master_bytes = read_small(directory / "master.json")
    detached = read_small(directory / "master.sha256").decode("ascii")
    if detached != digest(master_bytes) + "  master.json\n":
        raise Refused("MASTER_DIGEST_MISMATCH")
    master = json.loads(master_bytes)
    expected = {f"wo{i}.json" for i in range(1, 8)}
    inventory_map = master.get("artifact_sha256", {})
    if set(inventory_map) != expected or {p.name for p in directory.iterdir()} != expected | {"master.json", "master.sha256"}:
        raise Refused("RUN_ARTIFACT_SET_MISMATCH")
    if (set(master.get("statuses", {})) != set(WOS) or master.get("publish_gate") != "CLOSED"
            or master.get("publication_eligible") is not False
            or master.get("autonomy_eligible") is not False
            or master.get("owner_evidence") != "NOT_VERIFIED" or master.get("remote_mutations") != "NONE"
            or master["statuses"]["WO-6"] != wo6({})):
        raise Refused("MASTER_CONTRACT_MISMATCH")
    for key in ("input_sha256", "executor_sha256", "request_sha256"):
        exact_hash(master.get(key))
    for name, expected_hash in inventory_map.items():
        data = read_small(directory / name)
        if digest(data) != exact_hash(expected_hash):
            raise Refused("ARTIFACT_DIGEST_MISMATCH")
        wo = "WO-" + name[2]
        if json.loads(data) != master["statuses"][wo] or master["statuses"][wo].get("status") not in TERMINAL:
            raise Refused("ARTIFACT_STATUS_MISMATCH")
    return master


def record_run(root, run_id, report, input_sha256, *, expected_master_sha256=None):
    if (not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", run_id)
            or run_id in {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(10)), *(f"lpt{i}" for i in range(10))}):
        raise Refused("INVALID_RUN_ID")
    exact_hash(input_sha256)
    if expected_master_sha256 is not None:
        exact_hash(expected_master_sha256)
    if (set(report.get("statuses", {})) != set(WOS) or report.get("publish_gate") != "CLOSED"
            or report.get("publication_eligible") is not False
            or report.get("autonomy_eligible") is not False
            or report.get("owner_evidence") != "NOT_VERIFIED" or report.get("remote_mutations") != "NONE"
            or report["statuses"]["WO-6"] != wo6({})
            or any(r.get("status") not in TERMINAL for r in report["statuses"].values())):
        raise Refused("REPORT_CONTRACT_MISMATCH")
    root = Path(os.path.abspath(root))
    no_links(root)
    root.mkdir(parents=True, exist_ok=True)
    no_links(root)
    request_hash = digest(encode({"report": report, "input_sha256": input_sha256,
                                  "executor_sha256": digest(Path(__file__).read_bytes())}))
    final = root / run_id
    lock = root / ("." + run_id + ".lock")
    try:
        lock.mkdir()
    except FileExistsError:
        raise Refused("RUN_LOCKED") from None
    try:
        no_links(final)
        if final.exists():
            master = verify_run(final)
            if expected_master_sha256 is not None and digest(read_small(final / "master.json")) != expected_master_sha256:
                raise Refused("MASTER_CAS_CONFLICT")
            if master.get("request_sha256") != request_hash:
                raise Refused("RUN_ID_CONFLICT")
            return master  # byte-preserving verified idempotent replay
        if expected_master_sha256 is not None:
            raise Refused("EXPECTED_MASTER_MISSING")
        staging = root / ("." + run_id + "." + uuid.uuid4().hex + ".pending")
        staging.mkdir()
        artifacts = {}
        for index, wo in enumerate(WOS, 1):
            name, data = f"wo{index}.json", encode(report["statuses"][wo])
            write_new(staging / name, data)
            artifacts[name] = digest(data)
        master = {**report, "run_id": run_id, "request_sha256": request_hash,
                  "input_sha256": input_sha256, "executor_sha256": digest(Path(__file__).read_bytes()),
                  "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "runtime": {"os": platform.system(), "python": platform.python_version()},
                  "artifact_sha256": artifacts,
                  "inventory_scope": "these seven receipts only; master uses detached digest"}
        master_bytes = encode(master)
        write_new(staging / "master.json", master_bytes)
        write_new(staging / "master.sha256", (digest(master_bytes) + "  master.json\n").encode("ascii"))
        verify_run(staging)
        if final.exists():
            raise Refused("RUN_ID_CONFLICT")
        os.rename(staging, final)  # same-filesystem atomic directory publication
        return verify_run(final)
    finally:
        lock.rmdir()  # only our empty lock; failed .pending evidence is retained


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--record", action="store_true", help="write a LOCAL immutable run; never remote execution")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--expected-master-sha256", help="optional LOCAL receipt CAS; not provider authority")
    args = parser.parse_args(argv)
    data, snapshot, failed = b"", None, False
    if args.observations is not None:
        try:
            data = read_small(args.observations)
            snapshot = json.loads(data)
            if snapshot is None:
                failed = True
        except Exception:
            failed = True
    report = plan(snapshot, input_error=failed)
    if args.record:
        if args.output_root is None or args.run_id is None:
            report["record_error"] = "OUTPUT_ROOT_AND_RUN_ID_REQUIRED"
        else:
            try:
                report = record_run(args.output_root, args.run_id, report, digest(data),
                                    expected_master_sha256=args.expected_master_sha256)
            except Exception:
                report["record_error"] = "LOCAL_FINALIZATION_FAILED_NO_COMPLETION_CLAIM"
    elif args.output_root is not None or args.run_id is not None or args.expected_master_sha256 is not None:
        report["record_error"] = "RECORD_FLAG_REQUIRED"
    print(encode(report).decode("utf-8"), end="")
    return 2 if "record_error" in report else int(any(v["status"] == "FAIL-CLOSED" for v in report["statuses"].values()))


if __name__ == "__main__":
    raise SystemExit(main())
