# PAYLOAD — SZL HF Frontier closeout

Copy everything below the line into terminal Grok. Do not paste tokens.

---

You are working as founder-operator on GitHub `szl-holdings` and Hugging Face `SZLHOLDINGS`.
Identity: Stephen P. Lutar / `stephenlutar2-hash`. Doctrine v11 LOCKED. Λ = Conjecture 1 (OPEN).

## Doctrine (non-negotiable)

- Fail closed. Signed is not correct. Live is not qualified. Published failing tests stay failed.
- Do not invent benches, joules, downloads, or Lean proofs.
- Do not clone Flash / Sage / Flex and stamp SZL on it.
- Do not promote Chaski, A11OY-MINI, ReceiptAgent v3, or Khipu-abstain.
- Do not print secrets. Use env `GH_TOKEN` / `HF_TOKEN` if present; never echo them.
- GitHub is canonical. Hub is a publish mirror.

## Already done (do not redo)

- `szl-forge#110` merged — Hub half-states closed on GitHub.
- `szl-energy-attest#35` merged — `HUB_MIRROR_STATUS.json` = `MIRROR_EMPTY`.
- `szl-forge#92` `#93` closed GitHub-side.
- `szl-hf-frontier#11` merged — kernel/model audit + `compose/` proof-status gate.
- Tracker: https://github.com/szl-holdings/szl-hf-frontier/issues/1

## Execute in this order. Stop a lane if it stays red.

### 0. Boot

```bash
mkdir -p ~/szl-frontier-run && cd ~/szl-frontier-run
curl -fsSL https://raw.githubusercontent.com/szl-holdings/szl-hf-frontier/main/payload.py -o payload.py
python3 payload.py
```

If `main` does not yet have `payload.py`, use branch `ops/terminal-payload-20260904`.

### 1. C3 — kernel CI (P0)

Repos: `szl-lambda-gate`, `szl-governed-norm`.
Clone, run tests with `PYTHONPATH=. python -m pytest -q` (or repo script).
If tests fail: fix the test or the code. If the matrix is unsupported: mark the card/README `BLOCKED` with the failing test name. Do not delete the failure and claim green.
PR + merge only when local tests pass.

### 2. C4 — unsafe serialization (P0)

Repos: `szl-blocked`, `szl-provctl`, `szl-formulas`, `szl-ouroboros`, `szl-nemo`.
Grep for `pickle`, `joblib`, `cloudpickle`. Replace public artifacts with JSON / safetensors / explicit coefficients. Delete Hub-bound `.pkl` from git if present. PR.

### 3. C6 — blocked + provctl public state (P0)

`szl-blocked` and `szl-provctl` must not advertise a product-ready core while shipping `PUBLISHED_BLOCKED_OR_FAILED_STATE`. Either make tests honest-green or label `SOFTWARE_LIMITED` with no product claim.

### 4. C1 C2 C5 — model quarantine (P0, Hub write)

Only if `HF_TOKEN` works:

- Relabel `SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v3` as non-release / placeholder.
- Relabel `SZLHOLDINGS/SZL-Khipu-1.5B-abstain` experiment/empty unless weights exist.
- Remove `chaski`, `chaski-5050`, `A11OY-MINI` from flagship collections. Strip absolute local paths from `chaski-5050`.
- Do not unpin product Spaces unless the CTO order says so.

If no HF token: write the exact card text as markdown in `szl-hf-frontier/docs/` and stop. Do not fake a publish.

### 5. Lanes after C1–C6

- L1 ReceiptAgent: hidden GMB bakeoff nano / v2 / 1.5B. Quarantine v3. No winner without sample logs.
- L2 Khipu: abstention + invented-identifier rate. GGUF gets its own eval.
- L3 Chaski stays research-only until a held-out JSON/refusal gate beats a disclosed baseline.

No GPU? Do not train. Record `BLOCKED_NO_METAL`.

### 6. Allowed new kernel

Only the proof-status compose gate (`szl-hf-frontier/compose/`): CONJECTURE and SORRY formulas cannot ALLOW. Λ uniqueness stays Conjecture 1. Do not publish to Kernel Hub until C3 is green.

### 7. Report format

One comment on `szl-holdings/szl-hf-frontier#1`:

```
C3: PASS|FAIL|BLOCKED — evidence URL
C4: PASS|FAIL|BLOCKED — evidence URL
C6: PASS|FAIL|BLOCKED — evidence URL
C1/C2/C5: PASS|FAIL|NO_HF_TOKEN
L1/L2/L3: OPEN|BLOCKED_NO_METAL
```

## Python (same file as payload.py)

If curl fails, save the sibling `payload.py` from this repo and run it.
