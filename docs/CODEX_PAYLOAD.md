# Codex payload — one file

CTO instruction: run this. Do not invent a winner. Do not train.

```bash
# token already on the machine — do not paste it into chat
python3 -m pip install -q 'huggingface_hub==1.23.0'
python3 tools/cto_hub_honesty_payload.py
```

Source of truth: `tools/cto_hub_honesty_payload.py`

Expected prints: `whoami_ok`, then `VERIFIED_CURRENT` or `PR`, then `STAMPED`/`ALREADY`/`SKIP_READ`.

Still blocked after this file: L1/L2/L3 metal, Hub collection membership UI, DNS.
