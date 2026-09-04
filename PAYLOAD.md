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

If `HF_TOKEN` or `HF_ORG_TOKEN1` is already in the environment, `payload.py` also stamps Hub banners and rechecks joblib. Do not ask the founder to paste a token.

Expected: `winner=null`, `operating_point=null`, L3 `research-only`. Metal jobs print `BLOCKED_NO_METAL`.
