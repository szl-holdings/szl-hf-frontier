#!/usr/bin/env python3
"""Run a read-only estate audit, retaining honest stage and gap outcomes."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.capture_estate_snapshots import (  # noqa: E402
    CollectionError, capture, export_public_snapshot, sha256, utc_now, verify_snapshot_set, write_json,
)


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-capture", action="store_true", help="Verify and compile existing receipt-bound snapshots without network calls.")
    parser.add_argument("--public-only", action="store_true", help="Explicit anonymous capture when not skipping capture.")
    parser.add_argument("--snapshots", type=Path, default=ROOT / "data/snapshots")
    parser.add_argument("--raw-snapshots", type=Path, default=ROOT / ".estate-private/snapshots", help="Ignored local authenticated census; used when refreshing committed public snapshots.")
    parser.add_argument("--registry", type=Path, default=ROOT / "data/estate_registry.json")
    parser.add_argument("--gaps", type=Path, default=ROOT / "reports/unresolved_gaps.json")
    parser.add_argument("--receipt", type=Path, default=ROOT / "reports/estate_audit_receipt.json")
    parser.add_argument("--reviews", type=Path)
    args = parser.parse_args(argv)
    for field in ("snapshots", "raw_snapshots", "registry", "gaps", "receipt", "reviews"):
        value = getattr(args, field)
        if value is not None:
            setattr(args, field, value.resolve())
    receipt = {"schema": "szl.estate-audit-receipt/v1", "started_at": utc_now(), "complete": False, "status": "IN_PROGRESS", "signature_status": "UNSIGNED", "stages": {}, "outputs": {}, "publication_authorized": False}
    write_json(args.receipt, receipt)
    code = 1
    try:
        if not args.skip_capture:
            committed = args.snapshots == (ROOT / "data/snapshots").resolve()
            if committed and args.public_only:
                raise CollectionError("COMMITTED_SNAPSHOT_REQUIRES_AUTHENTICATED_PUBLIC_PROJECTION")
            observation = capture(args.raw_snapshots if committed else args.snapshots, public_only=args.public_only)
            receipt["stages"]["capture"] = "COMPLETE" if observation["complete"] else "FAILED"
            if not observation["complete"]:
                raise CollectionError("CAPTURE_FAILED")
            if committed:
                export_public_snapshot(args.raw_snapshots, args.snapshots)
        else:
            receipt["stages"]["capture"] = "SKIPPED_EXISTING_SNAPSHOTS"
        snapshot = verify_snapshot_set(args.snapshots)
        if snapshot.get("scope") == "TOKEN_VISIBLE":
            private_root = ROOT.resolve() / ".estate-private"
            for path in (args.registry, args.gaps, args.receipt):
                if path.is_relative_to(ROOT.resolve()) and not path.is_relative_to(private_root):
                    raise CollectionError("PRIVATE_INPUT_REQUIRES_LOCAL_OUTPUTS")
        receipt["snapshot_receipt_sha256"] = sha256(args.snapshots / "snapshot_receipt.json")
        receipt["snapshot_scope"] = snapshot["scope"]
        receipt["stages"]["snapshot_integrity"] = "VERIFIED_UNSIGNED"
        command = ["tools/build_estate_registry.py", "--input", str(args.snapshots), "--registry", str(args.registry), "--gaps", str(args.gaps)]
        if args.reviews:
            command += ["--reviews", str(args.reviews)]
        built = run(*command)
        build_log = args.receipt.with_suffix(".build.log")
        build_log.write_text(built.stdout + built.stderr, encoding="utf-8")
        receipt["outputs"]["build_log"] = {"sha256": sha256(build_log)}
        receipt["stages"]["build"] = "COMPLETE" if built.returncode == 0 else "FAILED"
        if built.returncode:
            raise CollectionError("REGISTRY_BUILD_FAILED")
        registry = json.loads(args.registry.read_text(encoding="utf-8"))
        gaps = json.loads(args.gaps.read_text(encoding="utf-8"))
        unresolved = gaps["unresolved_gaps"]
        receipt["artifact_count"] = len(registry)
        receipt["unresolved_gap_count"] = len(unresolved)
        receipt["high_gap_count"] = sum(item.get("severity") == "high" for item in unresolved)
        receipt["unreviewed_count"] = sum(item.get("audit", {}).get("status") == "UNREVIEWED" for item in registry)
        for name, path in (("registry", args.registry), ("gaps", args.gaps)):
            receipt["outputs"][name] = {"sha256": sha256(path)}
        validated = run("validators/validate_estate_registry.py", str(args.registry))
        receipt["stages"]["registry_validation"] = "PASSED" if validated.returncode == 0 else "BLOCKED"
        # Validator logs may identify private artifacts. Retain locally without
        # echoing raw subprocess output to terminal transcripts.
        log = args.receipt.with_suffix(".validation.log")
        log.write_text(validated.stdout + validated.stderr, encoding="utf-8")
        receipt["outputs"]["validation_log"] = {"sha256": sha256(log)}
        blocked = bool(validated.returncode or unresolved or receipt["unreviewed_count"])
        receipt.update(complete=True, status="BLOCKED_GAPS" if blocked else "AUDIT_PASSED")
        code = 2 if blocked else 0
    except CollectionError as exc:
        receipt.update(status="FAILED", failure=str(exc))
    except Exception:
        receipt.update(status="FAILED", failure="AUDIT_INTERNAL_ERROR")
    receipt["completed_at"] = utc_now()
    write_json(args.receipt, receipt)
    print(f"{receipt['status']}: capture/integrity/build/validation outcomes retained; publication_authorized=false")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
