#!/usr/bin/env python3
"""Bounded, read-only public Space HTTP witnesses; never inference qualification."""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import math
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.capture_estate_snapshots import resolve_credentials, write_json

SHA = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?\Z")
SPACE_ID = re.compile(r"SZLHOLDINGS/[A-Za-z0-9_.-]+\Z", re.I)
LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
PATHS = ("/", "/healthz", "/readyz")
LIMIT = 128 * 1024
HEALTH_KEYS = {"ok", "ready", "healthy", "alive", "health", "readiness"}
REVISION_KEYS = {"sha", "revision", "source_revision", "sourceRevision", "sourceRevisionObserved", "source_sha", "sourceSha", "git_sha", "gitSha", "commit", "commit_sha", "commitSha", "hf_revision", "hf_sha"}
OBJECT_KEYS = {"application", "app", "service", "health", "readiness", "source", "source_binding", "build"}
HEALTH_VALUES = {"ok", "healthy", "ready", "alive", "up", "pass", "passed", "unhealthy", "not_ready", "not-ready", "down", "fail", "failed", "error", "degraded", "blocked", "unavailable", "unknown"}
GOOD_VALUES = {"ok", "healthy", "ready", "alive", "up", "pass", "passed"}
BAD_VALUES = HEALTH_VALUES - GOOD_VALUES - {"unknown"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class WitnessError(Exception):
    """Only fixed error codes cross the report boundary."""


class RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise WitnessError("REDIRECT_REJECTED")



def _strict_json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Never project a last-wins JSON field into public visibility or readiness."""
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise WitnessError("AMBIGUOUS_JSON_OBJECT")
        result[name] = value
    return result


def _deny_nonfinite(_value: str) -> None:
    raise WitnessError("NONFINITE_JSON_NUMBER")


def _strict_json_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise WitnessError("NONFINITE_JSON_NUMBER")
    return number


def strict_json(raw: bytes, *, failure: str) -> Any:
    """Decode untrusted JSON without duplicate keys, NaN or overflow to Infinity.

    This checks parse ambiguity only. A valid snapshot still needs a trusted
    source, current complete inventory and live revision/health verification.
    """
    try:
        return json.loads(
            raw, object_pairs_hook=_strict_json_pairs,
            parse_constant=_deny_nonfinite, parse_float=_strict_json_float,
        )
    except WitnessError:
        raise
    except (ValueError, UnicodeError, RecursionError, OverflowError):
        raise WitnessError(failure) from None


def public_spaces(
    directory: Path, *, observed_at: datetime | None = None, max_age_days: int = 7
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read a retained public subset without concealing inventory exclusions.

    Completed, hash-consistent input is not proof that a provider list is
    current or exhaustive. Private/unknown rows are never probed or named in
    the public summary. Caller-visible counts make partial coverage explicit.
    """
    if type(max_age_days) is not int or not 1 <= max_age_days <= 90:
        raise WitnessError("INVALID_SNAPSHOT_FRESHNESS_POLICY")
    clock = datetime.now(timezone.utc) if observed_at is None else observed_at
    if not isinstance(clock, datetime) or clock.tzinfo is None or clock.utcoffset() is None:
        raise WitnessError("SNAPSHOT_OBSERVER_CLOCK_UNAVAILABLE")
    receipt_path = directory / "snapshot_receipt.json"
    raw_receipt = receipt_path.read_bytes()
    receipt = strict_json(raw_receipt, failure="INVALID_SNAPSHOT_RECEIPT_JSON")
    if not isinstance(receipt, dict):
        raise WitnessError("INVALID_SNAPSHOT_RECEIPT_JSON")
    if receipt.get("schema") != "szl.estate-snapshot-receipt/v1" or receipt.get("complete") is not True:
        raise WitnessError("INCOMPLETE_SNAPSHOT_RECEIPT")
    completed_at = receipt.get("completed_at")
    if not isinstance(completed_at, str):
        raise WitnessError("SNAPSHOT_COMPLETION_TIME_UNAVAILABLE")
    try:
        finished = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
    except ValueError:
        raise WitnessError("SNAPSHOT_COMPLETION_TIME_INVALID") from None
    if finished.tzinfo is None or finished.utcoffset() is None:
        raise WitnessError("SNAPSHOT_COMPLETION_TIME_INVALID")
    age_seconds = (clock.astimezone(timezone.utc) - finished.astimezone(timezone.utc)).total_seconds()
    if age_seconds < -300:
        raise WitnessError("SNAPSHOT_TIMESTAMP_IN_FUTURE")
    age_days = max(0.0, age_seconds / 86400)
    raw = (directory / "huggingface_spaces.json").read_bytes()
    expected = receipt.get("files", {}).get("huggingface_spaces.json", {})
    if hashlib.sha256(raw).hexdigest() != expected.get("sha256"):
        raise WitnessError("SPACE_SNAPSHOT_HASH_MISMATCH")
    rows = strict_json(raw, failure="INVALID_SPACE_SNAPSHOT_JSON")
    if not isinstance(rows, list) or len(rows) != expected.get("count"):
        raise WitnessError("SPACE_SNAPSHOT_COUNT_MISMATCH")
    spaces, seen = [], set()
    skipped_private, skipped_unknown = 0, 0
    for row in rows:
        if not isinstance(row, dict):
            raise WitnessError("INVALID_SPACE_SNAPSHOT_ROW")
        if row.get("private") is True:
            skipped_private += 1
            continue
        if row.get("private") is not False:
            skipped_unknown += 1
            continue
        name = row.get("path")
        if not isinstance(name, str) or not SPACE_ID.fullmatch(name) or name.casefold() in seen:
            raise WitnessError("INVALID_PUBLIC_SPACE_IDENTITY")
        revision = row.get("sha")
        if not isinstance(revision, str) or not SHA.fullmatch(revision):
            raise WitnessError("SPACE_SNAPSHOT_REVISION_MISSING")
        seen.add(name.casefold())
        spaces.append(row)
    stale = age_days > max_age_days
    # No value here certifies complete provider membership or running service.
    coverage_status = (
        "HOLD_STALE_OR_UNOBSERVED_VISIBILITY"
        if stale or skipped_unknown else "OBSERVED_PUBLIC_SUBSET_ONLY"
    )
    return sorted(spaces, key=lambda row: row["path"].casefold()), {
        "path": receipt_path.as_posix(),
        "sha256": hashlib.sha256(raw_receipt).hexdigest(),
        "completed_at": completed_at,
        "space_snapshot_sha256": expected["sha256"],
        "rows_in_snapshot": len(rows),
        "public_space_candidates": len(spaces),
        "private_rows_excluded": skipped_private,
        "unknown_visibility_rows_excluded": skipped_unknown,
        "snapshot_age_days": round(age_days, 4),
        "snapshot_stale": stale,
        "snapshot_max_age_days": max_age_days,
        "coverage_status": coverage_status,
        "complete_org_coverage_verified": False,
        "training_or_serving_verified": False,
    }


def space_host(name: str, metadata: dict[str, Any]) -> tuple[str, str]:
    subdomain = metadata.get("subdomain")
    host = metadata.get("host")
    static_sdk = metadata.get("sdk") == "static"
    declared = None
    if isinstance(subdomain, str) and subdomain:
        declared = subdomain.lower()
        if static_sdk and declared.endswith(".static.hf.space"):
            declared = declared.removesuffix(".static.hf.space")
        else:
            declared = declared.removesuffix(".hf.space")
        if not LABEL.fullmatch(declared):
            raise WitnessError("INVALID_PROVIDER_SUBDOMAIN")
    host_label = None
    static_host = False
    if isinstance(host, str) and host:
        parsed = urllib.parse.urlsplit(host if "://" in host else "https://" + host)
        if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in {"", "/"} or not parsed.netloc.endswith(".hf.space")):
            raise WitnessError("INVALID_PROVIDER_HOST")
        static_host = parsed.netloc.endswith(".static.hf.space")
        if static_host and not static_sdk:
            raise WitnessError("STATIC_HOST_REQUIRES_STATIC_SDK")
        host_label = parsed.netloc.removesuffix(".static.hf.space" if static_host else ".hf.space")
        if not LABEL.fullmatch(host_label):
            raise WitnessError("INVALID_PROVIDER_HOST")
    if declared and host_label and declared != host_label:
        raise WitnessError("PROVIDER_HOST_SUBDOMAIN_MISMATCH")
    chosen = declared or host_label
    suffix = ".static.hf.space" if static_host or (static_sdk and not host_label) else ".hf.space"
    if chosen:
        return chosen + suffix, "live_provider_metadata"
    # HF uses hyphens for namespace separator and underscores. Unrepresentable
    # identifiers remain unknown rather than becoming arbitrary network targets.
    chosen = name.casefold().replace("/", "-").replace("_", "-")
    if not LABEL.fullmatch(chosen):
        raise WitnessError("PUBLIC_RUNTIME_HOST_UNAVAILABLE")
    return chosen + suffix, "derived_from_public_space_identity"


