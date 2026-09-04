#!/usr/bin/env python3
"""CTO payload — C1/C2/C5 Hub honesty. No token print. Fail closed.

Run from a machine that already has a write token:

    export HF_TOKEN=...   # or HF_ORG_TOKEN / HF_ORG_TOKEN1
    python3 tools/cto_hub_honesty_payload.py

Does not train. Does not invent benches. Does not add models to flagship.
"""
from __future__ import annotations

import os
import sys
from typing import Iterable

TOKEN_KEYS = (
    "HF_TOKEN",
    "HF_ORG_TOKEN1",
    "HF_ORG_TOKEN",
    "HF_WRITE_TOKEN",
    "HUGGINGFACE_TOKEN",
    "HUGGING_FACE_HUB_TOKEN",
)

BANNERS = {
    "SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v3": (
        "> **NON-RELEASE / PLACEHOLDER.** Not a ReceiptAgent tournament winner.\n"
        "> `publication_eligible=false`. `autonomy_eligible=false`.\n"
        "> Do not treat this ID as flagship. L1 on szl-hf-frontier is still open.\n\n"
    ),
    "SZLHOLDINGS/SZL-Khipu-1.5B-abstain": (
        "> **EXPERIMENT. Adapter bytes missing or unverified.**\n"
        "> Evaluators use `SZLHOLDINGS/SZL-Khipu-1.5B` until a receipted adapter exists.\n\n"
    ),
    "SZLHOLDINGS/chaski": (
        "> **RESEARCH / NEGATIVE EVIDENCE.** Failed qualification. Not flagship.\n"
        "> Later SKU `A11OY-MINI` inherits this failed parent. Not a product claim.\n\n"
    ),
    "SZLHOLDINGS/chaski-5050": (
        "> **QUARANTINE.** Research residue. Strip owner-machine absolute paths.\n"
        "> Not flagship. Not a production checkpoint.\n\n"
    ),
    "SZLHOLDINGS/A11OY-MINI": (
        "> **GGUF of a failed parent (chaski).** Not flagship. Not a11oy production.\n\n"
    ),
    "SZLHOLDINGS/governed-inference-meter": (
        "> **DEPRECATED.** Successor is GitHub `szl-holdings/szl-energy-attest`.\n"
        "> This Hub card is not operational energy evidence.\n\n"
    ),
}

JOBLIB_IDS = (
    "SZLHOLDINGS/szl-blocked",
    "SZLHOLDINGS/szl-provctl",
    "SZLHOLDINGS/szl-formulas",
    "SZLHOLDINGS/szl-ouroboros",
    "SZLHOLDINGS/szl-nemo",
)


def _token() -> str:
    for key in TOKEN_KEYS:
        raw = str(os.environ.get(key) or "").strip()
        if raw:
            return raw
    raise SystemExit("UNAVAILABLE: no HF_* token in environment")


def _prepend(readme: str, banner: str) -> str:
    if banner.strip() in readme:
        return readme
    if readme.startswith("---"):
        end = readme.find("\n---", 3)
        if end != -1:
            split = end + 4
            return readme[:split] + "\n\n" + banner + readme[split:].lstrip("\n")
    return banner + readme


def _siblings(api, repo_id: str) -> set[str]:
    info = api.repo_info(repo_id=repo_id, repo_type="model")
    return {s.rfilename for s in (info.siblings or [])}


def quarantine_joblib(api, repo_ids: Iterable[str]) -> list[str]:
    from huggingface_hub import CommitOperationDelete

    out = []
    for repo_id in repo_ids:
        try:
            info = api.repo_info(repo_id=repo_id, repo_type="model")
        except Exception as exc:
            out.append(f"MISSING {repo_id} {type(exc).__name__}")
            continue
        names = {s.rfilename for s in (info.siblings or [])}
        if "model.joblib" not in names:
            out.append(f"VERIFIED_CURRENT {repo_id}@{info.sha} no model.joblib")
            continue
        commit = api.create_commit(
            repo_id=repo_id,
            repo_type="model",
            operations=[CommitOperationDelete(path_in_repo="model.joblib")],
            commit_message="quarantine: remove model.joblib from approved path",
            create_pr=True,
            parent_commit=info.sha,
        )
        out.append(f"PR {repo_id} parent={info.sha} {commit}")
    return out


def stamp_banners(api) -> list[str]:
    out = []
    for repo_id, banner in BANNERS.items():
        try:
            text = api.hf_hub_download(
                repo_id=repo_id, filename="README.md", repo_type="model"
            )
            with open(text, encoding="utf-8") as handle:
                readme = handle.read()
        except Exception as exc:
            out.append(f"SKIP_READ {repo_id} {type(exc).__name__}")
            continue
        updated = _prepend(readme, banner)
        if updated == readme:
            out.append(f"ALREADY {repo_id}")
            continue
        api.upload_file(
            path_or_fileobj=updated.encode("utf-8"),
            path_in_repo="README.md",
            repo_id=repo_id,
            repo_type="model",
            commit_message="honesty: stamp NON-RELEASE / RESEARCH banner",
        )
        out.append(f"STAMPED {repo_id}")
    return out


def main() -> int:
    token = _token()
    from huggingface_hub import HfApi

    api = HfApi(token=token)
    identity = api.whoami()
    name = str((identity or {}).get("name") or "")
    print(f"whoami_ok name_len={len(name)}")
    for line in quarantine_joblib(api, JOBLIB_IDS):
        print(line)
    for line in stamp_banners(api):
        print(line)
    print("DONE fail-closed payload. Flagship collection edit is Hub UI or collections API.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
