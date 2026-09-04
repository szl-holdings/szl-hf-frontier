#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SZL HF Frontier payload — stdlib only. Fail closed. Never prints secrets.
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

HUB = "https://huggingface.co/api/models?author=SZLHOLDINGS&limit=100"
KERNEL_EXPECT = {
    "SZLHOLDINGS/szl-governed-norm",
    "SZLHOLDINGS/szl-kernels",
    "SZLHOLDINGS/szl-lambda-gate",
    "SZLHOLDINGS/szl-block-kv",
    "SZLHOLDINGS/szl-maskmod",
    "SZLHOLDINGS/szl-receipt-attn",
    "SZLHOLDINGS/szl-invariants",
    "SZLHOLDINGS/szl-blocked",
    "SZLHOLDINGS/governed-inference-meter",
    "SZLHOLDINGS/szl-govsign",
    "SZLHOLDINGS/szl-provctl",
    "SZLHOLDINGS/szl-ouroboros",
    "SZLHOLDINGS/szl-formulas",
    "SZLHOLDINGS/YARQA-ATTN",
    "SZLHOLDINGS/szl-khipu-kernels",
}
DO_NOT_PROMOTE = {
    "SZLHOLDINGS/chaski",
    "SZLHOLDINGS/chaski-5050",
    "SZLHOLDINGS/A11OY-MINI",
    "SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v3",
    "SZLHOLDINGS/SZL-Khipu-1.5B-abstain",
}
RETIRED = {"SZLHOLDINGS/governed-inference-meter": "szl-holdings/szl-energy-attest"}
C3 = ["szl-holdings/szl-lambda-gate", "szl-holdings/szl-governed-norm"]
C4 = [
    "szl-holdings/szl-blocked",
    "szl-holdings/szl-provctl",
    "szl-holdings/szl-formulas",
    "szl-holdings/szl-ouroboros",
    "szl-holdings/szl-nemo",
]


def get_json(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "szl-hf-frontier-payload"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    gh = bool(os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"))
    hf = bool(os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN"))
    report: dict = {
        "schema": "szl.hf-frontier-payload/v1",
        "observed_at": now,
        "lambda": "Conjecture 1",
        "gh_token_present": gh,
        "hf_token_present": hf,
        "status": "MEASURED",
    }
    try:
        models = get_json(HUB)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        report["status"] = "BLOCKED"
        report["reason"] = f"HUB_API_UNAVAILABLE:{type(exc).__name__}"
        print(json.dumps(report, indent=2))
        return 2
    if not isinstance(models, list):
        report["status"] = "BLOCKED"
        report["reason"] = "HUB_API_SHAPE"
        print(json.dumps(report, indent=2))
        return 2

    kernels = []
    traction = []
    for m in models:
        mid = m.get("id") or ""
        tags = m.get("tags") or []
        row = {
            "id": mid,
            "downloads": int(m.get("downloads") or 0),
            "likes": int(m.get("likes") or 0),
            "lastModified": m.get("lastModified"),
            "pipeline_tag": m.get("pipeline_tag"),
            "deprecated": "deprecated" in tags or "superseded" in tags,
            "do_not_promote": mid in DO_NOT_PROMOTE,
        }
        if "kernel" in tags or "kernels" in tags:
            kernels.append(row)
        if row["downloads"] >= 50 or mid in DO_NOT_PROMOTE:
            traction.append(row)

    seen = {k["id"] for k in kernels}
    report["kernels_observed"] = sorted(seen)
    report["kernels_missing_vs_ledger"] = sorted(KERNEL_EXPECT - seen)
    report["kernels_extra_vs_ledger"] = sorted(seen - KERNEL_EXPECT)
    report["retired_still_listed"] = [k for k in sorted(RETIRED) if k in seen]
    report["traction_sorted"] = sorted(traction, key=lambda r: -r["downloads"])
    report["orders"] = {
        "C3_clone": C3,
        "C4_clone": C4,
        "C6": ["szl-holdings/szl-blocked", "szl-holdings/szl-provctl"],
        "next": "Fix C3 tests or mark BLOCKED. Then strip pickle/joblib in C4. Do not promote Chaski.",
    }
    if not hf:
        report["hub_write"] = "UNAVAILABLE_NO_HF_TOKEN"
    if not gh:
        report["github_write"] = "UNAVAILABLE_NO_GH_TOKEN"

    out = "frontier-payload-report.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
        fh.write("\n")
    print(json.dumps(report, indent=2))
    print(f"\nWrote {out}", file=sys.stderr)
    print("Next: clone C3 repos, run pytest, PR fixes. Do not invent benches.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