def bounded_application(value: Any, depth: int = 0) -> dict[str, Any]:
    if not isinstance(value, dict) or depth > 3:
        return {}
    result = {}
    for key in sorted(value):
        field = value[key]
        if key in HEALTH_KEYS and isinstance(field, bool):
            result[key] = field
        elif key in HEALTH_KEYS | {"status"} and isinstance(field, str) and field.casefold() in HEALTH_VALUES:
            result[key] = field.casefold()
        elif key in REVISION_KEYS and isinstance(field, str) and SHA.fullmatch(field):
            result[key] = field
        elif key in OBJECT_KEYS and isinstance(field, dict):
            child = bounded_application(field, depth + 1)
            if child:
                result[key] = child
    return result


def app_facts(value: dict[str, Any], prefix: str = "") -> tuple[list[bool], list[dict[str, str]]]:
    states: list[bool] = []
    revisions = []
    for key, field in value.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(field, dict):
            child_states, child_revisions = app_facts(field, path)
            states.extend(child_states)
            revisions.extend(child_revisions)
        elif key in HEALTH_KEYS and isinstance(field, bool):
            states.append(field)
        elif key in HEALTH_KEYS | {"status"} and isinstance(field, str):
            if field in GOOD_VALUES | BAD_VALUES:
                states.append(field in GOOD_VALUES)
        elif key in REVISION_KEYS:
            revisions.append({"field": path, "value": field, "binding": "declared_only"})
    return states, revisions


