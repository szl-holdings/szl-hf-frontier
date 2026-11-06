# Wave payload — paste this whole file to Grok in the terminal

CTO. Fail closed. Do not invent a winner. Do not train unless CUDA is present and you say BLOCKED_NO_METAL otherwise. Do not print tokens.

```bash
set -euo pipefail
cd /tmp
rm -rf szl-hf-frontier
git clone --depth 1 https://github.com/szl-holdings/szl-hf-frontier.git
cd szl-hf-frontier
python3 payload.py
```

The repository is private: the clone needs Git credentials with access to `szl-holdings` (for example `gh auth login` followed by `gh auth setup-git`). Without them GitHub answers 404. Do not ask the founder to paste a token.

`payload.py` is offline only (since #49). It reads no token, writes nothing to the Hub and does not probe CUDA, even when `HF_TOKEN` or `HF_ORG_TOKEN1` is set. Hub banner stamping and the joblib recheck live in the separate owner-run `tools/cto_hub_honesty_payload.py`, which refuses to run in CI.

Expected: `winner: null`, `local.l1_winner: null`, `local.l2_operating_point: null`, `local.l3_collection: research-only`, `local.estate: NOT READY`, `hub: DISABLED_OFFLINE_NO_OWNER_AUTHORIZATION`, `metal: NOT_PROBED_OFFLINE`.
