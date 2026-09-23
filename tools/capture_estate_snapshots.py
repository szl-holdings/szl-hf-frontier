#!/usr/bin/env python3
"""Capture GitHub and Hugging Face estate metadata into local JSON snapshots.

Read-only collector. Credentials are optional for public inventory and are read only
from GITHUB_TOKEN/HF_TOKEN environment variables. Values are never printed or stored.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

GITHUB_ORG = "szl-holdings"
HF_ORG = "SZLHOLDINGS"
USER_AGENT = "szl-estate-audit/1.0"


def request_json(url: str, token: str | None = None) -> Any:
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def github_repositories(token: str | None) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for page in range(1, 20):
        url = f"https://api.github.com/orgs/{GITHUB_ORG}/repos?type=all&per_page=100&page={page}&sort=updated&direction=desc"
        batch = request_json(url, token)
        if not isinstance(batch, list) or not batch:
            break
        entries.extend(batch)
        if len(batch) < 100:
            break
    return entries


def hf_repositories(kind: str, token: str | None) -> list[dict[str, Any]]:
    endpoint = {"models": "models", "datasets": "datasets", "spaces": "spaces"}[kind]
    query = urllib.parse.urlencode({"author": HF_ORG, "limit": "100", "full": "true"})
    result = request_json(f"https://huggingface.co/api/{endpoint}?{query}", token)
    if not isinstance(result, list):
        raise RuntimeError(f"Unexpected Hugging Face {kind} response")
    normalized: list[dict[str, Any]] = []
    for item in result:
        repo_id = item.get("id") or item.get("modelId")
        if not repo_id:
            continue
        normalized.append({
            "path": repo_id,
            "private": bool(item.get("private", False)),
            "gated": item.get("gated", False),
            "likes": item.get("likes", 0),
            "downloads": item.get("downloads", 0),
            "updated_at": item.get("lastModified"),
            "task": item.get("pipeline_tag"),
            "sdk": item.get("sdk"),
            "library_name": item.get("library_name"),
            "tags": item.get("tags", []),
        })
    return sorted(normalized, key=lambda item: item["path"].casefold())


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    output = Path(sys.argv[1] if len(sys.argv) > 1 else "data/snapshots")
    github_token = os.getenv("GITHUB_TOKEN")
    hf_token = os.getenv("HF_TOKEN")
    snapshots = {
        "github_repositories.json": github_repositories(github_token),
        "huggingface_models.json": hf_repositories("models", hf_token),
        "huggingface_datasets.json": hf_repositories("datasets", hf_token),
        "huggingface_spaces.json": hf_repositories("spaces", hf_token),
    }
    for filename, payload in snapshots.items():
        write_json(output / filename, payload)
        print(f"Wrote {len(payload)} entries: {output / filename}")


if __name__ == "__main__":
    main()
