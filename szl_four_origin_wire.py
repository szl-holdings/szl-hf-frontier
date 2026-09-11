#!/usr/bin/env python3
"""SZL four-origin wire — GitHub source, Hub mirror, product, proof.

GET/HEAD only. Fail closed. Never writes Hub, DNS, or product state.
Never promotes a model. Never upgrades MODELED to MEASURED.

Payload: SZL-FOUR-ORIGIN-WIRE-2026-09-11
Parent: SZL-HF-FRONTIER-2026-08-29
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

PAYLOAD = "SZL-FOUR-ORIGIN-WIRE-2026-09-11"
PARENT = "SZL-HF-FRONTIER-2026-08-29"
HF_ORG = "SZLHOLDINGS"
GH_ORG = "szl-holdings"
PRODUCT = "https://a-11-oy.com"
PROOF = "https://a11oy.net"
NEVER = "https://a11oy.com"
EXPECTED_PUBLIC = {"models": 46, "datasets": 35, "spaces": 21}
UA = "szl-four-origin-wire/2026-09-11 (+https://github.com/szl-holdings/szl-hf-frontier)"
CTX = ssl.create_default_context()
TIMEOUT = 15


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get(url: str, accept: str = "*/*") -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=CTX) as resp:
            raw = resp.read()
            headers = {k.lower(): v for k, v in resp.headers.items()}
            ctype = headers.get("content-type", "")
            if "json" in ctype:
                try:
                    body: Any = json.loads(raw.decode("utf-8", "replace"))
                except json.JSONDecodeError:
                    body = raw.decode("utf-8", "replace")[:400]
            else:
                text = raw.decode("utf-8", "replace")
                body = text if len(text) <= 400 else text[:400]
            return {
                "ok": 200 <= resp.status < 300,
                "status": resp.status,
                "url": url,
                "server": headers.get("server"),
                "x_szl_space": headers.get("x-szl-space"),
                "x_szl_wire_d": headers.get("x-szl-wire-d"),
                "content_type": ctype,
                "bytes": len(raw),
                "body": body,
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "url": url, "server": None, "x_szl_space": None, "x_szl_wire_d": None, "content_type": None, "bytes": 0, "body": None, "error": f"HTTPError {exc.code}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": None, "url": url, "server": None, "x_szl_space": None, "x_szl_wire_d": None, "content_type": None, "bytes": 0, "body": None, "error": f"{type(exc).__name__}: {exc}"}


def _hub_count(kind: str) -> dict[str, Any]:
    row = _get(f"https://huggingface.co/api/{kind}?author={HF_ORG}&limit=200", accept="application/json")
    if row["ok"] and isinstance(row["body"], list):
        row["count"] = len(row["body"])
        row["body"] = f"list[{row['count']}]"
    else:
        row["count"] = None
    return row


def probe_product() -> dict[str, Any]:
    honest = _get(f"{PRODUCT}/api/a11oy/v1/honest", accept="application/json")
    health = _get(f"{PRODUCT}/api/a11oy/healthz", accept="application/json")
    signing = _get(f"{PRODUCT}/api/a11oy/v1/signing-status", accept="application/json")
    apex = _get(f"{PRODUCT}/")
    verify = _get(f"{PRODUCT}/verify")
    console = _get(f"{PRODUCT}/console")
    cosign = _get(f"{PRODUCT}/cosign.pub")
    www = _get("https://www.a-11-oy.com/")
    spectral = _get(f"{PRODUCT}/spectral")
    controller = _get(f"{PRODUCT}/controller")
    git_sha = doctrine = signer = None
    if isinstance(honest.get("body"), dict):
        git_sha = honest["body"].get("git_sha")
        doctrine = (honest["body"].get("doctrine_lock") or {}).get("doctrine")
    if isinstance(health.get("body"), dict):
        signer = ((health["body"].get("rollup") or {}).get("signer") or {}).get("status")
        if signer is None:
            signer = (health["body"].get("signer") or {}).get("status")
    return {
        "origin": PRODUCT,
        "apex_ok": apex["ok"],
        "wire_d": apex.get("x_szl_wire_d"),
        "space": apex.get("x_szl_space"),
        "honest_ok": honest["ok"],
        "git_sha": git_sha,
        "doctrine": doctrine,
        "health_ok": health["ok"],
        "signer": signer,
        "signing_ok": signing["ok"],
        "verify_ok": verify["ok"],
        "console_ok": console["ok"],
        "cosign_ok": cosign["ok"],
        "www": {"ok": www["ok"], "error": www["error"], "status": www["status"]},
        "spectral": {"ok": spectral["ok"], "status": spectral["status"]},
        "controller": {"ok": controller["ok"], "status": controller["status"]},
    }


def probe_proof() -> dict[str, Any]:
    apex = _get(f"{PROOF}/")
    return {
        "origin": PROOF,
        "apex_ok": apex["ok"],
        "record_ok": _get(f"{PROOF}/record/")["ok"],
        "estate_ok": _get(f"{PROOF}/estate/")["ok"],
        "refresh_ok": _get(f"{PROOF}/estate-refresh-2026-09-11.json", accept="application/json")["ok"],
        "server": apex.get("server"),
        "never": NEVER,
    }


def probe_hub() -> dict[str, Any]:
    models, datasets, spaces = _hub_count("models"), _hub_count("datasets"), _hub_count("spaces")
    observed = {"models": models.get("count"), "datasets": datasets.get("count"), "spaces": spaces.get("count")}
    return {
        "org": HF_ORG,
        "expected_public_anonymous": EXPECTED_PUBLIC,
        "observed_public_anonymous": observed,
        "anonymous_inventory_match": observed == EXPECTED_PUBLIC,
        "note": "Anonymous author membership is a different scope from Series-A status counts.",
    }


def selftest() -> dict[str, Any]:
    checks = {
        "payload_locked": PAYLOAD.startswith("SZL-FOUR-ORIGIN-WIRE-"),
        "never_a11oy_com": NEVER == "https://a11oy.com",
        "two_origins": PRODUCT.endswith("a-11-oy.com") and PROOF.endswith("a11oy.net"),
        "expected_is_int": all(isinstance(v, int) for v in EXPECTED_PUBLIC.values()),
    }
    return {"ok": all(checks.values()), "checks": checks}


def report(self_row: dict[str, Any], live_row: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "payload": PAYLOAD,
        "parent": PARENT,
        "captured_at": _now(),
        "evidence_class": "MEASURED" if live_row else "SELFTEST",
        "lambda": "Conjecture 1",
        "doctrine": "v11",
        "origins": {
            "source": f"https://github.com/{GH_ORG}",
            "mirror": f"https://huggingface.co/{HF_ORG}",
            "product": PRODUCT,
            "proof": PROOF,
            "never": NEVER,
        },
        "selftest": self_row,
        "live": live_row,
        "alignment": {
            "product_honesty_reachable": bool(live_row and live_row.get("product", {}).get("honest_ok")),
            "proof_reachable": bool(live_row and live_row.get("proof", {}).get("apex_ok")),
            "hub_anonymous_inventory_match": bool(live_row and live_row.get("hub", {}).get("anonymous_inventory_match")),
            "www_tls": (live_row or {}).get("product", {}).get("www", {}).get("ok"),
            "spectral_controller": "UNAVAILABLE",
        },
        "winner": None,
        "ready": False,
        "bounds": [
            "HTTP 200 is reachability, not quality.",
            "DSSE-LIVE on /api/a11oy/healthz is not Lean /healthz mint.",
            "Anonymous Hub counts are not Series-A command-plane counts.",
            "This script does not write Hugging Face, DNS, or GitHub runtime state.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if not args.selftest and not args.live:
        args.selftest = True
        args.live = True
    self_row = selftest()
    live_row = None
    if args.live:
        live_row = {"product": probe_product(), "proof": probe_proof(), "hub": probe_hub()}
    payload = report(self_row, live_row)
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    if not self_row["ok"] or payload["winner"] is not None or payload["ready"] is True:
        return 2
    if args.live:
        if not live_row["product"].get("honest_ok"):
            print("REFUSED: product honesty endpoint not reachable", file=sys.stderr)
            return 2
        if not live_row["proof"].get("apex_ok"):
            print("REFUSED: proof origin not reachable", file=sys.stderr)
            return 2
        if not live_row["hub"].get("anonymous_inventory_match"):
            print("HOLD: anonymous Hub inventory drifted from expected 46/35/21", file=sys.stderr)
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
