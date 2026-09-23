# SZL Card Component Blueprints

These blueprints define component responsibilities, not a fixed visual layout.

## Status rail

**Inputs:** truth label, short qualifier, evidence link.

**Required behavior:** icon + text + color; no color-only state; wraps at mobile; exposes label to assistive technology.

## Evidence block

**Inputs:** source revision, evidence class, verification command or explicit unavailable reason, limitation.

**Required behavior:** factual statements only; long hashes use copy affordance and do not overflow at narrow widths.

## Source-of-truth panel

**Inputs:** canonical role, canonical URL, mirror URL if present, successor URL if archived/deprecated.

**Required behavior:** one canonical primary action; mirror and historical links are clearly subordinate.

## Command block

**Inputs:** executable command, prerequisites, expected bounded output, failure explanation.

**Required behavior:** commands remain outside narrative callouts; copyable; no secrets; no fabricated expected output.

## Relationship graph

**Inputs:** verified linked artifacts from estate registry.

**Required behavior:** distinguishes source, mirror, runtime, dataset, proof, and successor; does not infer unverified relations.

## Archive notice

**Inputs:** archive reason, canonical successor, historical boundary.

**Required behavior:** visually clear but non-alarmist; prevents the archive from being mistaken for an active source.

## Blocked/unavailable callout

**Inputs:** state, reason, next condition, related evidence.

**Required behavior:** block state is readable and dignified; never restyled as a generic error or hidden behind collapsed content.
