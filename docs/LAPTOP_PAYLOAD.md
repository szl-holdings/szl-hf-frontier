# SZL laptop payload — ReceiptAgent v3 smoke

CTO. You are on the owner WSL Ubuntu user `rosie` with RTX 5050.
Fail closed. Do not invent a winner. Do not publish. Do not raise the 80 C kill.
Do not train v3 as flagship. Do not print tokens.

Save as `/home/rosie/szl_laptop_payload.py` and run:
`python3 /home/rosie/szl_laptop_payload.py`

```python
#!/usr/bin/env python3
"""SZL laptop payload. Fail closed. Winner stays null."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
FORGE = HOME / "szl-forge"
LANE = FORGE / "frontier" / "qwen35-receiptagent-v3"
PINNED = HOME / ".venvs" / "szl-unsloth" / "bin" / "python"
ALT = HOME / "venv-ra-v3" / "bin" / "python"
PRE = HOME / "szl-runs" / "receiptagent-v3" / "runtime-preflight.json"


def run(cmd, check=True):
    print("+", " ".join(map(str, cmd)), flush=True)
    return subprocess.run(cmd, check=check)


def capture(cmd):
    p = subprocess.run(cmd, check=False, capture_output=True, text=True)
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()


def main() -> int:
    report = {
        "schema": "szl.laptop-payload/v1",
        "winner": None,
        "flagship": False,
        "publicationEligible": False,
    }
    code, gpu, err = capture(
        [
            "nvidia-smi",
            "--query-gpu=name,temperature.gpu,memory.free",
            "--format=csv,noheader",
        ]
    )
    report["gpu"] = gpu or err or "BLOCKED_NO_METAL"
    if code != 0 or "5050" not in (gpu or ""):
        print(json.dumps({**report, "status": "BLOCKED_NO_METAL"}, indent=2))
        return 1

    if not FORGE.is_dir():
        run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "https://github.com/szl-holdings/szl-forge.git",
                str(FORGE),
            ]
        )
    run(["git", "-C", str(FORGE), "fetch", "origin"])
    run(["git", "-C", str(FORGE), "checkout", "main"])
    run(["git", "-C", str(FORGE), "pull", "--ff-only"])
    src = subprocess.check_output(
        ["git", "-C", str(FORGE), "rev-parse", "HEAD"], text=True
    ).strip()
    report["source_commit"] = src

    if not PINNED.is_file():
        PINNED.parent.parent.mkdir(parents=True, exist_ok=True)
        if not ALT.is_file():
            print(json.dumps({**report, "status": "NOT_READY", "reason": "no venv"}, indent=2))
            return 1
        link = PINNED.parent.parent
        if link.exists() or link.is_symlink():
            if link.is_symlink() or link.is_file():
                link.unlink()
        if not link.exists():
            link.symlink_to(HOME / "venv-ra-v3")
    py = str(PINNED if PINNED.is_file() else ALT)
    code, torch, _ = capture(
        [py, "-c", "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"]
    )
    report["torch"] = torch
    if code != 0 or not str(torch).startswith("True"):
        print(json.dumps({**report, "status": "NOT_READY", "reason": "torch cuda"}, indent=2))
        return 1

    report["ollama"] = shutil.which("ollama") or "UNAVAILABLE"
    PRE.parent.mkdir(parents=True, exist_ok=True)
    q = run(
        [py, str(LANE / "qualify_runtime.py"), "--source-commit", src, "--report", str(PRE)],
        check=False,
    )
    if q.returncode != 0:
        print(json.dumps({**report, "status": "NOT_READY", "reason": "qualify_runtime"}, indent=2))
        return 1

    smoke = run(
        [
            py,
            str(LANE / "launch_supervised_training.py"),
            "--source-commit",
            src,
            "--run-kind",
            "smoke",
        ],
        check=False,
    )
    report["smoke_exit"] = smoke.returncode
    if smoke.returncode != 0:
        print(json.dumps({**report, "status": "SMOKE_FAILED"}, indent=2))
        return smoke.returncode
    print("SMOKE_OK. Not a winner. Do not run full unless supervisorRunId printed.")
    print(json.dumps({**report, "status": "SMOKE_OK"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

After `SMOKE_OK` and a `supervisorRunId`, run full only:

```bash
cd /home/rosie/szl-forge
SRC=$(git rev-parse HEAD)
/home/rosie/.venvs/szl-unsloth/bin/python \
  frontier/qwen35-receiptagent-v3/launch_supervised_training.py \
  --source-commit "$SRC" --run-kind full
```

Report MEASURED only: GPU line, source commit, smoke/full exit, supervisorRunId.
Winner stays null. Do not git add weights, gguf, pem, or outputs.
