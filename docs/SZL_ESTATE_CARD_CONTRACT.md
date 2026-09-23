# SZL Estate Card Contract v1

## Purpose

Every public SZL GitHub README, Hugging Face model/dataset card, and Space landing surface must be attractive, technically legible, and evidence-bounded. This contract prevents visual polish from hiding missing provenance, a blocked state, or an unclear source of truth.

## Shared required sections

1. **Identity** — exact artifact name and one-sentence job.
2. **Status** — one allowed truth label, rendered as icon + text + color.
3. **What it does** — bounded, current capability.
4. **What it does not do** — material limits and excluded interpretations.
5. **Use or verify** — a runnable command, live path, or explicit `UNAVAILABLE` state.
6. **Evidence** — revision, receipt/evaluation/formal boundary, and limitations.
7. **Source of truth** — canonical GitHub, Hub, dataset, Space, or successor.
8. **Related artifacts** — only verified, live relationships.
9. **License and maintenance posture**.

## Allowed truth labels

`MEASURED`, `REPRODUCIBLE`, `SOURCE_BACKED`, `SOFTWARE`, `EXPERIMENTAL`, `ADVISORY`, `PROPOSAL_ONLY`, `REFERENCE`, `SYNTHETIC`, `BLOCKED`, `DEPRECATED`, `ARCHIVED`, `UNAVAILABLE`.

A truth label is not a release tier, safety claim, correctness claim, or authority grant.

## Artifact requirements

| Class | Additional required fields |
|---|---|
| Model | Base model; weight/config availability; intended use; eval state; limitations; artifact identity |
| Kernel | Not-a-model statement; install/import command; API surface; source/mirror boundary; evidence and test state |
| Dataset | Schema; data source; splits/config; license; PII/restriction posture; known gaps |
| Space | Source repository; runtime class; public capability; real effect boundary; fallback/unavailable behavior |
| GitHub repository | Canonical role; install/verify path; architecture relation; support posture; Hub/Space relation |
| Archive/alias | Historical reason; canonical successor; no ambiguous active-status language |

## Visual requirements

- Use only semantic SZL design tokens.
- Render status with icon, label, and color; never color alone.
- Preserve keyboard-visible focus and reduced-motion behavior.
- Put the identity/status/source path before historical detail.
- Keep command blocks executable and outside editorial callouts.
- Avoid generic AI imagery, misleading benchmark charts, or decorative proof language.

## Prohibited substitutions

```text
A receipt is not correctness.
A signature is not authority.
A formula is not authority.
A model card is not deployment certification.
A passing test is not production validation.
An archived artifact is not an active canonical source.
A Hub mirror is not automatically the source of truth.
```
