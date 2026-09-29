# Retained historical audit and reconciliation

This directory preserves the September 24, 2026 public census (224 artifacts), its immutable evidence bytes, and the subsequent source/model review. Internal paths are relative to this evidence root so their original hashes remain verifiable. This is historical evidence, not the current estate inventory or current deployment status. The latest committed public census remains at the repository root under `data/` and `reports/`.

The source review records 89 resolved source findings and 268 remaining findings. Model witnesses cover bounded synthetic execution, artifact bytes, or software behavior at the recorded revisions. They do not establish training reproduction, independent evaluation, production qualification, or current provider parity. Original reports remain unchanged, including statements subsequently superseded by later release receipts.

From the repository root:

```console
python tools/reconcile_estate.py --root examples/estate-audit-20260924 --check
python tools/verify_model_reconciliation.py --root examples/estate-audit-20260924
```

The executable tools and adversarial tests live at the repository root. The retained `reports/executed_sources/` files record the original audit execution and are not active application entry points.