class RuntimeReader:
    def __init__(self, token: str | None, timeout: float = 15):
        self.token, self.timeout = token, timeout
        self.opener = urllib.request.build_opener(RejectRedirects())
        # Shared across worker threads: stop Hub metadata fan-out on HTTP 429.
        self._hub_rate_limited = threading.Event()
        self._hub_request_lock = threading.Lock()

    def fetch(self, url: str, *, api: bool, allowed_host: str | None = None) -> tuple[int, bytes, bool, str]:
        parsed = urllib.parse.urlsplit(url)
        target = "huggingface.co" if api else allowed_host
        if (not target or parsed.scheme != "https" or parsed.netloc != target
                or parsed.username or parsed.password or parsed.fragment or parsed.query
                or (not api and parsed.path not in PATHS)):
            raise WitnessError("UNSAFE_REQUEST_TARGET")
        if not api:
            suffix = ".static.hf.space" if target.endswith(".static.hf.space") else ".hf.space"
            if not target.endswith(suffix) or not LABEL.fullmatch(target.removesuffix(suffix)):
                raise WitnessError("UNSAFE_PUBLIC_RUNTIME_HOST")
        headers = {"User-Agent": "szl-runtime-witness/1.0", "Accept": "application/json,text/html;q=0.5"}
        if api and self.token:
            headers["Authorization"] = "Bearer " + self.token
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            if api:
                # Serialize metadata request initiation through the response
                # headers: once a 429 arrives, queued workers cannot start.
                with self._hub_request_lock:
                    if self._hub_rate_limited.is_set():
                        raise WitnessError("PROVIDER_RATE_LIMITED")
                    try:
                        response = self.opener.open(request, timeout=self.timeout)
                    except urllib.error.HTTPError as exc:
                        response = exc
                    if response.code == 429:
                        self._hub_rate_limited.set()
            else:
                try:
                    response = self.opener.open(request, timeout=self.timeout)
                except urllib.error.HTTPError as exc:
                    response = exc
            with response:
                raw = response.read(LIMIT + 1)
                content_type = str(response.headers.get("Content-Type", "")).split(";", 1)[0].strip().lower()
                return response.code, raw[:LIMIT], len(raw) > LIMIT, content_type
        except WitnessError:
            raise
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException):
            raise WitnessError("NETWORK_ERROR_OR_TIMEOUT") from None

    def metadata(self, name: str, runtime: bool = False) -> dict[str, Any]:
        if not SPACE_ID.fullmatch(name):
            raise WitnessError("INVALID_PUBLIC_SPACE_IDENTITY")
        code, body, truncated, _ = self.fetch(f"https://huggingface.co/api/spaces/{name}" + ("/runtime" if runtime else ""), api=True)
        if code == 429:
            raise WitnessError("PROVIDER_RATE_LIMITED")
        if code != 200:
            raise WitnessError(f"PROVIDER_HTTP_{code}")
        if truncated:
            raise WitnessError("PROVIDER_METADATA_TOO_LARGE")
        try:
            result = strict_json(body, failure="INVALID_PROVIDER_JSON")
        except (ValueError, UnicodeError, RecursionError):
            raise WitnessError("INVALID_PROVIDER_JSON") from None
        if not isinstance(result, dict):
            raise WitnessError("INVALID_PROVIDER_JSON")
        return result

    def probe(self, host: str, path: str) -> dict[str, Any]:
        observed_at, start = now(), time.monotonic()
        result: dict[str, Any] = {"path": path, "url": f"https://{host}{path}", "observed_at": observed_at,
                                  "http_status": None, "error": None, "application": {}, "declared_revisions": []}
        try:
            code, body, truncated, content_type = self.fetch(result["url"], api=False, allowed_host=host)
            application = {}
            if not truncated:
                try:
                    application = bounded_application(strict_json(body, failure="INVALID_APPLICATION_JSON"))
                except WitnessError:
                    # Invalid or ambiguous health never becomes affirmative readiness.
                    pass
            _, revisions = app_facts(application)
            result.update(http_status=code, body_sha256=hashlib.sha256(body).hexdigest(),
                          body_hash_scope="first_131072_bytes" if truncated else "complete_response_body",
                          bytes_observed=len(body), truncated=truncated, content_type=content_type if content_type in {"application/json", "text/html", "text/plain"} else "other",
                          application=application, declared_revisions=revisions)
        except WitnessError as exc:
            result["error"] = str(exc)
        result["elapsed_ms"] = round((time.monotonic() - start) * 1000)
        return result


