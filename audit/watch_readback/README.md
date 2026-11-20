# watch_readback: fail-closed watch/readback validator

Purpose: classify a watched training lane's evidence as admissible or
non-evidentiary, with fixed thresholds and a zero-mutation contract.
Born from the 2026-11-20 r4/r5 frontier postmortems: both uninstrumented
fires died quietly (r5 stopped 17:52:44Z, no DONE, markers stale since
17:12:26Z) and produced NON_EVIDENTIARY verdicts by this exact rule set.

## Rules (fail closed)

* A lane is evaluated from: boot time, ordered progress markers with UTC
  stamps, a terminal observation, and the recorded provider-call log.
* INTERVENE_AFTER_S = 2100 (T+35): no new progress marker within 35
  minutes of boot -> intervention flag.
* OWNER_STOP_AFTER_S = 2700 (T+45): silence past 45 minutes -> an
  owner-stop request is due (recorded as a recommendation only).
* Markers that predate boot are not fresh evidence of this boot (the
  observed r5 shape) and make the clock stale immediately.
* COMPLETE_SET_ADMITTED requires: ordered marker set, terminal DONE
  with result manifest, and readback sha256 equal to manifest sha256.
* terminal-without-DONE -> REJECT_TERMINAL_WITHOUT_DONE.
* DONE-only (no marker set / manifest) -> REJECT_DONE_ONLY.
* any malformed input raises ValidationError; nothing is UNKNOWN.
* verify_zero_mutations: every recorded provider call must be GET/HEAD;
  any other verb fails closed.

## Acceptance (binding for this PR)

"Acceptance: the fixed fixture set (T+35 intervention, T+45 owner-stop,
terminal-without-DONE rejection, DONE-only rejection, complete-set
admission, zero provider mutations) passes exactly, and the package
self-lints to plain ASCII with lines <= 80 columns."

This package adds validator capability only. It executes no provider
calls, promotes no DONE, clears no gate, and touches no held item (F5
rotation, A7 digest pinning, K1 visibility, five-organ 503, hf-sync
release freeze). Council receipts 2026-11-20: Kimi
KIMI_T10_PRDRAIN_PASS, Mistral MISTRAL_T10_DRAIN_CLEARED.

## Local verification receipt (2026-11-20)

Pushed only after local proof on the CTO device: pytest 9/9 pass,
selflint clean (ASCII, <= 80 columns).
