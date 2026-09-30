# Evidence-first selective agent lab

Python research prototype, with a retained real local inference smoke run on September 29, 2026. The canonical source is versioned here; the measured run remains unsigned local research with its original `LOCAL_UNPUBLISHED` receipt label. It supplies no production authorization, trained new model, calibrated safety certificate, or novel statistical theorem.

This additive source adoption preserves the three implementation modules, their
64 matching offline tests, the measured predecessor snapshot, the original
inference receipt, and the archival source-alignment input/output byte for byte.
Only documentation paths are adapted for this repository. `SHA256SUMS` records
the ten frozen files with repository-relative paths; ordinary CI checks those
hashes before testing and replaying. Source alignment is an isolated offline
observer, with no change to the estate collectors or their release thresholds.

The receipt retains its original `LOCAL_UNPUBLISHED`, `signed=false`, and
`promotion_eligible=false` labels. Committing the retained observation does not
retroactively change its source identity or authenticate the local observer.

The implementation keeps three questions separate: what the model proposed, whether a trusted fixture capability permits that exact read, and whether independent calibration data supports a selective policy. Retrieved text and model confidence cannot issue a capability.

## Measured result

Forty real Ollama responses were retained, twenty per model. Eight clean/injected document pairs exercise authorized reads; four cases require abstention because a capability is absent, expired, request-mismatched, or evidence-stale.

- `szl-khipu:latest`: 15/20 raw-contract-correct; 15/16 useful requested reads; 7/8 pairs both correct; 0/4 correct explicit abstentions.
- `qwen3:4b-instruct`: 16/20 raw-contract-correct; 16/16 useful requested reads; 8/8 pairs both correct; 0/4 correct explicit abstentions.
- The deterministic fixture gate rejected all nine invalid proposals across the two models. It admitted 31 useful in-memory reads and recorded zero unauthorized simulated reads. Every inference returned; no infrastructure failures were discarded.

A rejected unsafe model proposal is a gate success, not a correct model answer. These authored fixtures are descriptive development cases, not IID or held-out evidence. The result is a concrete abstention-training/evaluation target, not population-level model superiority or prompt-injection safety.

Full model manifest identities, requests, raw responses, gate outcomes, inference counters, timings, chained row digests, and summary counts are in `../../../examples/local-evidence-admission-20260929/local-inference-receipt.json`. Mutable model names are accompanied by full before/after digests. This run used Ollama 0.33.2 on a loopback-only, task-managed service at port 11435, which was stopped afterwards. No cloud model, weight pull, provider publication, or external tool effect was involved.

## Run and replay

Python 3.12 or later, standard library only. Run these commands from this directory, replacing `python` with an installed Python executable if needed:

```sh
python -B -m unittest -q test_evidence_lab test_selective_calibration test_source_alignment
python -I -B evidence_lab.py --verify ../../../examples/local-evidence-admission-20260929/local-inference-receipt.json
```

The inference/replay and calibration-library boundary passed 34/34 tests independently. Five additional CLI tests cover bounded input, output preservation, held-out split overlap, fixed selection, and honest offline evidence labels; the combined local suite is 39 tests.

The separately frozen source-alignment observer contributes 25 additional
offline tests, for 64 tests in this adopted subtree. Ordinary CI performs no
model or network requests for this lab.

To make a **new** observation, first run a loopback-only Ollama instance with the selected models already installed. Then choose an unused output path:

```sh
python -I -B evidence_lab.py --port 11435 --models szl-khipu:latest qwen3:4b-instruct --output new-observation.json
```

The runner refuses to overwrite an existing receipt or checkpoint. It checks model identity before each request and after the run. Each checkpoint is partial evidence, not a completed run receipt. A model-policy failure stays visible even if the gate safely rejects it; the process success condition is infrastructure availability and absence of unauthorized simulated effects, **not** perfect model accuracy.

## Preserved measured source and compatible replay

The measured run used source SHA-256 `9bd505ecf0cc7dead5fea7234b41de4a71521c0a3a79569e5bf9304ed00ad210`. Its byte-exact, non-executed snapshot is `measured-source-20260929.py.txt`.

After measurement, independent review found that replay did not enforce the local/synthetic/unpublished labels. Only `verify_run` was hardened; requests, fixtures, gate, scoring, and inference code were unchanged. The current verifier accepts its own source or that one exact predecessor, and fails if the retained predecessor snapshot is missing or altered. It also checks the fixed evidence/publication labels, allowed loopback endpoint, and explicit limits. The original run receipt was not rewritten or retrospectively resealed under the repaired source.

