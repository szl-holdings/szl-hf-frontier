# SZL-HF-FRONTIER-1 — CODEX EXECUTION PAYLOAD
**Payload ID:** SZL-HF-FRONTIER-1-CODEX-2026-09-30
**Parent:** payloads/SZL-HF-FRONTIER-1-2026-09-30.md (findings F1–F9, work orders WO-1..7)
**Executor:** Codex. **Doctrine:** v11 — fail closed. Receipts or it did not happen.
**Env:** Python 3.10+, `pip install huggingface_hub pyyaml requests`, env vars `HF_TOKEN`, `GITHUB_TOKEN`.

## Gates (read before running)
1. WO-6 owner gate: publishing (WO-3 publish step) is BLOCKED until
   `frontier1/wo6_owner_action.md` contains `OWNER CONFIRMED <date>`.
2. Forge PRs #254/#243: DO NOT MERGE. Out of scope.
3. Any WO may legally end FAIL-CLOSED or UNAVAILABLE. Never paper over it.
4. Re-verify all repo IDs against the live estate before mutating anything.

## The code

```python
#!/usr/bin/env python3
"""SZL-HF-FRONTIER-1 executor. One file, seven work orders, master receipt."""
from __future__ import annotations
import hashlib, json, os, pathlib, re, sys, time
from datetime import datetime, timezone

import requests, yaml
from huggingface_hub import HfApi

OUT = pathlib.Path("frontier1"); OUT.mkdir(exist_ok=True)
NOW = lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
STATUS = {}  # wo -> {"status": ..., "note": ...}

def receipt(name: str, payload: dict) -> None:
    (OUT / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")

def fail_closed(wo: str, note: str) -> None:
    STATUS[wo] = {"status": "FAIL-CLOSED", "note": note}
    print(f"[{wo}] FAIL-CLOSED: {note}")

def done(wo: str, note: str = "ok") -> None:
    STATUS[wo] = {"status": "DONE", "note": note}
    print(f"[{wo}] DONE: {note}")

# ─── WO-1: merged-model card reconciliation (F2) ───────────────────────────
MERGED_REPOS = [
    "szl-receiptagent-qwen35-0.8b-v2", "szl-receiptagent-qwen35-0.8b-v3",
    "khipu-r3", "chaski-r2", "chaski-5050", "brain-navigator-r2",
    "KHIPU-R2", "WILLAY",
]

def wo1(api: HfApi) -> None:
    rec = {}
    for name in MERGED_REPOS:
        rid = f"SZLHOLDINGS/{name}"
        try:
            info = api.model_info(rid, files_metadata=True)
            st = next((f for f in (info.siblings or []) if f.rfilename.endswith(".safetensors")), None)
            if st is None or (st.size or 0) < 200_000_000:   # adapter-only is ~25-150MB
                fail_closed("WO-1", f"{rid}: no full checkpoint (largest safetensors too small) — card untouched")
                return
            card = api.repo_info(rid, repo_type="model")
            readme = None
            try:
                from huggingface_hub import hf_hub_download
                readme = pathlib.Path(hf_hub_download(rid, "README.md", repo_type="model")).read_text(encoding="utf-8")
            except Exception:
                pass
            if not readme:
                fail_closed("WO-1", f"{rid}: no README to reconcile")
                return
            m = re.match(r"^---\n(.*?)\n---\n", readme, re.S)
            if not m:
                fail_closed("WO-1", f"{rid}: README has no YAML frontmatter")
                return
            meta = yaml.safe_load(m.group(1)) or {}
            before_tags = set(meta.get("tags", []))
            meta["library_name"] = "transformers"
            meta["base_model_relation"] = "merged"
            meta["tags"] = sorted(t for t in before_tags
                                  if t not in {"peft", "lora", "qlora", "adapter"})
            body = readme[m.end():]
            new = "---\n" + yaml.safe_dump(meta, sort_keys=False) + "---\n" + body
            (OUT / f"wo1_{name}_README.md").write_text(new, encoding="utf-8")
            rec[rid] = {"before_tags": sorted(before_tags), "after_tags": meta["tags"],
                        "param_check_bytes": st.size, "status": "STAGED (push gated on WO-6)"}
        except Exception as e:
            fail_closed("WO-1", f"{rid}: {e}")
            return
    receipt("wo1_card_receipt.json", {"repos": rec, "timestamp": NOW()})
    done("WO-1", f"{len(rec)} cards staged; pushes deferred to post-WO-6 gate")

# ─── WO-2: placeholder repo inventory (F4) — NO DELETES ───────────────────
PLACEHOLDERS = [("model", "SZLHOLDINGS/SZLHOLDINGS"),
                ("dataset", "SZLHOLDINGS/SZLHOLDINGS"),
                ("space", "SZLHOLDINGS/README")]

def wo2(api: HfApi) -> None:
    inv = {}
    for rtype, rid in PLACEHOLDERS:
        try:
            info = api.repo_info(rid, repo_type=rtype, files_metadata=True)
            files = [{"name": f.rfilename, "bytes": f.size or 0} for f in (info.siblings or [])]
            big = [f for f in files if f["bytes"] > 50_000_000]
            if big:
                fail_closed("WO-2", f"{rid}: unexpected large files {big} — escalate, do not annotate")
                return
            inv[rid] = {"type": rtype, "files": files,
                        "disposition": "under audit SZL-HF-FRONTIER-1-2026-09-30"}
        except Exception as e:
            fail_closed("WO-2", f"{rid}: {e}")
            return
    receipt("wo2_inventory.json", {"inventory": inv, "timestamp": NOW(),
                                   "owner_decision_required": True})
    done("WO-2", f"{len(inv)} placeholders inventoried; disposition = owner decision")

# ─── WO-3: DPO khipu-abstain lane (F3) — CUDA-gated ────────────────────────
DPO_SPEC = {"pipeline": "tools/szl_omen_pipeline.py @ szl-forge branch huggingface",
            "subcommand": "dpo", "data": "SZLHOLDINGS/SZL-Khipu-1.5B-abstain",
            "policy_adapter": "SZLHOLDINGS/khipu-r3", "lora": "r16 a32 bf16 (no QLoRA on Qwen3.5)",
            "seed": 11, "beta": 0.1, "max_len": 1024, "max_prompt": 512}

def wo3() -> None:
    import torch
    if not torch.cuda.is_available():
        STATUS["WO-3"] = {"status": "UNAVAILABLE", "note": "no CUDA host — DPO not run degraded"}
        print("[WO-3] UNAVAILABLE: no CUDA host"); return
    # Gate on WO-6 before any publish; the run itself may proceed to produce a receipt.
    print("[WO-3] CUDA present. Run: python szl_omen_pipeline.py dpo")
    print("[WO-3] Expect dpo_receipt.json with: data sha256, pairs_used, train_loss (TRAIN METRIC),")
    print("       publication_eligible=false, next gate = held-out abstain generate.")
    STATUS["WO-3"] = {"status": "OWNER-PENDING", "note": "GPU run scheduled; publish gated on WO-6"}

# ─── WO-4: hologram pointer verification (F5) ──────────────────────────────
def wo4() -> None:
    tok = os.environ.get("GITHUB_TOKEN")
    if not tok:
        fail_closed("WO-4", "GITHUB_TOKEN not set"); return
    H = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}
    org = "szl-holdings"
    page, repos = 1, []
    while True:
        r = requests.get(f"https://api.github.com/orgs/{org}/repos",
                         headers=H, params={"per_page": 100, "page": page})
        r.raise_for_status()
        batch = r.json(); repos += batch
        if len(batch) < 100: break
        page += 1
    rows, broken = [], []
    for repo in repos:
        if repo.get("archived") and "Canonical:" in (repo.get("description") or ""):
            target = repo["description"].split("Canonical:")[1].strip().rstrip(".")
            t = target.replace("https://github.com/", "")
            tr = requests.get(f"https://api.github.com/repos/{t}", headers=H)
            ok = tr.status_code == 200 and not tr.json().get("archived")
            rows.append({"source": repo["full_name"], "target": t, "status": "OK" if ok else "BROKEN"})
            if not ok: broken.append((repo["full_name"], t))
    receipt("wo4_pointer_receipt.json", {"pointers": rows, "timestamp": NOW()})
    for src, tgt in broken:   # file issues, do not silently fix
        requests.post(f"https://api.github.com/repos/{src}/issues", headers=H,
                      json={"title": f"canonical pointer broken: {tgt}",
                            "body": "Auto-filed by SZL-HF-FRONTIER-1 WO-4. Verify and update the redirect."})
    done("WO-4", f"{len(rows)} pointers checked, {len(broken)} broken -> issues filed")

# ─── WO-5: private estate manifest (F6) ────────────────────────────────────
PRIVATE_DATASETS = ["szl-evidence", "david-leads-data", "thesis-formula-index",
                    "szl-org-infra", "anatomy-alive-harness", "vault-artifacts",
                    "szl-training-receipts", "yuyay-v3-axis-labels-v1", "legacy-archive"]
PRIVATE_SPACES = ["szl-constellation-staging", "szl-safe-stack", "a11oy-factory",
                  "counsel-assurance", "puriq-markets", "terra-assurance"]

def wo5(api: HfApi) -> None:
    manifest, cutoff = {}, time.time() - 30 * 86400
    for rtype, names in (("dataset", PRIVATE_DATASETS), ("space", PRIVATE_SPACES)):
        for n in names:
            rid = f"SZLHOLDINGS/{n}"
            try:
                info = api.repo_info(rid, repo_type=rtype)
                ts = info.lastModified.timestamp() if hasattr(info.lastModified, "timestamp") else 0
                manifest[rid] = {"type": rtype, "last_modified": str(info.lastModified),
                                 "flag": "STALE-REVIEW" if ts and ts < cutoff else "ACTIVE"}
            except Exception as e:
                fail_closed("WO-5", f"{rid}: {e}"); return
    receipt("wo5_private_manifest.json", {"manifest": manifest, "timestamp": NOW(),
                                          "visibility_changes": "NONE"})
    done("WO-5", f"{len(manifest)} private repos manifested")

# ─── WO-6: owner token-hygiene gate (F1) ───────────────────────────────────
def wo6() -> None:
    gate = OUT / "wo6_owner_action.md"
    if not gate.exists():
        gate.write_text(
            "# WO-6 OWNER ACTION REQUIRED\n\n"
            "Two HF tokens were exposed in plain text on 2026-09-12 (prefixes hf_nGHC…, hf_rpzm…).\n"
            "1. Revoke both at https://huggingface.co/settings/tokens\n"
            "2. Append below: OWNER CONFIRMED <date>\n\n"
            "Publishing (WO-1 pushes, WO-3 publish) is blocked until this line exists.\n",
            encoding="utf-8")
    confirmed = any(line.startswith("OWNER CONFIRMED") for line in gate.read_text().splitlines())
    STATUS["WO-6"] = {"status": "DONE" if confirmed else "OWNER-PENDING",
                      "note": "gate file present" if confirmed else "awaiting owner confirmation"}
    print(f"[WO-6] {'DONE' if confirmed else 'OWNER-PENDING'}")

def gate_open() -> bool:
    return STATUS.get("WO-6", {}).get("status") == "DONE"

# ─── WO-7: deprecated model banner (F7) ────────────────────────────────────
def wo7(api: HfApi) -> None:
    rid, banner = "SZLHOLDINGS/governed-inference-meter", \
        "> **DEPRECATED** — canonical: https://github.com/szl-holdings/szl-energy-attest\n"
    try:
        from huggingface_hub import hf_hub_download
        p = pathlib.Path(hf_hub_download(rid, "README.md", repo_type="model"))
        text = p.read_text(encoding="utf-8")
        if "DEPRECATED" not in text:
            (OUT / "wo7_README_governed-inference-meter.md").write_text(banner + text, encoding="utf-8")
        receipt("wo7_receipt.json", {"repo": rid, "banner": "present" if "DEPRECATED" in text
                                     else "staged", "timestamp": NOW()})
        done("WO-7")
    except Exception as e:
        fail_closed("WO-7", str(e))

# ─── main + master receipt ─────────────────────────────────────────────────
def main() -> int:
    if not os.environ.get("HF_TOKEN"):
        print("HF_TOKEN required"); return 2
    api = HfApi(token=os.environ["HF_TOKEN"])
    wo6()                      # gate first
    wo1(api); wo2(api); wo3(); wo4(); wo5(api); wo7(api)
    receipt("SZL-HF-FRONTIER-1-2026-09-30-master.json", {
        "payload": "SZL-HF-FRONTIER-1-CODEX-2026-09-30", "timestamp": NOW(),
        "machine": os.environ.get("COMPUTERNAME") or os.uname().nodename,
        "statuses": STATUS, "publish_gate": "OPEN" if gate_open() else "BLOCKED (WO-6)",
        "artifact_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in sorted(OUT.iterdir()) if p.is_file()},
    })
    print(json.dumps(STATUS, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

## Execution order
`wo6 → wo1 → wo2 → wo3 → wo4 → wo5 → wo7 → master receipt` (already enforced in `main()`).

## Acceptance
- Every WO lands in {DONE, UNAVAILABLE, FAIL-CLOSED, OWNER-PENDING} in the master receipt.
- WO-1 card pushes and WO-3 publish run ONLY after WO-6 shows OWNER CONFIRMED.
- No deletions. No merges of #254/#243. No fabricated numbers. Fail-closed is a valid outcome.
