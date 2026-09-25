#!/usr/bin/env python3
"""Read public, revision-bound source cards and emit conservative review candidates.

This is metadata extraction, not human review, qualification, or release authority.
Only explicit public inventory rows are fetched. Credentials never enter receipts.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

SURFACES = {"models": "huggingface-model", "datasets": "huggingface-dataset", "spaces": "huggingface-space"}
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REVISION = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
GH_LINK = re.compile(r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)([^\s<>\]\)\"']*)", re.I)
SOURCE_WORDS = re.compile(r"\b(canonical|source(?:\s+code)?|upstream|implementation|successor|replaced\s+by|superseded\s+by)\b", re.I)
PRODUCTION = re.compile(r"\b(production[- ](?:ready|grade)|live\s+(?:deployment|endpoint|runtime)|fully\s+operational|operational\s+(?:endpoint|service)|deployed\s+(?:to|in)\s+production)\b", re.I)
NEGATION = re.compile(r"\b(not|never|no|without|isn't|aren't|cannot|can't|non)\b|\b(prohibited|unsupported|unverified|unqualified|does not)\b", re.I)
MAX_CARD_BYTES = 2 * 1024 * 1024


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def public_items(root: Path) -> list[dict[str, Any]]:
    """Missing privacy markers are unknown, never treated as public."""
    items = []
    for kind in ("github", *SURFACES):
        path = root / ("github_repositories.json" if kind == "github" else f"huggingface_{kind}.json")
        if not path.is_file():
            raise ValueError(f"Required inventory snapshot missing: {path.name}")
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            raise ValueError(f"Invalid inventory snapshot: {path.name}")
        for row in rows:
            if not isinstance(row, dict) or row.get("private") is not False:
                continue
            name = row.get("full_name") if kind == "github" else row.get("path")
            if not isinstance(name, str) or not REPO.fullmatch(name):
                raise ValueError("Invalid public repository identity")
            surface = "github" if kind == "github" else SURFACES[kind]
            prefix = "" if kind in {"github", "models"} else f"{kind}/"
            base = "https://github.com/" if kind == "github" else "https://huggingface.co/"
            items.append({"id": f"{surface}/{name.casefold()}", "kind": kind, "name": name,
                          "url": base + prefix + name, "inventory": row})
    ids = [item["id"] for item in items]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate public inventory identity")
    return sorted(items, key=lambda item: item["id"])


class SourceUnavailable(Exception):
    """Safe error code; never wraps raw response bodies or headers."""


def safe_origin(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or parsed.netloc not in {"api.github.com", "huggingface.co"}
            or parsed.username or parsed.password or parsed.fragment):
        raise SourceUnavailable("UNSAFE_PROVIDER_URL")
    return parsed.netloc


class SameOriginRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        if safe_origin(newurl) != safe_origin(request.full_url):
            raise SourceUnavailable("OFF_ORIGIN_REDIRECT")
        return super().redirect_request(request, fp, code, msg, headers, newurl)


class Reader:
    def __init__(self, github_token: str | None = None, hf_token: str | None = None):
        self.github_token = github_token
        self.hf_token = hf_token
        self.opener = urllib.request.build_opener(SameOriginRedirect())

    def read(self, url: str, *, github: bool = False, limit: int = MAX_CARD_BYTES) -> bytes:
        if safe_origin(url) != ("api.github.com" if github else "huggingface.co"):
            raise SourceUnavailable("WRONG_CREDENTIAL_ORIGIN")
        token = self.github_token if github else self.hf_token
        headers = {"User-Agent": "szl-estate-source-classifier/1.0", "Accept": "application/json" if github else "*/*"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with self.opener.open(request, timeout=40) as response:
                body = response.read(limit + 1)
        except urllib.error.HTTPError as exc:
            raise SourceUnavailable(f"HTTP_{exc.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise SourceUnavailable("REQUEST_FAILED") from None
        if len(body) > limit:
            raise SourceUnavailable("RESPONSE_TOO_LARGE")
        return body

    def json(self, url: str, *, github: bool = False) -> Any:
        try:
            return json.loads(self.read(url, github=github, limit=16 * 1024 * 1024))
        except (ValueError, UnicodeError):
            raise SourceUnavailable("INVALID_JSON") from None


def save_evidence(directory: Path, item: dict[str, Any], revision: str, kind: str,
                  body: bytes, url: str, source_path: str) -> dict[str, Any]:
    digest = hashlib.sha256(body).hexdigest()
    # Hash-based paths do not trust remote repository or card names as local paths.
    path = directory / "blobs" / f"{digest}.{'md' if kind == 'source_card' else 'json'}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    stored_path = path.resolve().relative_to(directory.resolve().parent.parent).as_posix()
    return {"kind": kind, "url": url, "revision": revision, "sha256": digest,
            "path": stored_path, "source_path": source_path, "bytes": len(body), "status": "observed"}


def capture(item: dict[str, Any], directory: Path, reader: Reader) -> dict[str, Any]:
    observed: dict[str, Any] = {"id": item["id"], "observed_at": now(), "observed_revision": None,
                                 "card": "", "files": [], "evidence": [], "errors": []}
    row, kind, name = item["inventory"], item["kind"], item["name"]
    revision = row.get("source_revision") or row.get("sha") or row.get("revision") or row.get("head_sha")
    try:
        if kind == "github":
            api = f"https://api.github.com/repos/{name}"
            current = reader.json(api, github=True)
            if current.get("private") is not False:
                raise SourceUnavailable("PUBLIC_VISIBILITY_NOT_CONFIRMED")
            if str(current.get("full_name", "")).casefold() != name.casefold():
                raise SourceUnavailable("REPOSITORY_IDENTITY_MISMATCH")
            if not isinstance(revision, str) or not REVISION.fullmatch(revision):
                branch = str(row.get("default_branch") or "HEAD")
                data = reader.json(f"{api}/commits/{urllib.parse.quote(branch, safe='')}", github=True)
                revision = data.get("sha")
            if not isinstance(revision, str) or not REVISION.fullmatch(revision):
                raise SourceUnavailable("IMMUTABLE_REVISION_MISSING")
            observed["observed_revision"] = revision
            readme_url = f"{api}/readme?ref={revision}"
            data = reader.json(readme_url, github=True)
            if data.get("encoding") != "base64" or not isinstance(data.get("content"), str):
                raise SourceUnavailable("README_CONTENT_UNAVAILABLE")
            body = base64.b64decode(data["content"], validate=False)
            if len(body) > MAX_CARD_BYTES:
                raise SourceUnavailable("RESPONSE_TOO_LARGE")
            source_path = str(data.get("path") or "README.md")
            immutable_url = f"https://github.com/{name}/blob/{revision}/{urllib.parse.quote(source_path, safe='/')}"
            observed["evidence"].append(save_evidence(directory, item, revision, "source_card", body, immutable_url, source_path))
            observed["card"] = body.decode("utf-8", errors="replace")
        else:
            api = f"https://huggingface.co/api/{kind}/{name}"
            if not isinstance(revision, str) or not REVISION.fullmatch(revision):
                data = reader.json(api)
                revision = data.get("sha")
            if not isinstance(revision, str) or not REVISION.fullmatch(revision):
                raise SourceUnavailable("IMMUTABLE_REVISION_MISSING")
            observed["observed_revision"] = revision
            metadata_url = f"{api}/revision/{revision}"
            data = reader.json(metadata_url)
            if data.get("sha") != revision:
                raise SourceUnavailable("REVISION_MISMATCH")
            # Authenticated reads must not expand the public scope if visibility changed.
            if data.get("private") is not False:
                raise SourceUnavailable("PUBLIC_VISIBILITY_NOT_CONFIRMED")
            siblings = data.get("siblings")
            if not isinstance(siblings, list):
                raise SourceUnavailable("FILE_INVENTORY_UNAVAILABLE")
            observed["files"] = sorted({entry["rfilename"] for entry in siblings
                                         if isinstance(entry, dict) and isinstance(entry.get("rfilename"), str)})
            inventory_body = (json.dumps({"revision": revision, "files": observed["files"]}, indent=2, sort_keys=True) + "\n").encode()
            observed["evidence"].append(save_evidence(directory, item, revision, "file_inventory", inventory_body, metadata_url, ""))
            readme = next((path for path in observed["files"] if path.casefold() == "readme.md"), None)
            if readme is None:
                raise SourceUnavailable("README_NOT_IN_REVISION")
            card_url = f"{item['url']}/resolve/{revision}/{urllib.parse.quote(readme, safe='/')}"
            body = reader.read(card_url)
            observed["evidence"].append(save_evidence(directory, item, revision, "source_card", body, card_url, readme))
            observed["card"] = body.decode("utf-8", errors="replace")
    except SourceUnavailable as exc:
        observed["errors"].append(str(exc))
    except (KeyError, TypeError, ValueError):
        observed["errors"].append("INVALID_SOURCE_RESPONSE")
    return observed


def github_claims(card: str, public_github: set[str]) -> list[dict[str, Any]]:
    claims = []
    heading = ""
    heading_line = -100
    for number, line in enumerate(card.splitlines(), 1):
        if line.lstrip().startswith("#"):
            heading, heading_line = line, number
        for match in GH_LINK.finditer(line):
            name = match.group(1).removesuffix(".git").casefold()
            context = line + (" " + heading if number - heading_line <= 6 else "")
            claims.append({"url": match.group(0).rstrip(".,;:"), "repository": name,
                           "verified_public_repository": name in public_github,
                           "mapping_context": bool(SOURCE_WORDS.search(context)), "line": number,
                           "relation": "successor" if re.search(r"\b(successor|replaced by|superseded by)\b", context, re.I) else "source"})
    return claims


def production_claims(card: str) -> list[dict[str, Any]]:
    """Flag bounded affirmative prose; this is candidate extraction, not fact checking."""
    results = []
    in_code = False
    lines = card.splitlines()
    for number, line in enumerate(lines, 1):
        if line.lstrip().startswith(("```", "~~~")):
            in_code = not in_code
            continue
        if in_code:
            continue
        if "|" in line and number < len(lines) and re.fullmatch(r"\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*", lines[number]):
            continue  # A Markdown table's column labels do not assert deployment.
        previous = []
        for preceding in reversed(lines[max(0, number - 3):number - 1]):
            if not preceding.strip() or preceding.lstrip().startswith(("#", "|", "```", "~~~")):
                break
            previous.insert(0, preceding)
        context = " ".join(previous)
        context = re.split(r"(?<=[.!?;])\s+", context)[-1] if context else ""
        if re.search(r"[.!?;][*_`>]*\s*$", context):
            context = ""
        for sentence_index, sentence in enumerate(re.split(r"(?<=[.!?;])\s+", line)):
            for match in PRODUCTION.finditer(sentence):
                before = ((context if sentence_index == 0 else "") + " " + sentence[:match.start()])[-160:]
                after = re.sub(r"[*_`]", "", sentence[match.end():match.end() + 80])
                # Negation only binds in this bounded clause. Contrast starts a new clause.
                before = re.split(r"\b(?:but|however|whereas)\b", before, flags=re.I)[-1]
                negative_value = re.match(r"\s*[:|=]?\s*(?:(?:state|status|claim)\s*)?[:|=]?\s*(?:(?:is|are|remains?)\s*)?(?:not|false|unknown|unverified|unsupported|prohibited|blocked|demoted|deprecated)\b", after, re.I)
                required_evidence = re.search(r"\brequires?\s+(?:a\s+)?(?:separate\s+)?$", before, re.I)
                negated = bool(NEGATION.search(before) or negative_value or required_evidence)
                if not negated:
                    results.append({"line": number, "claim": match.group(0),
                                    "excerpt": sentence[max(0, match.start() - 90):match.end() + 100].strip()})
    return results


def classify(item: dict[str, Any], observation: dict[str, Any], public_github: set[str]) -> dict[str, Any]:
    kind, row = item["kind"], item["inventory"]
    card = observation.get("card", "")
    claims = github_claims(card, public_github)
    mapping = [claim for claim in claims if claim["mapping_context"]]
    verified = {claim["repository"] for claim in mapping if claim["verified_public_repository"]}
    invalid = [claim for claim in mapping if not claim["verified_public_repository"]]
    positive_claims = production_claims(card)
    notes = ["Automated source extraction only; human review and operational qualification remain outstanding."]
    audit_status = "UNREVIEWED"
    inspected = bool(card and any(entry.get("kind") == "source_card" for entry in observation.get("evidence", [])))
    lower = card.casefold()
    klass = {"github": "repository", "models": "model", "datasets": "dataset", "spaces": "space"}[kind]
    status = "SOURCE_BACKED" if kind == "github" and inspected else "EXPERIMENTAL"
    classification = "canonical_source" if kind == "github" and inspected else "unresolved"
    role = "source" if classification == "canonical_source" else "none"
    links: dict[str, str] = {"github" if kind == "github" else "huggingface": item["url"]}
    recommendations = []
    if kind == "spaces":
        classification, role = "operational_runtime_surface", "runtime"
        status = "SOFTWARE" if inspected else "EXPERIMENTAL"
        links["space"] = item["url"]
        notes.append("Runtime surface describes its target role; no health, inference, or readiness probe was performed.")
    if kind == "datasets":
        classification, role = "support_artifact", "record"
    if kind == "github" and inspected and re.search(r"\b(execution tracker|documentation repository|reference.only|test fixtures|provenance archive)\b", "\n".join(card.splitlines()[:25]), re.I):
        classification, role, status = "support_artifact", "record", "REFERENCE"
    if kind == "models":
        if re.search(r"\b(software (?:kernel|package|library)|python (?:kernel|package|library)|not a (?:trained )?(?:model|checkpoint))\b", lower):
            klass, status = "kernel", "SOFTWARE"
        notes.append("Repository files and card statements do not prove training, evaluation, or promotion of model weights.")
    if len(verified) == 1 and not invalid:
        target = next(claim for claim in mapping if claim["repository"] in verified)
        if kind != "github":
            links["github"] = target["url"]
            if kind != "spaces":
                classification, role = "mirror_distribution", "mirror"
        else:
            successors = [claim for claim in mapping if claim["relation"] == "successor" and claim["repository"] != item["name"].casefold()]
            if successors:
                links["successor"] = successors[0]["url"]
    elif kind != "github" or invalid or len(verified) > 1:
        audit_status = "NEEDS_CANONICAL_MAPPING"
        reason = "ambiguous" if len(verified) > 1 else "unverified" if invalid else "missing"
        notes.append(f"Explicit canonical GitHub mapping is {reason}; no route was guessed from repository names.")
        recommendations.append({"action": "resolve_canonical_mapping", "reason": reason, "owner": "SZL Holdings maintainer"})
    # Source-card words are claims only; retained source evidence does not verify their qualifications.
    declared = re.search(r"(?im)^\s*(?:>\s*)?(?:\*\*)?(?:status|truth.status|lifecycle)\s*(?:\*\*)?\s*[:|]\s*(?:\*\*)?([A-Z_ -]+)", card)
    declared_status = declared.group(1).strip().upper() if declared else ""
    provider_deprecated = kind == "github" and bool(re.match(r"^\s*(?:\[)?deprecated\b", str(row.get("description") or ""), re.I))
    if row.get("archived") is True:
        klass, status, classification, role = "archive", "DEPRECATED" if provider_deprecated else "ARCHIVED", "archived_provenance", "record"
    elif provider_deprecated or "DEPRECATED" in declared_status or "SUPERSEDED" in declared_status:
        status, classification, role = "DEPRECATED", "successor_deprecated", "record"
    elif any(word in declared_status for word in ("BLOCKED", "QUARANTINED", "EXPERIMENTAL", "RESEARCH")):
        classification = "experimental_blocked"
        status = "BLOCKED" if any(word in declared_status for word in ("BLOCKED", "QUARANTINED")) else "EXPERIMENTAL"
    if status in {"ARCHIVED", "DEPRECATED"} and not links.get("successor"):
        audit_status = "NEEDS_CANONICAL_MAPPING"
        notes.append("Archived/deprecated provenance has no verified explicit successor mapping.")
    if not inspected:
        audit_status = "UNAVAILABLE_WITH_REASON"
        notes.append("Immutable source card unavailable: " + ", ".join(observation.get("errors") or ["EMPTY_SOURCE_CARD"]))
    if positive_claims:
        recommendations.append({"action": "verify_or_bound_public_runtime_claims", "owner": "SZL Holdings maintainer",
                                "reason": "Affirmative production/live language requires separate source-bound runtime evidence."})
        notes.append(f"{len(positive_claims)} affirmative runtime claim candidate(s); card language is not operational proof.")
        if audit_status == "UNREVIEWED":
            audit_status = "NEEDS_STATUS_CORRECTION"
    return {"id": item["id"], "artifact_class": klass, "status": status,
            "canonical": {"role": role, "url": item["url"]}, "links": links,
            "audit": {"status": audit_status, "last_checked": observation["observed_at"], "notes": notes},
            "classification": classification, "observed_revision": observation.get("observed_revision"),
            "evidence": observation.get("evidence", []), "source_claims": claims,
            "production_claims": positive_claims, "candidate_recommendations": recommendations,
            "review_method": "automated_source_extraction"}


def observation_path(directory: Path, item: dict[str, Any]) -> Path:
    return directory / "observations" / (hashlib.sha256(item["id"].encode()).hexdigest() + ".json")


def load_observation(directory: Path, item: dict[str, Any]) -> dict[str, Any]:
    observation = json.loads(observation_path(directory, item).read_text(encoding="utf-8"))
    if observation.get("id") != item["id"]:
        raise ValueError("Observation identity mismatch")
    revision = observation.get("observed_revision")
    for entry in observation.get("evidence", []):
        if entry.get("revision") != revision or not isinstance(revision, str) or not REVISION.fullmatch(revision):
            raise ValueError("Observation revision mismatch")
        stored = entry.get("path")
        if (not isinstance(stored, str) or not stored or "\\" in stored
                or PurePosixPath(stored).is_absolute() or PureWindowsPath(stored).drive
                or any(part in {"..", "."} for part in stored.split("/"))):
            raise ValueError("Unsafe evidence path: expected a repository-relative path")
        target = directory.resolve().parent.parent.joinpath(*PurePosixPath(stored).parts)
        if target.is_symlink() or not target.resolve().is_relative_to(directory.resolve()):
            raise ValueError("Unsafe evidence path: outside evidence directory")
        content = target.read_bytes()
        if hashlib.sha256(content).hexdigest() != entry.get("sha256"):
            raise ValueError("Observation content hash mismatch")
        if entry.get("kind") == "source_card" and observation.get("card") != content.decode("utf-8", errors="replace"):
            raise ValueError("Observation card content mismatch")
    return observation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/snapshots"))
    parser.add_argument("--output", type=Path, default=Path("data/source_reviews.json"))
    parser.add_argument("--evidence-dir", type=Path, default=Path("data/source-evidence"))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--offline", action="store_true", help="Reclassify retained observations with verified content hashes; never call providers.")
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error("--workers must be between 1 and 8")
    items = public_items(args.input)
    if not items:
        raise SystemExit("No explicitly public inventory rows; no output written.")
    reader = Reader(os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN"), os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN"))
    public_github = {item["name"].casefold() for item in items if item["kind"] == "github"}
    def process(item: dict[str, Any]) -> dict[str, Any]:
        if args.offline:
            observation = load_observation(args.evidence_dir, item)
        else:
            observation = capture(item, args.evidence_dir, reader)
            write_json(observation_path(args.evidence_dir, item), observation)
        return classify(item, observation, public_github)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        reviews = list(pool.map(process, items))
    write_json(args.output, reviews)
    summary = {"review_method": "automated_source_extraction", "artifact_count": len(reviews),
               "qualified_artifact_count": 0, "generated_at": now(), "offline": args.offline,
               "authenticated": {"github": bool(reader.github_token), "huggingface": bool(reader.hf_token)},
               "by_classification": {}, "by_audit_status": {}}
    for review in reviews:
        for field, key in (("by_classification", review["classification"]), ("by_audit_status", review["audit"]["status"])):
            summary[field][key] = summary[field].get(key, 0) + 1
    write_json(args.output.with_suffix(".summary.json"), summary)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
