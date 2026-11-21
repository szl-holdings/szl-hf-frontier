#!/usr/bin/env python3
"""Read-only, credential-scoped estate census with fail-closed local receipts."""
from __future__ import annotations

import argparse
import email.utils
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from szl_estate_operational import (  # noqa: E402
    PaginatedInventory, _RejectRedirects, _pagination_links,
    _response_headers, _validated_next_url,
)

GITHUB_ORG = "szl-holdings"
HF_ORG = "SZLHOLDINGS"
SCHEMA = "szl.estate-snapshot-receipt/v1"
FILES = {"github": "github_repositories.json", "models": "huggingface_models.json",
         "datasets": "huggingface_datasets.json", "spaces": "huggingface_spaces.json"}
RECEIPT = "snapshot_receipt.json"
SHA = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?\Z")


class CollectionError(Exception):
    """Only fixed, non-sensitive error codes may cross the CLI boundary."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    """Replace individual files atomically; the receipt is the set commit marker."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".estate-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def source_identity() -> dict[str, Any]:
    result: dict[str, Any] = {"git_sha": None, "working_tree_dirty": None}
    git = shutil.which("git")
    if git:
        head = subprocess.run([git, "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
        status = subprocess.run([git, "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, capture_output=True, text=True)
        if head.returncode == 0 and SHA.fullmatch(head.stdout.strip()):
            result["git_sha"] = head.stdout.strip()
        if status.returncode == 0:
            result["working_tree_dirty"] = bool(status.stdout.strip())
    result["collector_sha256"] = sha256(Path(__file__))
    result["pagination_module_sha256"] = sha256(ROOT / "szl_estate_operational.py")
    return result


def resolve_credentials(public_only: bool = False) -> tuple[dict[str, str], dict[str, Any]]:
    tokens: dict[str, str] = {}
    summaries: dict[str, Any] = {}
    for provider, keys in (
        ("github", ("GH_TOKEN", "GITHUB_TOKEN")),
        ("huggingface", ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "HUGGINGFACE_TOKEN", "HF_ORG_TOKEN1", "HF_ORG_TOKEN")),
    ):
        token, source = "", "none"
        if not public_only:
            for key in keys:
                token = os.environ.get(key, "").strip()
                if token:
                    source = "environment:" + key
                    break
            if not token and provider == "github" and shutil.which("gh"):
                found = subprocess.run(["gh", "auth", "token", "--hostname", "github.com"], capture_output=True, text=True)
                if found.returncode == 0:
                    token, source = found.stdout.strip(), "gh-auth-cache"
            if not token and provider == "huggingface":
                try:
                    from huggingface_hub import get_token
                    token = get_token() or ""
                    if token:
                        source = "huggingface-hub-cache"
                except ImportError:
                    pass
        tokens[provider] = token
        summaries[provider] = {"present": bool(token), "source": source,
                               "identity_validated": False, "organization_membership_validated": False,
                               "all_private_resources_visible": False}
    return tokens, summaries


MAX_PROVIDER_RETRY_ATTEMPTS = 3
MAX_PROVIDER_RETRY_WAIT_S = 20.0


def provider_retry_delay(status: int, headers: dict[str, str], *,
                         provider: str, attempt: int, wall_now: float) -> float | None:
    """Return a bounded-retry *proposal*, never permission to ignore a denial.

    GitHub 403 is retriable only with explicit server evidence of throttling.
    A Retry-After or RateLimit reset longer than the caller's budget must stop
    the call, not be shortened to an unsafe early retry.
    """
    if status != 429 and not (
        provider == "github" and status == 403
        and (headers.get("x-ratelimit-remaining") == "0" or "retry-after" in headers)
    ):
        return None
    retry_after = headers.get("retry-after", "").strip()
    if re.fullmatch(r"[0-9]{1,9}", retry_after):
        return float(int(retry_after))
    if retry_after:
        try:
            parsed = email.utils.parsedate_to_datetime(retry_after)
            if parsed.tzinfo is not None:
                return max(0.0, parsed.timestamp() - wall_now)
        except (TypeError, ValueError, OverflowError):
            retry_after = ""  # Invalid untrusted header; bounded fallback below.
    if provider == "huggingface":
        header = headers.get("ratelimit", "")
        # The Hub exposes seconds to reset in t=<seconds> (within its
        # rate-limit bucket). Never treat the remaining count as a reset.
        found = re.search(r"(?:^|[;\s])t\s*=\s*([0-9]{1,9})(?=[;\s]|$)", header)
        if found:
            return float(int(found.group(1)))
    if provider == "github" and headers.get("x-ratelimit-remaining") == "0":
        reset = headers.get("x-ratelimit-reset", "")
        if re.fullmatch(r"[0-9]{1,11}", reset):
            return max(0.0, float(int(reset)) - wall_now)
    return float(1 << attempt)


def request_json(url: str, token: str | None = None, *, provider: str,
                 sleep_fn=time.sleep, monotonic=time.monotonic,
                 wall_clock=time.time) -> tuple[Any, dict[str, str]]:
    """Read a provider response with a small, deterministic retry budget.

    Exhaustion and explicit auth rejection always fail closed. The caller's
    pagination receipt cannot claim completeness after any failed page.
    """
    parsed = urllib.parse.urlsplit(url)
    expected = {"github": "api.github.com", "huggingface": "huggingface.co"}[provider]
    try:
        trusted = (parsed.scheme == "https" and parsed.hostname == expected
                   and parsed.port in (None, 443) and not parsed.username
                   and not parsed.password and not parsed.fragment)
    except ValueError:
        trusted = False
    if not trusted:
        raise CollectionError("UNSAFE_REQUEST_ORIGIN")
    headers = {"Accept": "application/json", "User-Agent": "szl-estate-audit/2"}
    if provider == "github":
        headers.update({"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, headers=headers, method="GET")
    opener = urllib.request.build_opener(_RejectRedirects())
    started = monotonic()
    for attempt in range(MAX_PROVIDER_RETRY_ATTEMPTS):
        try:
            with opener.open(request, timeout=30) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
                if len(raw) > 8 * 1024 * 1024:
                    raise CollectionError("RESPONSE_TOO_LARGE")
                return json.loads(raw.decode("utf-8")), _response_headers(response.headers)
        except urllib.error.HTTPError as exc:
            try:
                delay = provider_retry_delay(
                    int(exc.code), _response_headers(exc.headers),
                    provider=provider, attempt=attempt, wall_now=wall_clock(),
                )
            finally:
                exc.close()
            if delay is None:
                raise CollectionError(f"HTTP_{exc.code}") from None
            available = MAX_PROVIDER_RETRY_WAIT_S - max(0.0, monotonic() - started)
            if attempt + 1 >= MAX_PROVIDER_RETRY_ATTEMPTS or delay > available:
                raise CollectionError(f"HTTP_{exc.code}_RATE_LIMITED") from None
            sleep_fn(delay)
        except (UnicodeError, json.JSONDecodeError):
            raise CollectionError("INVALID_JSON") from None
        except CollectionError:
            raise
        except Exception:
            raise CollectionError("NETWORK_ERROR") from None
    raise CollectionError("RETRY_BUDGET_EXHAUSTED")


def validate_identities(tokens: dict[str, str], summaries: dict[str, Any]) -> None:
    if not all(tokens.values()):
        raise CollectionError("AUTHENTICATION_REQUIRED")
    gh, _ = request_json("https://api.github.com/user", tokens["github"], provider="github")
    if not isinstance(gh, dict) or not isinstance(gh.get("login"), str):
        raise CollectionError("GITHUB_IDENTITY_INVALID")
    summaries["github"].update(identity_validated=True, identity=gh["login"])
    membership, _ = request_json(f"https://api.github.com/user/memberships/orgs/{GITHUB_ORG}", tokens["github"], provider="github")
    if (not isinstance(membership, dict) or membership.get("state") != "active"
            or str((membership.get("organization") or {}).get("login", "")).casefold() != GITHUB_ORG.casefold()):
        raise CollectionError("GITHUB_ORGANIZATION_MEMBERSHIP_UNVERIFIED")
    summaries["github"].update(organization_membership_validated=True, organization=GITHUB_ORG)
    hf, _ = request_json("https://huggingface.co/api/whoami-v2", tokens["huggingface"], provider="huggingface")
    if not isinstance(hf, dict) or not isinstance(hf.get("name"), str):
        raise CollectionError("HF_IDENTITY_INVALID")
    summaries["huggingface"].update(identity_validated=True, identity=hf["name"])
    if not any(isinstance(org, dict) and str(org.get("name", "")).casefold() == HF_ORG.casefold() for org in hf.get("orgs", [])):
        raise CollectionError("HF_ORGANIZATION_MEMBERSHIP_UNVERIFIED")
    summaries["huggingface"].update(organization_membership_validated=True, organization=HF_ORG)


def inventory_url(kind: str, authenticated: bool) -> str:
    if kind == "github":
        query = urllib.parse.urlencode({"type": "all" if authenticated else "public", "per_page": 100, "sort": "full_name", "direction": "asc"})
        return f"https://api.github.com/orgs/{GITHUB_ORG}/repos?{query}"
    query = urllib.parse.urlencode({"author": HF_ORG, "limit": 100, "full": "true"})
    return f"https://huggingface.co/api/{kind}?{query}"


def validated_inventory_link(kind: str, start: str, current: str, candidate: str,
                             rows: list[dict[str, Any]]) -> str:
    """Allow GitHub's numeric org alias only when every observed owner binds it.

    GitHub canonicalizes /orgs/{login}/repos pagination to
    /organizations/{id}/repos. The immutable owner ID comes from provider rows,
    never from an unvalidated next-link path. Origin and query checks still use
    the shared strict validator.
    """
    resolved = urllib.parse.urljoin(current, candidate)
    path = urllib.parse.urlsplit(resolved).path
    if kind == "github" and re.fullmatch(r"/organizations/[1-9][0-9]*/repos", path):
        owner_ids = set()
        for row in rows:
            owner = row.get("owner")
            if (not isinstance(owner, dict) or type(owner.get("id")) is not int
                    or owner["id"] <= 0 or str(owner.get("login", "")).casefold() != GITHUB_ORG.casefold()):
                raise CollectionError("GITHUB_ORGANIZATION_ALIAS_UNVERIFIED")
            owner_ids.add(owner["id"])
        if len(owner_ids) != 1:
            raise CollectionError("GITHUB_ORGANIZATION_ALIAS_UNVERIFIED")
        owner_id = next(iter(owner_ids))
        parsed = urllib.parse.urlsplit(start)
        alias = parsed._replace(path=f"/organizations/{owner_id}/repos").geturl()
        return _validated_next_url(alias, current, candidate)
    return _validated_next_url(start, current, candidate)


def collect_inventory(kind: str, token: str, max_pages: int) -> PaginatedInventory:
    """Follow validated provider links; a safety limit never certifies completion."""
    provider = "github" if kind == "github" else "huggingface"
    result = PaginatedInventory(scope="TOKEN_VISIBLE" if token else "PUBLIC_ONLY")
    start = inventory_url(kind, bool(token))
    current = start
    visited: set[str] = set()
    identities: set[str] = set()
    try:
        while True:
            if result.pages_fetched >= max_pages:
                raise CollectionError("PAGE_CEILING")
            if current in visited:
                raise CollectionError("PAGINATION_CYCLE")
            visited.add(current)
            result.pages_fetched += 1
            page, headers = request_json(current, token, provider=provider)
            if not isinstance(page, list) or len(page) > 100:
                raise CollectionError("INVALID_LIST_PAGE")
            for row in page:
                if not isinstance(row, dict):
                    raise CollectionError("INVALID_ITEM")
                raw_id = row.get("id") if kind == "github" else row.get("id", row.get("modelId"))
                valid = type(raw_id) is int and raw_id > 0 if kind == "github" else isinstance(raw_id, str) and bool(raw_id.strip())
                if not valid:
                    raise CollectionError("INVALID_ITEM_ID")
                identity = str(raw_id).casefold()
                if identity in identities:
                    raise CollectionError("DUPLICATE_ITEM_ID")
                identities.add(identity)
                name = row.get("full_name") if kind == "github" else raw_id
                org = GITHUB_ORG if kind == "github" else HF_ORG
                if not isinstance(name, str) or len(name.split("/")) != 2 or name.split("/")[0].casefold() != org.casefold():
                    raise CollectionError("OUT_OF_SCOPE_ITEM")
                if type(row.get("private")) is not bool:
                    raise CollectionError("UNKNOWN_VISIBILITY")
                if not token and row["private"]:
                    raise CollectionError("PRIVATE_ITEM_IN_PUBLIC_SCOPE")
                result.items.append(row)
                result.private_items_seen += int(row["private"])
            links = [(validated_inventory_link(kind, start, current, url, result.items), relations)
                     for url, relations in _pagination_links(headers.get("link", ""))]
            following = next((url for url, relations in links if "next" in relations), None)
            if following is None:
                if any(url != current for url, relations in links if "last" in relations):
                    raise CollectionError("NONTERMINAL_LAST_LINK")
                if len(page) == 100 and not any(set(relations) & {"prev", "first", "last"} for _, relations in links):
                    raise CollectionError("MISSING_PAGINATION_LINK")
                result.completion = "COMPLETE"
                return result
            current = following
    except CollectionError as exc:
        result.failure = str(exc)
    except ValueError:
        result.failure = "INVALID_PAGINATION_LINK"
    result.completion = "INCOMPLETE"
    return result


def observed_license(row: dict[str, Any]) -> Any:
    card = row.get("cardData")
    if isinstance(card, dict) and card.get("license"):
        return card["license"]
    tags = row.get("tags", [])
    licenses = [tag.removeprefix("license:") for tag in tags if isinstance(tag, str) and tag.startswith("license:")] if isinstance(tags, list) else []
    return licenses[0] if len(licenses) == 1 else licenses or None


def enrich_item(kind: str, row: dict[str, Any], token: str) -> dict[str, Any]:
    if kind == "github":
        name = row["full_name"]
        branch = row.get("default_branch")
        revision = None
        revision_status = "UNAVAILABLE"
        if isinstance(branch, str) and branch:
            try:
                commit, _ = request_json(f"https://api.github.com/repos/{urllib.parse.quote(name, safe='/')}/commits/{urllib.parse.quote(branch, safe='')}", token, provider="github")
                revision = commit.get("sha") if isinstance(commit, dict) else None
                if not isinstance(revision, str) or not SHA.fullmatch(revision):
                    raise CollectionError("INVALID_GITHUB_REVISION")
                revision_status = "OBSERVED"
            except CollectionError as exc:
                if str(exc) != "HTTP_409":
                    raise
                revision_status = "EMPTY_REPOSITORY"
        result = {key: row.get(key) for key in ("id", "full_name", "html_url", "private", "archived", "disabled", "description", "license", "default_branch", "updated_at", "pushed_at", "homepage", "fork")}
        result.update(source_revision=revision, revision_status=revision_status, metadata_observed_at=utc_now())
        return result
    name = row.get("id") or row.get("modelId")
    if not row.get("sha") or not observed_license(row) or (kind == "spaces" and "runtime" not in row):
        details, _ = request_json(f"https://huggingface.co/api/{kind}/{urllib.parse.quote(name, safe='/')}", token, provider="huggingface")
        if (not isinstance(details, dict) or (details.get("id") or details.get("modelId")) != name
                or type(details.get("private")) is not bool or details["private"] != row["private"]):
            raise CollectionError("HF_METADATA_IDENTITY_OR_VISIBILITY_CHANGED")
        row = {**row, **details}
    revision = row.get("sha")
    if revision is not None and (not isinstance(revision, str) or not SHA.fullmatch(revision)):
        raise CollectionError("INVALID_HF_REVISION")
    return {"path": name, "private": row["private"], "gated": row.get("gated", False),
            "likes": row.get("likes"), "downloads": row.get("downloads"),
            "updated_at": row.get("lastModified"), "task": row.get("pipeline_tag"),
            "sdk": row.get("sdk"), "library_name": row.get("library_name"),
            "tags": row.get("tags", []), "sha": revision, "license": observed_license(row),
            "runtime": row.get("runtime") if kind == "spaces" else None,
            "metadata_observed_at": utc_now()}


def verify_snapshot_set(root: Path) -> dict[str, Any]:
    try:
        receipt = json.loads((root / RECEIPT).read_text(encoding="utf-8"))
        if receipt.get("schema") != SCHEMA or receipt.get("complete") is not True:
            raise CollectionError("SNAPSHOT_RECEIPT_INCOMPLETE")
        for kind, filename in FILES.items():
            record = receipt["files"][filename]
            if record["sha256"] != sha256(root / filename):
                raise CollectionError("SNAPSHOT_HASH_MISMATCH")
            rows = json.loads((root / filename).read_text(encoding="utf-8"))
            if not isinstance(rows, list) or len(rows) != record["count"]:
                raise CollectionError("SNAPSHOT_COUNT_MISMATCH")
            if receipt["inventories"][kind]["completion"] != "COMPLETE":
                raise CollectionError("SNAPSHOT_INVENTORY_INCOMPLETE")
        return receipt
    except CollectionError:
        raise
    except (OSError, ValueError, KeyError, TypeError):
        raise CollectionError("SNAPSHOT_RECEIPT_INVALID") from None


def export_public_snapshot(raw_root: Path, public_root: Path) -> dict[str, Any]:
    """Export explicit public rows without authenticated identities or private counts."""
    if raw_root.resolve() == public_root.resolve():
        raise CollectionError("PUBLIC_OUTPUT_MUST_DIFFER")
    original = verify_snapshot_set(raw_root)
    if original.get("scope") != "TOKEN_VISIBLE":
        raise CollectionError("AUTHENTICATED_CENSUS_REQUIRED")
    receipt = {"schema": SCHEMA, "complete": False, "status": "IN_PROGRESS",
        "started_at": original["started_at"], "completed_at": original["completed_at"],
        "source": original["source"], "signature_status": "UNSIGNED",
        "scope": "PUBLIC_PROJECTION_OF_AUTHENTICATED_CENSUS",
        "parent_receipt_sha256": sha256(raw_root / RECEIPT), "private_scope": "WITHHELD",
        "inventories": {}, "files": {},
        "credentials": {provider: {key: summary[key] for key in ("present", "identity_validated", "organization_membership_validated")} for provider, summary in original["credentials"].items()}}
    write_json(public_root / RECEIPT, receipt)
    for kind, filename in FILES.items():
        rows = [row for row in json.loads((raw_root / filename).read_text(encoding="utf-8")) if row.get("private") is False]
        write_json(public_root / filename, rows)
        receipt["files"][filename] = {"sha256": sha256(public_root / filename), "count": len(rows)}
        receipt["inventories"][kind] = {"completion": "COMPLETE", "scope": receipt["scope"], "count": len(rows), "private_counts_withheld": True}
    receipt.update(complete=True, status="COMPLETE")
    write_json(public_root / RECEIPT, receipt)
    return receipt


def capture(output: Path, *, public_only: bool = False, max_pages: int = 1000, workers: int = 4) -> dict[str, Any]:
    # Reject before writing even the IN_PROGRESS receipt. The committed public
    # projection must never be replaced by token-visible inventory.
    public_root = (ROOT / "data/snapshots").resolve()
    if output.resolve() == public_root or output.resolve().is_relative_to(public_root):
        raise CollectionError("CAPTURE_REQUIRES_LOCAL_OUTPUT_USE_PUBLIC_EXPORT")
    if (not public_only and output.resolve().is_relative_to(ROOT.resolve())
            and not output.resolve().is_relative_to(ROOT.resolve() / ".estate-private")):
        raise CollectionError("AUTHENTICATED_CAPTURE_REQUIRES_PRIVATE_OUTPUT")
    receipt: dict[str, Any] = {"schema": SCHEMA, "complete": False, "status": "IN_PROGRESS",
        "started_at": utc_now(), "completed_at": None, "source": source_identity(),
        "signature_status": "UNSIGNED", "scope": "PUBLIC_ONLY" if public_only else "TOKEN_VISIBLE",
        "private_scope": "NOT_OBSERVED" if public_only else "TOKEN_VISIBLE_NOT_ORG_TOTAL",
        "credentials": {}, "inventories": {}, "files": {}, "failure": None}
    write_json(output / RECEIPT, receipt)
    snapshots: dict[str, Any] = {}
    try:
        tokens, summaries = resolve_credentials(public_only)
        receipt["credentials"] = summaries
        if not public_only:
            validate_identities(tokens, summaries)
        for kind, filename in FILES.items():
            token = tokens["github" if kind == "github" else "huggingface"]
            result = collect_inventory(kind, token, max_pages)
            if result.completion == "COMPLETE":
                try:
                    with ThreadPoolExecutor(max_workers=workers) as pool:
                        rows = list(pool.map(lambda row: enrich_item(kind, row, token), result.items))
                    snapshots[filename] = sorted(rows, key=lambda row: (row.get("path") or row["full_name"]).casefold())
                except CollectionError as exc:
                    result.completion, result.failure = "INCOMPLETE", str(exc)
            summary = result.summary()
            summary.pop("duplicate_ids", None)
            receipt["inventories"][kind] = summary
        if any(summary["completion"] != "COMPLETE" for summary in receipt["inventories"].values()):
            raise CollectionError("INVENTORY_OR_METADATA_INCOMPLETE")
        for filename, rows in snapshots.items():
            write_json(output / filename, rows)
            receipt["files"][filename] = {"sha256": sha256(output / filename), "count": len(rows)}
        receipt.update(complete=True, status="COMPLETE")
    except CollectionError as exc:
        receipt.update(status="FAILED", failure=str(exc))
    except Exception:
        receipt.update(status="FAILED", failure="COLLECTION_INTERNAL_ERROR")
    receipt["completed_at"] = utc_now()
    write_json(output / RECEIPT, receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", nargs="?", default=str(ROOT / ".estate-private/snapshots"), help="Local snapshots; defaults to ignored .estate-private/snapshots. Authenticated output may contain private metadata.")
    parser.add_argument("--public-only", action="store_true", help="Explicit anonymous census; does not establish private coverage.")
    parser.add_argument("--public-output", type=Path, help="Export public rows from the completed authenticated census.")
    parser.add_argument("--max-pages", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=4, choices=range(1, 9))
    args = parser.parse_args(argv)
    if args.max_pages < 1:
        parser.error("--max-pages must be positive")
    if args.public_only and args.public_output:
        parser.error("--public-output requires an authenticated census")
    output = Path(args.output)
    if args.public_output and output.resolve() == args.public_output.resolve():
        parser.error("--public-output must differ from the raw output")
    try:
        receipt = capture(output, public_only=args.public_only, max_pages=args.max_pages, workers=args.workers)
    except CollectionError as exc:
        print("FAILED: " + str(exc), file=sys.stderr)
        return 1
    if not receipt["complete"]:
        print("FAILED: " + receipt["failure"] + "; incomplete receipt retained", file=sys.stderr)
        return 1
    if args.public_output:
        try:
            export_public_snapshot(output, args.public_output)
        except CollectionError as exc:
            print("FAILED: " + str(exc), file=sys.stderr)
            return 1
    print("COMPLETE: four inventories captured; scope=" + receipt["scope"] + "; receipt=UNSIGNED; qualification=UNREVIEWED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
