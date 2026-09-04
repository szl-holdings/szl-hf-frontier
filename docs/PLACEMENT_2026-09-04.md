# Placement — thread operational surface

As of 2026-09-04.

## Where this thread lives

| Surface | Role | Decision |
|---|---|---|
| GitHub `szl-holdings/szl-hf-frontier` | Source of the proof loop, payloads, CI selftest | **HOME** |
| GitHub `szl-holdings/hatun-mcp` | MCP bus + Second Brain / Anatomy adapters | Already merged `#107` |
| [a11oy.net](https://a11oy.net) | Proof registry. Records, atlas, ROADMAP | **PROOF** |
| [a-11-oy.com](https://a-11-oy.com) | Product runtime. Do not dump this thread as a new product | **PRODUCT** |
| Hugging Face `SZLHOLDINGS` | Artifact mirror. Existing Spaces only | **NOT FLAGSHIP** |

## Why not a new Hub Space

Flagship stays empty. Winner stays null. Ready stays false.
A new Space would look like a product. This thread is a proof contract.

## Run

```bash
python3 payloads/SZL_HATUN_ORGAN_BUS.py
```

Expect `selftest: true`, `ready: false`, `winner: null`.
No Hub PUT from these files.
