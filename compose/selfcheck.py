from .gate import ALLOW_FORMULAS, compose_allow


def main() -> int:
    blocked = compose_allow("lambda_aggregate")
    sorry = compose_allow("pac_bayes_mcallester")
    allowed = compose_allow("hoeffding_tail", {"t": 0.1, "n": 100})
    unknown = compose_allow("invented_joule")
    assert blocked["status"] == "BLOCKED"
    assert sorry["status"] == "BLOCKED"
    assert allowed["status"] == "ALLOWED"
    assert unknown["status"] == "BLOCKED"
    assert "lambda_aggregate" not in ALLOW_FORMULAS
    assert "hoeffding_tail" in ALLOW_FORMULAS
    print("selfcheck_ok", len(ALLOW_FORMULAS), "proven_allow_names")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