def assess_runtime(result: dict[str, Any]) -> str:
    """Evaluate retained probes without turning a refused redirect into an outage."""
    stage = result.get("provider_stage")
    failure = (stage in {"BUILD_ERROR", "RUNTIME_ERROR", "CONFIG_ERROR", "DELETING"}
               or result.get("hub_revision_matches_snapshot") is False
               or result.get("runtime_revision_matches_snapshot") is False)
    # A provider lifecycle stage other than RUNNING cannot be made healthy by
    # a cached 200 or a previous self-reported /healthz response.
    if stage != "RUNNING":
        return "FAIL" if failure else "UNKNOWN"
    healthy = False
    rate_limited = False
    for probe in result.get("probes", []):
        code = probe.get("http_status")
        if code == 429:
            rate_limited = True  # Not evidence that the application is unhealthy.
        states, _ = app_facts(probe.get("application", {}))
        if probe["path"] == "/":
            if probe.get("error") and probe["error"] != "REDIRECT_REJECTED":
                failure = True
            if code is not None and code >= 400 and code != 429:
                failure = True
        if code is not None and code >= 500:
            failure = True
        if False in states:
            failure = True
        if probe["path"] in {"/healthz", "/readyz"} and code == 200 and states and all(states):
            healthy = True
    if failure:
        return "FAIL"
    if rate_limited:
        return "UNKNOWN"
    # Public HTTP alone does not establish an actively running provider.
    if result.get("provider_stage") != "RUNNING":
        return "UNKNOWN"
    return "HEALTH_RESPONSE_OBSERVED" if healthy else "UNKNOWN"


