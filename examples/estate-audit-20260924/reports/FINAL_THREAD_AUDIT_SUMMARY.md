# SZL Holdings estate execution audit — 2026-09-24

## Result

The authenticated census, immutable source-card and file-list capture, draft registry, gap report, model inventory and bounded runtime witness ran. The audit is **BLOCKED_GAPS**, with **357 unresolved gaps and 211 HIGH gaps**. Public estate promotion is not authorized.

Source implementation commit: 85df5b393f87a933a8c0c640a99846ea49429ce2.

Finance [PR #41](https://github.com/szl-holdings/vertical-services/pull/41) was already merged at 598243df05c14a493c2e2e939a86327ef71eb5f8. This run reproduced its Docker startup failure and merged repair [PR #42](https://github.com/szl-holdings/vertical-services/pull/42) at f487dc0fdc71af52841e3634bf7b9c6bf9fb6448. GitHub verifies both squash signatures. The repair packages required engine/feed/receipt/static files and adds a real container HTTP smoke.

## Public census

| Surface | Public identities |
|---|---:|
| GitHub repositories | 118 |
| Hugging Face model repositories | 49 |
| Hugging Face datasets | 35 |
| Hugging Face Spaces | 22 |
| Total | 224 |

This public projection derives from authenticated token-visible inventory. Private names and counts are withheld from public artifacts; complete authenticated snapshots remain local. Token visibility is not proof of unrestricted organization-wide access. The final visibility check independently confirmed all 224 identities still public. The preceding GitHub quota failure remains retained locally.

## Source relationships and unresolved gates

All 224 identities have a review record. Immutable source-card bytes are retained for 223 identities. The release-assets dataset has no README in its observed revision and remains unavailable for source-card review. Automated extraction grants no ALIGNED status.

| Gap | Count |
|---|---:|
| Canonical route unresolved | 89 |
| Source classification unresolved | 25 |
| Source review needs mapping or unavailable source | 97 |
| Remaining alignment review | 127 |
| Unknown license | 19 |

HIGH counts overlap identities: they count gate findings, not distinct failed products. Every unresolved record retains artifact ID, owner, observed revision where available, evidence and reason. Canonical routing uses explicit card links to observed GitHub repositories. Automated card review cannot reactivate archived or deprecated inventory.

## Model evidence

All 49 model repositories have revision-bound file inventories. 17 list weight-candidate filenames, totaling 72 files; 32 list none. 25 have source mappings and 24 remain unresolved.

These are **FILE_LIST_OBSERVATION_ONLY** findings. Optimizer state, fixtures, placeholders and unrelated binaries can match a weight filename pattern. Weight bytes, integrity, training, evaluation, and serving are not verified. No training job, benchmark score, model qualification or theorem closure was invented.

## Runtime and public claims

Latest retained assessment: 19 HEALTH_RESPONSE_OBSERVED, 1 FAIL, and 2 UNKNOWN across 22 public Spaces. Requests were limited to /, /healthz, and /readyz; application requests carried no credentials. Functional inference remains unverified.

- szl-khipu: provider/repository revision changed relative to the census. The binding gate fails despite health responses. This is source drift, not evidence of an outage.
- README: static root redirect was not followed; health routes are 404. Target remains UNKNOWN. Original and corrected assessment are retained.
- szl-frontier: root HTML returned 200; health/readiness routes returned 404, leaving health UNKNOWN.
- Finance v2: separate functional probes returned 404 for v2 signals and receipt verification. Public / and /panels returned identical bytes. Public source identifies puriq-live, while reviewed v2 is in vertical-services.
- Shared vertical-services runtime reports stale source d018c1f2c892bd36f8ba7e9c85ee0430da348a17.

Existing draft [A11oy PR #2176](https://github.com/szl-holdings/a11oy/pull/2176) owns the canonical Finance backend/projection integration. Reviewed v2 must be composed as a separately source-bound component with both revision/digest sets. The manual publisher has no Finance-only input and does not consume standalone v2. An estate-wide dispatch would not solve that wiring. No competing writer was introduced.

No public README or HF card was rewritten. The detector found no remaining affirmative production-claim candidates after checking nearby limitations against retained card bytes. That bounded scan does not prove every public claim correct. The registry does not promote listings, health, signatures or filename matches into operational qualification.

Proof and paper lanes remain unverified by this execution: no Lean theorem closure, lambda_uniqueness closure, independently signed receipt qualification, or 12/12 publication gate is asserted.

## Validation and evidence boundaries

- Estate: **205 offline regression tests passed**; all four existing payload, operational, wave and investor self-tests passed; JSON Schema validation passed for all 224 entries.
- Offline replay reproduces source reviews, registry, gaps and model evidence. Receipt hashes and runtime assessments verify.
- Finance: **245 tests plus 19 subtests passed**, eight repaired-container HTTP routes passed, and three receipts remained UNSIGNED_HONEST.
- Finance PR #42: 11 executed checks passed; four publication stages skipped. Post-merge CI and delegated workflow passed without claiming deployment.
- New estate source commits are locally SSH signed and verified. Audit JSON receipts remain **UNSIGNED**; hashes provide integrity only.
- Exact executed collector and pagination-module bytes are retained. Inherited pagination-module CRLF bytes are LF-normalized equivalent to its Git blob; they are not byte-identical.
- Default estate admission exits blocked. Structural integrity and CI success do not authorize promotion.

See execution_commands.json, snapshot_receipt.json, estate_audit_receipt.json, source_execution_binding.json, runtime_witness.json, model_evidence_inventory.json, and source-evidence blobs for exact commands, times, revisions, hashes and limitations.
