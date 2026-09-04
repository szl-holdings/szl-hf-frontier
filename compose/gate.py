"""Proof-status gated composition. Doctrine v11. Fail closed."""
from __future__ import annotations

from typing import Any

# Status labels mirrored from szl-formulas/_formulas.py. Software mirror only.
# Lean locked-proven count remains exactly 8 in the estate ledger.
PROOF_STATUS = {
    "lambda_aggregate": "CONJECTURE",
    "lambda_homogeneous": "AXIOM",
    "lambda_bounded": "PROVEN",
    "pac_bayes_mcallester": "SORRY",
    "bekenstein_cascade": "PROVEN",
    "reidemeister_invariant": "AXIOM",
    "khipu_merkle_root": "PROVEN",
    "dsse_envelope": "PROVEN",
    "gleason_quantum_lambda": "AXIOM",
    "hoeffding_tail": "PROVEN",
    "pinsker_kl_bound": "AXIOM",
    "fisher_rao_distance": "PROVEN",
    "bohr_complementarity_floor": "PROVEN",
    "kochen_specker_18vector_witness": "AXIOM",
    "two_witness_ks18_soundness": "SORRY",
    "shor_codeword_distance": "PROVEN",
    "css_ingress_verify": "PROVEN",
    "kitaev_surface_correct": "AXIOM",
    "reed_solomon_singleton": "PROVEN",
    "madhava_series": "PROVEN",
    "schur_concave_lambda_two_axis": "AXIOM",
}

BLOCK_ON_STATUS = frozenset({"CONJECTURE", "SORRY"})
ALLOW_FORMULAS = frozenset(
    name for name, status in PROOF_STATUS.items() if status == "PROVEN"
)


def compose_allow(name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    """Refuse ALLOW when the named formula is CONJECTURE or SORRY."""
    status = PROOF_STATUS.get(name)
    if status is None:
        return {
            "name": name,
            "status": "BLOCKED",
            "reason": "UNKNOWN_FORMULA",
            "proof_status": None,
            "value": None,
        }
    if status in BLOCK_ON_STATUS:
        return {
            "name": name,
            "status": "BLOCKED",
            "reason": f"PROOF_STATUS_{status}_CANNOT_ALLOW",
            "proof_status": status,
            "value": None,
            "advisory": True,
        }
    return {
        "name": name,
        "status": "ALLOWED",
        "reason": "PROOF_STATUS_PERMITS_ALLOW",
        "proof_status": status,
        "value": None,
        "note": "Value is computed only when the formula module is imported; this gate is the admission check.",
    }
