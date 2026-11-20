"""Fixtures: the binding evidence classification set (fail closed)."""

import pytest

import selflint
from readback_validator import (
    ValidationError,
    classify,
    verify_zero_mutations,
    silence_report,
)

BOOT = "2026-11-20T17:13:10Z"
LATE = "2026-11-20T17:12:26Z"


def _evidence(markers, terminal, done, calls=None, manifest=None):
    last = markers[-1][1] if markers else LATE
    return {
        "boot_ts": BOOT,
        "last_marker_ts": last,
        "markers": markers,
        "terminal": terminal,
        "done": done,
        "manifest_sha256": manifest,
        "readback_sha256": manifest,
        "calls": calls if calls is not None else
                 [{"verb": "GET", "path": "/containers"}],
    }


def test_complete_set_admitted():
    markers = [("ENTRY_BOOT", "2026-11-20T17:20:00Z"),
               ("BEFORE_KERNELS", "2026-11-20T17:40:00Z")]
    ev = _evidence(markers, {"state": "done"},
                   {"state": "MEASURED"}, manifest="a" * 64)
    out = classify(ev)
    assert out["verdict"] == "COMPLETE_SET_ADMITTED"


def test_terminal_without_done_rejected():
    ev = _evidence([("ENTRY_BOOT", "2026-11-20T17:20:00Z")],
                   {"state": "stopped"}, None)
    out = classify(ev)
    assert out["verdict"] == "REJECT_TERMINAL_WITHOUT_DONE"


def test_done_only_rejected():
    ev = _evidence([], {"state": "done"}, {"state": "MEASURED"},
                   manifest=None)
    out = classify(ev)
    assert out["verdict"] == "REJECT_DONE_ONLY"


def test_t35_intervention_and_t45_owner_stop_flags():
    stale = {"boot_ts": BOOT, "last_marker_ts": "2026-11-20T17:12:26Z"}
    intervene, owner_stop, is_stale = silence_report(stale)
    assert intervene and owner_stop and is_stale
    fresh = {"boot_ts": BOOT, "last_marker_ts": "2026-11-20T17:20:00Z"}
    assert silence_report(fresh) == (False, False, False)


def test_zero_mutation_contract_fails_on_write_verb():
    with pytest.raises(ValidationError):
        verify_zero_mutations([{"verb": "POST", "path": "/x"}])
    assert verify_zero_mutations([{"verb": "GET"}])


def test_malformed_input_raises_never_unknown():
    with pytest.raises(ValidationError):
        classify({"boot_ts": BOOT})
    with pytest.raises(ValidationError):
        classify(_evidence([("A", "not-a-time")],
                           {"state": "stopped"}, None))


def test_stale_evidence_is_non_evidentiary():
    ev = _evidence([("ENTRY_BOOT", "2026-11-20T17:14:00Z")],
                   {"state": "stopped"}, None)
    out = classify(ev)
    assert out["verdict"] == "NON_EVIDENTIARY_EVIDENCE_STALE"


def test_self_lint_ascii_80cols(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "ok.py").write_text("# fine\n", encoding="ascii")
    assert selflint.lint_tree(pkg) == []
