# Massed Compute Write-Rail Doctrine v0.1 (DRAFT, owner ratification required)

Status: DRAFT_SEALED for ratification. Applies to every Massed Compute deployment act in the SZL estate. Nothing in this doc authorizes a write; it defines the only rails under which a write MAY be requested.

## Measured basis (2026-11-20)
- Bearer API key authorizes GET only. POST /deploy returns 307 to a login callback: the deploy write path is portal-session gated.
- No API spend visibility: the balance endpoint returns SPA HTML. Billing is visible only in the owner web console.
- Owner-set initial budget ceiling: $500-$2000 (owner tick 2026-11-20 ~22:25Z). A pasted API key is treated as read-only; it was pasted in chat and is exposure-compromised (rotation deferred by owner decision).

## Rail A (preferred): support-issued write-scoped, spend-capped API credential
Issued by Massed support to the owner, scoped to deploy/terminate only, with a hard spend cap at or below the owner ceiling and per-credential rate limits. Owner delivers it via the device secret file convention (dotfile, never chat, never printed, never in receipts). Executor use requires: (1) the ceiling number in the ratification sentence, (2) single-canary manifest hash, (3) watchdog terminate plus GET readback proof, (4) spend reconcile in the owner console within 24h of any create.

## Rail B (fallback): owner-in-browser deploy
The owner personally operates the portal session. Executor prepares the exact payload and the owner pastes it into the console GUI. No executor handling of cookies, sessions, exports, replays, or CDP automation of the owner session. Read-back verification still runs via GET API. Any deviation ends the deployment activity for the night.

## Spend controls (both rails)
1. Budget: no single canary beyond $10; no night beyond 10 percent of the owner ceiling without a fresh owner sentence.
2. Watchdog: every create carries a terminate deadline (canary T+50m hard cap) executed the moment evidence is captured.
3. Readback: 200 is not proof; termination is proven only by GET /instance readback showing the node absent.
4. Console check: the owner eyeballs the console billing line during every running minute of any deployed node.
5. Auto-recharge: recommendation on record to disable/limit the $25 auto-recharge during early canaries (owner decision pending).

## Evidence requirements
Request and response IDs, timestamps, payload hashes, readback snapshots, all sealed per receipt doctrine. MEASURED != PASS. Private evidence stays device-side unless the owner changes the publication doctrine.

## Explicit bans
- No CDP/session automation of the owner portal. No credential or cookie export or replay.
- No writes with the exposure-compromised read-only key.
- No touching the four running modelhost nodes.
- No bulk training, no K3, until the registry ratification and F5/A7/K1 ticks exist.

## Seat review (required fields)
- Astra review: ENDORSE (2026-11-20, dur 3.8s): deterministic + correct public-only fetch doctrine; cost: cold-residency with timed bursts only viable path under ceiling; integrity risk LOW.
- Sol witness: ENDORSE (2026-11-20, dur 8.5s): registry + cost findings endorsed; 401-fallback honest, prevents silent omission; watch triggers: unauthorized_spend, registry_drift, secret_exposure.
- Kimi handler adjudication: EXECUTE-tonight item Q1.3 of the 2026-11-20 get-it-all-done crew lap; this document is the receipt.

Ratification line (owner fills): I ratify this write-rail doctrine with ceiling $____ and single-canary manifest sha256 ____.
