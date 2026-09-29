# Evidence-backed source reconciliation

The current public census stays in `data/` and `reports/`. The fully retained September 24 census and its later source/model review are an explicit historical example in `examples/estate-audit-20260924/`. They cover 224 artifacts; they do not replace the newer 226-artifact census or certify current remote heads. The historical source review resolves 89 of its 357 source findings and retains 268 open findings. Its model review covers 49 model repositories and claims no production qualification or reproduced training.

Source reviewers record findings in `data/reconciliation/source_decisions.json` beneath the chosen evidence root. Every decision binds the original artifact identity and revision, the complete census receipt, and retained source bytes. GitHub remains the implementation authority; Hub support records retain their own artifact identity while missing producer mappings stay open. New observations require a new matching ledger; copying old revision bindings onto new observations is invalid.

Run:

```console
python tools/verify_estate_evidence.py
python tools/reconcile_estate.py --root examples/estate-audit-20260924 --check
python tools/verify_model_reconciliation.py --root examples/estate-audit-20260924
```

The reconciler writes a separate registry and a report showing which original findings were resolved and which remain. It never rewrites the original audit, transfers canonical ownership, or declares release authority. A successful check establishes exact evidence integrity and reproducibility of the recorded review. It does not independently prove that the human/agent interpretation of that evidence is correct.

Allowed closures are limited to source classification, canonical relationships, and an artifact's observed license grant. A target relationship needs both evidence from the reviewed artifact and retained source evidence from an active GitHub target at a declared immutable revision. A license from an upstream dependency does not establish the artifact's license. A source relationship review cannot close public-card, runtime, training, evaluation, or publication gates.

An explicitly frozen archive can be a terminal provenance record with no replacement product. This exception requires `ARCHIVED`, `archived_provenance`, canonical role `record`, an explicit final-purpose reason, and revision-bound evidence. It never applies to `DEPRECATED` records: those still require evidenced successor routes. Split migrations may retain multiple scoped successors instead of inventing a single canonical replacement.

Original automated source extraction and subsequent curated reconciliation remain separate, so changes in interpretation can be audited without silently overwriting the observations that produced the first report. Raw training receipts remain unchanged even when their hashes disagree with current model bytes.