def witness(row: dict[str, Any], reader: RuntimeReader) -> dict[str, Any]:
    name, expected = row["path"], row["sha"]
    result: dict[str, Any] = {"id": "huggingface-space/" + name.casefold(), "space": name,
                              "observed_at": now(), "expected_hf_revision": expected,
                              "runtime": "UNKNOWN", "functional_inference_verified": False,
                              "probes": [], "errors": [], "notes": ["HTTP and health declarations only; no inference, qualification, or release authority is established."]}
    try:
        metadata = reader.metadata(name)
        if metadata.get("private") is not False or str(metadata.get("id", "")).casefold() != name.casefold():
            raise WitnessError("LIVE_PUBLIC_IDENTITY_NOT_CONFIRMED")
        runtime = metadata.get("runtime")
        if not isinstance(runtime, dict):
            runtime = reader.metadata(name, runtime=True)
        host, host_source = space_host(name, metadata)
        hub_sha = metadata.get("sha")
        hub_sha = hub_sha if isinstance(hub_sha, str) and SHA.fullmatch(hub_sha) else None
        runtime_sha = runtime.get("sha") or runtime.get("revision")
        runtime_sha = runtime_sha if isinstance(runtime_sha, str) and SHA.fullmatch(runtime_sha) else None
        stage = runtime.get("stage")
        stage = stage if isinstance(stage, str) and re.fullmatch(r"[A-Z_]{1,40}", stage) else "UNKNOWN"
        result.update(host=host, host_source=host_source, hub_observed_revision=hub_sha,
                      hub_revision_matches_snapshot=None if hub_sha is None else hub_sha == expected,
                      runtime_observed_revision=runtime_sha,
                      runtime_revision_matches_snapshot=None if runtime_sha is None else runtime_sha == expected,
                      provider_stage=stage)
        if hub_sha is not None and hub_sha != expected:
            result["errors"].append("HUB_REVISION_DRIFT")
        if runtime_sha is not None and runtime_sha != expected:
            result["errors"].append("RUNTIME_REVISION_MISMATCH")
        if stage == "RUNNING":
            result["probes"] = [reader.probe(host, path) for path in PATHS]
        else:
            # GET can wake a sleeping free-tier Space. Do not mutate its
            # lifecycle just to sample reachability, nor infer availability.
            result["notes"].append(
                "Provider is not RUNNING; no public runtime routes were probed."
            )
        result["runtime"] = assess_runtime(result)
        if runtime_sha is None:
            result["notes"].append("Provider runtime revision is absent; repository HEAD and application source declarations do not bind deployed code.")
    except WitnessError as exc:
        result["errors"].append(str(exc))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/snapshots"))
    parser.add_argument("--output", type=Path, default=Path("reports/runtime_witness.json"))
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    if not 1 <= args.workers <= 6 or not 0 < args.timeout <= 15:
        parser.error("Workers must be 1..6 and timeout must be greater than 0 and at most 15 seconds")
    rows, receipt = public_spaces(args.input)
    tokens, _ = resolve_credentials()
    reader = RuntimeReader(tokens.get("huggingface"), args.timeout)
    started = now()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda row: witness(row, reader), rows))
    report = {"schema": "szl.public-runtime-witness/v1", "started_at": started, "completed_at": now(),
              "snapshot_receipt": receipt, "authenticated_metadata": bool(reader.token),
              "public_runtime_requests_authenticated": False,
              "complete_org_coverage_verified": False,
              "trained_model_count_verified": False,
              "release_authorized": False,
              "request_paths": list(PATHS),
              "limits": {"workers": args.workers, "timeout_seconds": args.timeout, "response_bytes": LIMIT},
              "artifact_count": len(results), "functional_inference_verified": False,
              "by_runtime": dict(sorted(Counter(item["runtime"] for item in results).items())), "artifacts": results}
    write_json(args.output, report)
    print(json.dumps({key: report[key] for key in ("artifact_count", "by_runtime", "functional_inference_verified")}, sort_keys=True))


if __name__ == "__main__":
    main()
