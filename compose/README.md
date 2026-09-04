# szl-compose — proof-status gated formula pass

SOFTWARE / CPU. Not a CUDA kernel. Not published to Kernel Hub from this PR.

Idea the Hub does not already sell: a forward pass that **cannot ALLOW on a CONJECTURE or SORRY formula**. Λ uniqueness stays Conjecture 1. PAC-Bayes stays SORRY. Those functions may emit an ADVISORY receipt or raise. They never flip a gate to ALLOW.

This reuses the 21 formulas already in `szl-holdings/szl-formulas`. It does not invent a 22nd law of physics.

```python
from compose.gate import compose_allow

# ALLOW path may only name PROVEN formulas.
result = compose_allow(
    name="hoeffding_tail",
    args={"t": 0.1, "n": 100},
)
assert result["status"] in {"ALLOWED", "BLOCKED"}
```

Run: `python -m compose.selfcheck`
