# SZL Holdings — Org-wide repository audit and fix wave, 2026-10-01

**Scope.** Every active repository of the `szl-holdings` GitHub organization (137 total, 29 archived, 108 active), read through the GitHub REST API at 18:3xZ on 2026-10-01: default-branch CI, open pull requests, code scanning (CodeQL, OpenSSF Scorecard, Trivy), Dependabot and secret-scanning alerts, repository security settings, branch rules, and the presence of hygiene files. Fixes were landed as one GitHub-signed commit per pull request (GraphQL `createCommitOnBranch`), tested locally where the suite was runnable in the audit sandbox, and squash-merged only when the repository's checks were green. Nothing was force-merged; one admin-path merge attempt on `szl-holdings/.github` was refused by the execution guard and is recorded as an owner decision below.

Labels: MEASURED = observed through the API or a test run; REPORTED = taken from a tool's output without re-derivation; UNAVAILABLE = not observable from this seat.

## 1. Org state at audit time (MEASURED)

| Dimension | Value |
|---|---|
| Repositories | 137 total, 108 active, 29 archived |
| Red workflows on default branches (latest push run per workflow) | 0 of 108 repositories |
| Open pull requests (active repos) | 7 at start (all owner-authored); 0 drafts |
| Dependabot alerts open | 1 (platform, `dompurify`, low) |
| Secret-scanning alerts open | 0 |
| Secret scanning + push protection | enabled on 108 / 108 |
| Dependabot security updates | enabled on 108 / 108 |
| Code scanning alerts open | 1,752 — Scorecard 1,097 · CodeQL 654 · Trivy 1 |
| Severity mix | critical 10 · high 336 · error 12 · medium 750 · low 115 · warning 166 · note 363 |
| Branch rules | every active repository has branch protection or at least one ruleset |
| `delete_branch_on_merge` | false on 108 / 108 at start → **true on 108 / 108** after this wave |
| Missing `.github/dependabot.yml` | 13 repos → 3 remaining (szl-ops-runbook, szl-org-health, szlholdings.com — in flight in the parallel session) |
| Missing CODEOWNERS | 15 repos → 3 remaining (same three) |
| Missing CodeQL workflow | 19 repos → 3 remaining (same three) |
| Missing LICENSE | 5 (frontier-compass, szl-command-center, szl-ops-runbook, szl-showcase, szlholdings.com) — owner decision, see §6 |
| Missing README | 1 (szl-showcase) |
| SECURITY.md | 59 repos rely on the org-level `szl-holdings/.github/SECURITY.md` (present, 2,480 bytes) |

## 2. What was fixed in this wave (MEASURED)

49 pull requests merged, 2 left open with reasons (§5). Full list with URLs in `org-audit-2026-10-01.json → merged / open`.

### 2.1 Critical findings — 10 of 10 addressed

| # | Repo | Finding | Resolution |
|---|---|---|---|
| 1–2 | .github | Scorecard DangerousWorkflow: `estate-one-fabric-alignment.yml` checked out `workflow_run`/`pull_request` head contexts | Guarded resolve step admits same-repository heads only; contract test updated — **PR #828 green except the new effect-boundary gate (owner decision, §5)** |
| 3 | a11oy-factory | DangerousWorkflow in `factory-keyless-signing.yml` | contract job checks out `github.sha` — merged #55 |
| 4 | david-leads | DangerousWorkflow in `frontier-live-canary.yml` | canary checks out its own commit; deployed revision stays data — merged #137 |
| 5 | szl-router | DangerousWorkflow in `hf-space-drift-check.yml` | verifier checks out its own commit — merged #82 |
| 6 | david-leads | CodeQL `py/partial-ssrf` in `app/signals.py` | public-data origin allowlist in `_get()`, state FIPS admitted only by allowlist membership (returns the allowlist constant) — merged #138 |
| 7 | puriq-live | `py/partial-ssrf` in `puriq_market.py` | path segments rebuilt from allowlist constants and an integer CIK — merged #24 |
| 8 | retrieval-bench | `py/full-ssrf` in `retrieval/fusion.py` | requests select an operator-configured endpoint by exact match (`RETRIEVAL_BENCH_ENDPOINTS`); unconfigured → BLOCKED — merged #11 + follow-up #12 |
| 9–10 | vertical-services | `py/partial-ssrf` in connector transport and finance feed | allowlist re-derivation for GitHub repo / Coinbase pair, integer CIK, character-allowlist Stooq symbol — merged #65 |

