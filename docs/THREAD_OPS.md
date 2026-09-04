# Thread ops — ReceiptAgent v3 laptop lane

Status date: 2026-09-04.
Winner: null.
Flagship: false.
publicationEligible: false.
Estate: NOT READY.

This file operationalizes the 2026-09-04 laptop/frontier thread.
It does not promote a SKU. It does not disable the 80 C GPU trip.

## Destinations (do not merge jobs)

| Surface | Job | This thread |
|---|---|---|
| `szl-holdings/szl-hf-frontier` | Canonical ops / wave contracts | HOME |
| `szl-holdings/szl-forge` | Train kit (`frontier/qwen35-receiptagent-v3`) | TRAIN |
| `huggingface.co/SZLHOLDINGS` | Artifact registry | Honesty banners only. v3 stays NON-RELEASE. No new flagship Space. |
| `a11oy.net` | Proof / RECORD | Optional pointer. Kernel is not run here. |
| `a-11-oy.com` | Product command center | Not the home for an untrained adapter. |
| `a11oy.com` | Unrelated storefront | Never |

Hub is not the front door. Do not publish a Grok Build SPA as a fourth public origin.

## MEASURED from the owner laptop paste (WSL Ubuntu / rosie)

- GPU: NVIDIA GeForce RTX 5050 Laptop GPU
- `torch.cuda.is_available()`: True
- Unsloth: OK in `~/venv-ra-v3`
- Forge HEAD at setup: `9b1f8ae75da2075d5a45997b9a19b17b799e1f65`
- This chat sandbox: BLOCKED_NO_METAL

Smoke and full have not been MEASURED in this thread.

## Contracts that stay locked

- `candidate.json` `maximum_gpu_temperature_c`: 80
- Python path the launcher expects: `/home/rosie/.venvs/szl-unsloth/bin/python`
- Base: `unsloth/Qwen3.5-0.8B` @ `23c69c53358a07516b5827588b3fdb12ae78fd65`
- smoke = 1 optimizer step (not a qualified adapter)
- full = 135 steps (still not flagship)
- L1 winner stays null without sample-level GMB logs
- L2 operating_point stays null
- L3 collection stays research-only
- Lambda aggregate stays BLOCKED / Conjecture 1

## Next operator step

Run `LAPTOP_PAYLOAD.md` on the 5050 WSL box as user `rosie`.
Do not git add weights, GGUF, PEM, or outputs.
