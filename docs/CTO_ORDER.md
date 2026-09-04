# CTO order — close the criticals, push the lanes

**ID:** `CTO-HF-FRONTIER-2026-09-04`  
**Issuer:** CTO, SZL Holdings  
**Payload:** `SZL-HF-FRONTIER-2026-08-29`  
**Strict result:** NOT READY until C1–C6 are closed.

## Standing order

Do not train new flagship weights until:

1. ReceiptAgent v3 is quarantined.
2. Khipu-abstain is repaired or relabelled.
3. `szl-lambda-gate` and `szl-governed-norm` stop publishing failed tests as if live.
4. Pickle/joblib surfaces are gone from Hub.
5. Chaski and A11OY-MINI are out of flagship collections.
6. `chaski-5050` no longer leaks owner-machine paths.

Then invest compute only in artifacts that earn promotion on a frozen hidden task.

## Owners

| Cluster | Canonical repo |
|---|---|
| C1, C2, C5, L1, L3 | `szl-holdings/szl-forge` |
| C3, C4, C6 | `szl-holdings/szl-kernels` |
| L2 | `szl-holdings/szl-khipu` |

Writes go through reviewed pull requests and controlled Hugging Face publication jobs. No silent Hub edits.
