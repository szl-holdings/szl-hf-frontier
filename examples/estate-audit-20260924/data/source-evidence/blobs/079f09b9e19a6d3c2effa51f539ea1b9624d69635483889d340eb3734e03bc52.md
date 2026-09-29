# KHIPU-X1

**FPGA-first governed LLM accelerator reference.**

This repository is a software reference and future hardware workspace. It is not
a fabricated chip and does not claim performance superiority.

Current implemented lane:

- KIDS v0.1 descriptor draft;
- deterministic NumPy simulator;
- minimal explicit graph lowering;
- safe `.khipu` package builder/verifier;
- SHA3-256 execution receipt chain;
- RC1 authorization-state emulator;
- conformance tests.

Current hardware status: **UNAVAILABLE — target FPGA not selected**.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest -q
khipu-x1 demo --out ./demo-output
```

Or without installing:

```bash
PYTHONPATH=src python scripts/demo.py --out ./demo-output
```

## Truth labels

- `SCAFFOLDED`: interface/document exists.
- `SOFTWARE_EMULATED`: reference code executed.
- `FPGA_MEASURED`: only after exact bitstream/device tests.
- `BLOCKED`: attempted path refused with evidence.
- `UNAVAILABLE`: capability does not exist or was not measured.

## Program boundary

One owner prototype only. No production tooling, mass-production order or ASIC
tapeout is authorized by this repository.