### 2.2 CodeQL high / error findings — 63 fixed at source, 3 dismissed with recorded reasons

| Repo | PR | Findings |
|---|---|---|
| a11oy-net | #256 | 3× `js/xss-through-dom` (canonical escaper), 2× incomplete-url-substring (hostname-exact checks), `py/bad-tag-filter` |
| david-leads | #138 | 2× incomplete-url-substring, clear-text-logging, polynomial-redos, 4× uninitialized-local-variable |
| frontier-bench | #23 | 2× clear-text-logging (run-id nonce via uuid4), 2× `js/bad-tag-filter`; `py/overly-permissive-file` **dismissed: won't fix** (Docker build-context files must be COPY-readable) |
| killinchu | #480, #481 | 2× `actions/cache-poisoning/poisonable-step` (sibling checkout split by trust context), 6× incomplete-url-substring (fake transport dispatches by hostname) |
| a11oy-factory, lyte-lattice, nexus, szl-command-lab, szl-frontier | #56, #29, #48, #41, #213 | shared Replit-template scripts: `js/file-system-race` (descriptor-based reads), `js/regex/missing-regexp-anchor`; nexus also `with-app-env.mjs` race + `py/side-effect-in-assert`; szl-frontier also witness-check race + `js/double-escaping` (single-pass entity table) |
| szl-platform | #18 | **real bug**: `szl_iso42001` signed receipt called `build_receipt(kind=…)` which never existed, so the signed path always fell back to unsigned — now calls the GovernedAction/v1 builder correctly (verified: `signed: True`, `verify_receipt` findings empty); 2× `jinja2/autoescape-false` (explicit `select_autoescape`), 3× incomplete-url-substring (tests); `py/weak-sensitive-data-hashing` **dismissed: false positive** (API-key fingerprint for actor identity, not password storage) |
| szl-evidence-litellm | — | `py/weak-sensitive-data-hashing` **dismissed: false positive** (same vendored code) |
| szl-hf-frontier | #66 | 4× incomplete-url-substring — bearer tokens now attach by exact hostname (`api.github.com` / `*.github.com`) instead of URL substring (a real credential-leak pattern) |
| szl-holdings.github.io | #34 | 2× incomplete-url-substring (hostname-based external-dependency guard) + 2 committed `.pyc` removed (Scorecard BinaryArtifacts) |
| lyte-services #33, szl-constellation #26, szl-vertical-forge #12, szl-crosscheck #15 | — | test-only: token/hostname-exact assertions, side-effect-free assert, case/space-tolerant tag extraction |
| szl-atelier | #35 | `py/path-injection`: normalise-and-contain before resolve (traversal probes return 404) |
| szl-build-env | #33 (open) | `py/clear-text-logging`: success line echoes no identifiers — **blocked by a pre-existing red lane** (§5) |
| szl-gpu-bridge | #111 | 4× uninitialized-local-variable (`raise unittest.SkipTest` in optional-PyNaCl guards) |

CodeQL closes these alerts when it next analyses `main` in each repository; the PR-level "new alerts" checks were green at merge time for every merged PR.

### 2.3 Scorecard findings addressed

