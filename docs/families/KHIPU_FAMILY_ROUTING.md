# Khipu family canonical routing

**Audit source:** `szl-holdings/szl-forge` source and public Hub cards

## Canonical graph

```text
szl-forge/khipu/ source and harness
        ↓
SZLHOLDINGS/SZL-Khipu-1.5B
signed research baseline · MEASURED_RESEARCH_ONLY
        ↓
SZLHOLDINGS/SZL-Khipu-1.5B-GGUF
derived local-runtime quantizations · not signed checkpoint
        ↓
SZLHOLDINGS/szl-model-inference-lab
bounded CPU demonstration pinned to exact GGUF revision and hash
```

## Roles

| Artifact | Registry class | Public role | Promotion boundary |
|---|---|---|---|
| `SZL-Khipu-1.5B` | Model | Signed research baseline | Autonomous/high-stakes use prohibited; owner-run abstention is 2/6 |
| `SZL-Khipu-1.5B-GGUF` | Derived model | Local llama.cpp/Ollama/LM Studio runtime | LFS hash identifies quant bytes; signed evaluation does not cover post-quant behavior |
| `szl-model-inference-lab` | Space | Bounded CPU demonstration | Demonstration is not a governed production endpoint |
| `KHIPU-R2` | Model | Separate candidate SKU | `publication_eligible: false`; never overwrites baseline |
| `SZL-Khipu-1.5B-abstain` | Experiment | Quarantined candidate | Adapter bytes missing or unverified; not evaluation baseline |

## Non-duplication rules

```text
No candidate may overwrite SZL-Khipu-1.5B.
No GGUF card may claim to be the signed checkpoint.
No local demonstration may claim production runtime authority.
No candidate result may replace the baseline 2/6 abstention result.
No KHIPU-R2 or abstain experiment may be presented as a promoted successor.
```

## Card routing

- Base model card: source, evidence, controller boundary, research-use limitation.
- GGUF card: parent model, exact quant hash, local run path, post-quant evaluation limit.
- Candidate card: separate SKU, experiment status, qualification boundary, no-overwrite rule.
- Space card: pinned artifact, bounded capability, runtime and authority limits.

## Source facts to retain

- Base source is `szl-holdings/szl-forge/khipu/`.
- The base model is `MEASURED_RESEARCH_ONLY`; its held-out abstention is 2/6.
- KHIPU-R2 remains separately identified, publication-ineligible, and non-overwriting.
- The abstain experiment remains unverified/empty until receipted adapter bytes exist.
- The GGUF local runtime is derivative-only and must retain its parent/evidence distinction.