Original receipt file SHA-256: `9b3a3dccda2a8f9a67a538176b7fadc894466530e2c95f2b5039a6665b563190`. Hashes enable integrity comparisons; these local observations are unsigned and do not authenticate the observer or authorize deployment.

## Calibration utility

`selective_calibration.py` provides `calibrate(episodes)` and `evaluate(test_episodes, calibration, calibration_episodes)`. An episode has exactly `episode_id`, finite `score` in [0,1], boolean `capability_valid`, and boolean `error`. IDs must be unique. Invalid capabilities never enter the selected set, whatever the score.

The frozen 21-threshold grid uses a simultaneous Hoeffding bound with delta divided across the grid. The default target is alpha=0.05, delta=0.05. Empty selection has no numeric risk estimate. If no threshold qualifies, the artifact says `ABSTAIN_ALL / INSUFFICIENT_CALIBRATION`. Test labels never choose a new threshold; overlap and altered calibration artifacts reject.

This utility requires a fixed scorer/policy and independently sampled calibration episodes. It is **not connected to confidence scores in the forty-call smoke run**, and its synthetic 2,000-row unit fixtures are not measured model calibration. No certificate has been issued for either local model.

The offline CLI takes strict JSON episode lists (one MiB per file), refuses to overwrite earlier evidence, and labels its report as offline data evaluation rather than model inference:

```sh
python -B selective_calibration.py --calibration calibration-episodes.json --test sealed-test-episodes.json --output new-selective-evaluation.json
```

The optional test file must have disjoint episode IDs. Passing this mechanical split check does not establish independent sampling or distributional assumptions; those remain experiment-design obligations. This command does not train a model, mint production permission, or publish anything.

## Offline source-alignment observer

`source_alignment.py` compares one bounded retained domain-readback receipt to
a caller-supplied GitHub source revision. It verifies the retained runtime JSON
bytes and digest, preserves separate GitHub/HF revision roles, rejects stale or
future observations, and treats registry HTML as reachability only. All author,
release, signature, immutable-parity, exact-head CI, and functional-readiness
proofs remain false. It performs no network request or publication.

The CLI defaults to a 3,600-second observation age and refuses to overwrite an
existing output. The [retained archival example](../../../examples/source-alignment-20260929/README.md)
uses an explicitly recorded 21,600-second window for a September 29 observation;
that archive is not a fresh probe or release check. This independent observer
does not relax any canonical collector threshold or override older receipts.

## Research lineage and the SZL adaptation

The method is to study established work, extract a useful invariant, build a small independent prototype, and test the difference. It is not a claim about how a particular fashion house operates or a license to copy unattributed code.

- [CaMeL, Debenedetti and collaborators](https://arxiv.org/abs/2503.18813): separate trusted control/data flow from untrusted observations and check capabilities at tool boundaries. The published result is not our result.
- [SelectiveNet, Geifman and El-Yaniv](https://proceedings.mlr.press/v97/geifman19a.html): measure useful coverage alongside errors on accepted predictions.
- [Learn then Test, Angelopoulos and collaborators](https://arxiv.org/abs/2110.01052): account for selecting a policy from multiple candidates, rather than searching test labels.
- [AgentDojo, ETH SPY Lab](https://github.com/ethz-spylab/agentdojo): follow up with executable task utility and adaptive injection evaluation. This prototype has not run AgentDojo.

The implemented integration is capability-bounded execution, explicit abstention, and replayable evidence. Selective prediction and capability security are prior art; novelty would require a literature comparison and stronger measured experiments.

## Next release boundary

Canonical order is GitHub `szl-holdings` Python source, then exact-source Hugging Face `SZLHOLDINGS` publication/readback, then domain application verification at `a-11-oy.com` and `a11oy.net`. A local test, a pushed branch, a merge, a provider build, and a functioning application are separate states. This source addition does not claim Hugging Face publication, domain deployment, held-out qualification, or a promoted model. The original observation remains unsigned local research evidence.

The next model experiment should use new, disjoint denial/evidence cases and a frozen correctness scorer, with useful authorized-read coverage retained. A next kernel experiment must compare a pinned implementation against a numerical reference and record actual device correctness, latency, memory, and source hashes; a source file or model-card title is not a compiled or faster kernel.
