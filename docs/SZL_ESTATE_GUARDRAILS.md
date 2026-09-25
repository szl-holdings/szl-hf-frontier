# SZL Estate Guardrails v1

## Duplicate-prevention rule

The estate registry is **one record per public identity**. The validator rejects:

- Duplicate registry IDs.
- Duplicate canonical owners for an active source, runtime, record, or successor URL.
- Duplicate active canonical identities.
- Duplicate active GitHub-to-Hugging-Face mirror pairs.
- Archived or deprecated records without an explicit successor.

Shared reference links are allowed. Many artifacts may correctly reference the same organization page, proof corpus, evidence lake, or product surface. A shared reference does not create shared canonical ownership.

An archive, alias, fixture, or historical record may preserve provenance, but it may never masquerade as a second active canonical artifact.

## Gates

A public artifact may not move to `ALIGNED_*` unless all relevant gates pass.

| Gate | Fail condition |
|---|---|
| Registry | Missing ID, class, visibility, truth status, canonical role/URL, or audit status |
| Duplicate prevention | Reused active canonical ownership, canonical identity, or live mirror pair |
| Canonical route | Missing source of truth; archived/deprecated artifact without successor |
| Link integrity | Missing or malformed GitHub/Hub/Space/dataset relation |
| Card contract | Missing identity, status, what-it-is, what-it-is-not, use/verify, evidence, source, or maintenance posture |
| Truth language | Claims prohibited by doctrine or unsupported by the artifact state |
| Accessibility | Status conveyed only with color; invisible focus; missing alt text; non-semantic heading order; motion without reduction path |
| Visual regression | Unreviewed screenshot difference in a required state or viewport |

## Required visual states

`DEFAULT`, `HOVER`, `FOCUS_VISIBLE`, `MEASURED`, `SOFTWARE`, `EXPERIMENTAL`, `ADVISORY`, `BLOCKED`, `UNAVAILABLE`, `ARCHIVED`, `MOBILE`, `REDUCED_MOTION`.

## Required viewport matrix

| Name | Width |
|---|---:|
| Mobile | 360 px |
| Tablet | 768 px |
| Desktop | 1280 px |
| Wide | 1600 px |

## Ouroboros closure

The estate loop closes only after:

1. A fresh GitHub and Hugging Face enumeration contains no unregistered public artifact.
2. Every registered artifact has a resolved audit status.
3. No `NEEDS_*` item remains without an owner and explicit reason.
4. All changed public cards pass the contract, duplicate-prevention, link, accessibility, and visual gates.
5. A post-change re-enumeration detects no orphan, stale successor, duplicate canonical ownership, or new ambiguity.

A visually attractive page does not bypass any gate.