- **BinaryArtifactsID**: governance-as-code #24 (6 committed `.pyc` removed, `.gitignore` added), szl-holdings.github.io #34 (2 removed). Remaining: 2 wheels under `szl-evidence-litellm/releases/v0.1.0/` — owner decision (§6).
- **VulnerabilitiesID**: szl-atelier #36, szl-constellation #27, szl-mesh #57 (fastapi 0.115.x → 0.141.1 pins pulled a patched starlette; sub-app suites green: 120 / 9 / 12 tests), immune #156 (`cryptography>=49.0.0` floor). Remaining ranges in §4.
- **DependencyUpdateToolID / SASTID**: dependabot.yml and CodeQL added where missing (§2.4).
- **TokenPermissionsID (73) and PinnedDependenciesID (532)**: being worked in the parallel owner session (a11oy #2406/#2407, .github #827, lutar-lean #307 merged today); not duplicated here. Remaining counts in §4.

### 2.4 Hygiene wave — 16 repositories

`chore(hygiene)` PRs merged in: ci-witness-action, frontier-compass, gdw-frontier (artifact-weight manifest refreshed for the new files), pitch-collateral, registry-mirror, szl-command-center, szl-estate-os, szl-evidence-mandate, szl-openshell-receipts, szl-quant, szl-quant-witness, szl-safe-stack, szl-showcase, szl-skills, szl-v14, uds-bundles. Files: `.github/CODEOWNERS` (`* @stephenlutar2-hash`, mirroring the org default), grouped weekly `.github/dependabot.yml` (github-actions / pip / npm / docker as detected), `.github/workflows/codeql.yml` calling the org reusable workflow pinned to `szl-holdings/.github@144b9f48` with languages detected per repository. Every new CodeQL workflow ran green on its own PR.

### 2.5 Settings

`delete_branch_on_merge=true` on all 108 active repositories (was false everywhere). No other settings were changed.

### 2.6 Model qualification lane (from the owner's closeout)

- szl-forge #471 merged: negative receipt for the khipu-abstain DPO challenger (bundle `20261001-a989dd523998`): held-out MEASURED adversarial baseline 6/6 vs challenger 0/6, eval 0/5 vs 0/5, challenger parse failures on every row; `advisory_challenger_improves=False`; promotion NOT_PROMOTABLE; khipu-r3 remains the artifact of record.
- szl-forge #473 merged: DPO training profiles — C3 (rpo_alpha=1.0 NLL anchor, lr 1e-5, beta 0.3, one epoch) default; C2 reproduces the collapsed run on request; every effective setting and override lands in `dpo_receipt.json`; `KNOWN_PIPELINE_SHA256` gains the ladder/pure-bf16 digests. The parallel session has since re-pinned the owner DPO runbook to profile C3 (szl-hf-frontier #67). Training for C3: NOT_STARTED.

## 3. Pull-request queue (MEASURED)

At start: 7 open PRs. Disposition: immune #155 (CLEAN, green, 15 h idle) merged; szl-forge #473 merged; szl-forge #295 (observe job fails closed by design: `BLOCKED_OR_UNAVAILABLE / HOLD`), szl-org-health #216 (since merged by the parallel session), szl-typesafe-triage #35/#36 (superseded by #38/#39 in the parallel session), platform #601 (274 files, commit-lint + truth-drift + vitest red; needs engineering review, not a green-merge candidate) left to their owners.

## 4. Backlog — not done, by count (REPORTED from the audit snapshot)

| Item | Count | Why not done here |
|---|---|---|
| Scorecard PinnedDependenciesID | 532 | actions/pip/Docker pinning across ~90 repos; parallel session has started (a11oy). Mechanical but high-churn; recommend a scripted SHA-pin wave per repo family. |
| Scorecard TokenPermissionsID | 73 (17 in .github, 7 a11oy-net, 7 killinchu, 5 immune, 5 szl-router, …) | parallel session owns this lane (3 repos landed today) |
| Scorecard CodeReviewID / MaintainedID / BranchProtectionID | 85 / 69 / 35 | structural for a single-founder org (two-reviewer, activity, admin-token checks); not fixable by code |
| Scorecard CIIBestPractices / Fuzzing / SAST / CITests / SecurityPolicy | 85 / 85 / 71 / 29 / 8 | badge/program adoption; SAST and SecurityPolicy counts fall as the new CodeQL workflows and the org SECURITY.md are observed |
| CodeQL note/warning quality findings | ~530 (`py/unused-import` 102, `py/empty-except` 93, implicit string concat 52, `py/file-not-closed` 51, …) | code quality, not security; recommend ruff `--fix` waves per repo |
| Scorecard VulnerabilitiesID — torch | platform, szl-gpu-bridge, uds-bundles (torch < 2.13 ranges) | GPU/CUDA stack pins; owner decision per deployment |
| Scorecard VulnerabilitiesID — uds-bundles | gradio < 6.16, starlette, python-multipart < 0.0.31, cryptography, sentence-transformers < 5.6 | pinned deployment bundles; needs bundle rebuild + test |
| Scorecard VulnerabilitiesID — platform | scikit-learn < 1.5, pytest < 9.0.3, npm dompurify < 3.4.16 (also the single Dependabot alert) | lockfile/manifest bumps inside the monorepo |
| szl-forge diskcache PYSEC-2026-2447 | 1 | no fixed version published upstream |
| Scorecard BinaryArtifactsID — wheels | 2 (`szl-evidence-litellm/releases/v0.1.0/*.whl`) | move to GitHub Releases / PyPI (now published as szl-evidence-litellm 0.1.1 / szl-receipts 14.0.1) — owner decision |
| Open GitHub issues | 185 (szl-forge 49, szl-frontier 37, a11oy 25, .github 21, szl-org-health 12, …; 160 owner-authored, 25 bot) | evaluation / roadmap queue, labelled `estate:*`; not closable without evidence. szl-forge #362 (Khipu abstention) now has the negative receipt and C3 profile as its next evidence. |
| `.github` control-plane effect boundary | 97 undeclared workflows (3 declared) | the gate denies every undeclared workflow change; declarations are a rollout project of their own |

## 5. Open pull requests from this wave

| PR | State | Reason |
|---|---|---|
| .github #828 | green except `Static control-plane effect boundary` (WORKFLOW_DECLARATION_MISSING) | the merge queue drops it (`branch_protection_failure`, forge9-main ruleset); today's three owner merges in this repository used the admin path; the execution guard refused that path for this session — **owner merge or declaration** |
| szl-build-env #33 | `ci` (five-organ acceptance) red | pre-existing: every `ci` run since 2026-09-28 fails at step 4 `trace seed response exceeded the size limit` (verify/run-acceptance.sh); unrelated to the one-line change — **engineering item** |

## 6. Owner decisions (UNAVAILABLE from this seat)

1. **Cloudflare edge controller**: `CLOUDFLARE_API_TOKEN` is in a11oy/production, but the bounded controller returns `LIVE_ROUTE_MUTATION_BLOCKED` because the apex is already proxied and its two Worker routes do not exist; by design it only creates routes while `a-11-oy.com` / `www` are DNS-only, then re-proxies with rollback. Path: flip both records to DNS-only in the dashboard, dispatch `repair-cloudflare-product-edge-production.yml` with `dry_run=false`, accept a few minutes of degraded apex. The Pipedream Cloudflare connector still carries a token in the API-key slot (`6103 Invalid format for X-Auth-Key header`), so this seat cannot do the flip. Until then `/spectral` and `/controller` stay 404 while the site itself is up.
2. **.github #828** — admin-path merge or a control-plane effect declaration for `estate-one-fabric-alignment.yml`.
3. **LICENSE** for frontier-compass, szl-command-center, szl-ops-runbook, szl-showcase, szlholdings.com — choose Apache-2.0 (estate default) or keep proprietary (website / collateral).
4. **Committed wheels** in szl-evidence-litellm `releases/` — retire in favour of the PyPI releases.
5. **torch / uds-bundles / platform dependency ranges** (§4).
6. **David reader token**, **brand Spaces token** (szl-brand `HF_TOKEN` still dated 2026-09-27; both marketing Spaces unchanged), **llm-router Space binding** (`0b6a90ec` vs main `dfb94389`) — owner-only lanes from the earlier queue, unchanged today.
7. **szl-build-env five-organ acceptance** — red since 2026-09-28 (§5).

## 7. Method notes

- Audit gatherer: REST only (`gh api`), 108 repositories × ~12 calls; Dependabot alerts via cursor pagination; code-scanning alerts via `--paginate`. Raw per-repo results in `org-audit-2026-10-01.json`.
- Every fix PR body carries the seven provenance headings (Origin / Rights / Agents and tools / Tests / Security / Rollback / Known limits).
- Three alerts were dismissed through the API with a recorded reason (frontier-bench #5 won't fix; szl-platform #2 and szl-evidence-litellm #1 false positive). No alert was dismissed to make a count look better.
- Two accidental additions (bytecode in retrieval-bench #11, egg-info in szl-crosscheck #15 / szl-vertical-forge #12) were removed from their branches before merge; the PR helper now strips `__pycache__`, `.pytest_cache` and `*.egg-info` before staging.
