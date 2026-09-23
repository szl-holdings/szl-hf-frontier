# SZL Enterprise Design-System Operating Model

## Purpose

This document converts publicly documented practices from mature enterprise design systems into original SZL operating controls. It does not copy another organization’s visual identity, components, assets, wording, or trade dress.

## Pattern extraction

| Source pattern | SZL implementation |
|---|---|
| Atlassian: foundations, components, tools, and patterns | One token source, card contracts, validators, and artifact-specific templates |
| Shopify: one home, many doors; eliminate redundant content | One canonical artifact record with verified GitHub/Hub/Space/dataset links; no duplicated canonical pages |
| Workday: community-visible component system with visual-regression and accessibility review | Versioned standards, reviewable diffs, screenshot baselines, accessibility gates, and changelog discipline |
| Material: tokens shared across design, code, tools, and platforms; explicit component states | Semantic tokens, required status variants, viewport fixtures, and state matrix |
| Fluent: global primitive tokens plus semantic alias tokens; adaptive accessibility | Primitive values never used directly in product surfaces; aliases carry role, contrast, theme, and state meaning |
| Salesforce: component blueprints, styling hooks, accessible patterns, controlled customization | SZL component/card blueprints; semantic hooks; approved extension points; no arbitrary hard-coded overrides |

## Layered architecture

```text
Layer 0: Truth
  Artifact registry, source-of-truth, revision, license, status, evidence boundary.

Layer 1: Foundations
  Primitive color/spacing/type/motion values plus semantic aliases.

Layer 2: Components
  Status rail, evidence block, source-of-truth panel, command block, relation graph,
  archive notice, warning/blocked callout, mobile navigation.

Layer 3: Templates
  Model card, kernel card, dataset card, Space landing surface, GitHub README,
  archive/alias route, organization profile.

Layer 4: Guardrails
  Schema, duplicate prevention, card contract, links, truth language, accessibility,
  visual regression, responsive fixtures.

Layer 5: Release
  Reviewable change plan, dry run, explicit approval, mutation, re-enumeration,
  proof report, drift watch.
```

## Required developer workflow

1. Register or update an artifact record before changing a public surface.
2. Declare source of truth, class, visibility, truth status, canonical route, and relations.
3. Select the correct card template; do not clone another artifact's card blindly.
4. Consume semantic tokens and shared component primitives only.
5. Add or update fixtures for required status and viewport states.
6. Run registry, duplicate, link, card, accessibility, and visual checks locally.
7. Submit a reviewable diff with before/after screenshots and claim-boundary notes.
8. Require approval for public mutation.
9. Re-run all checks after mutation; retain the result in the estate proof report.

## Required reviewer workflow

### Developer review

- Is the source route correct and revision-pinned where appropriate?
- Do commands match actual install/import/runtime behavior?
- Is the public API and artifact class accurately described?
- Are links live, non-duplicated, and canonically routed?
- Do validation, accessibility, and visual tests pass?

### Investor review

- Is the job and business relevance clear within the first screen?
- Does the status language make the maturity/evidence boundary obvious?
- Is the proof path visible without reading implementation detail?
- Are the product, research, reference, and archive roles visibly distinct?
- Does the page avoid invented performance, deployment, or authority claims?

## Required test matrix

| Dimension | Required cases |
|---|---|
| Status | DEFAULT, MEASURED, SOFTWARE, EXPERIMENTAL, ADVISORY, BLOCKED, UNAVAILABLE, ARCHIVED |
| Interaction | default, hover, focus-visible, disabled where applicable |
| Viewport | 360, 768, 1280, 1600 px |
| Motion | default and prefers-reduced-motion |
| Theme | dark and light when the surface supports both |
| Accessibility | keyboard path, focus, semantic headings, alt text, contrast, non-color status cue |

## Release gates

```text
G0 Registry record exists and validates.
G1 No duplicate canonical identity, public URL, or mirror pair exists.
G2 Source/mirror/successor routes validate.
G3 Card contract passes for the artifact class.
G4 Truth-language scan passes.
G5 Accessibility checks pass or an explicit documented exception blocks release.
G6 Visual regression diff is reviewed and approved.
G7 Developer and investor review paths are complete.
G8 Post-mutation re-audit passes.
```

No aesthetic preference overrides G0-G8.

## No-bandaid rules

- Do not use an image to conceal missing documentation.
- Do not use a badge to conceal an unresolved status.
- Do not duplicate a card when a canonical route exists.
- Do not convert a `BLOCKED`, `UNAVAILABLE`, `ARCHIVED`, or `EXPERIMENTAL` state into a visual green light.
- Do not represent model cards, receipts, formulas, or tests as authority.
- Do not merge a local visual pass into a public claim of hosted production validation.

## Ouroboros operation

```text
Enumerate -> register -> classify -> relate -> validate -> design -> review
-> mutate -> re-enumerate -> compare -> resolve drift -> repeat.
```

The loop is complete only when every public artifact is registered, resolved, and passes its relevant release gates.