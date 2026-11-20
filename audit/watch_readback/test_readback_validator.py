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
STALE = "2026-11-20T17:12:26Z"
FRESH = "2026-11-20T17:20:00Z"


def _evidence(markers, terminal, done, calls=None, manifest=None,
              readback=None):
    last = markers[-1][1] if markers else STALE
    return {
        "boot_ts": BOOT,
        "last_marker_ts": last,
        "markers": markers,
        "terminal": terminal,
        "done": done,
        "manifest_sha256": manifest,
        "readback_sha256": readback if readback is not None else manifest,
        "calls": calls if calls is not None else
                 [{"verb": "GET", "path": "/containers"}],
    }


def test_complete_set_admitted():
    markers = [("ENTRY_BOOT", FRESH),
               ("BEFORE_KERNELS", "2026-11-20T17:40:00Z")]
    out = classify(_evidence(markers, {"state": "done"},
                             {"state": "MEASURED"}, manifest="a" * 64))
    assert out["verdict"] == "COMPLETE_SET_ADMITTED"


def test_complete_set_mismatched_readback_fails_closed():
    markers = [("ENTRY_BOOT", FRESH)]
    with pytest.raises(ValidationError):
        classify(_evidence(markers, {"state": "done"},
                           {"state": "MEASURED"}, manifest="a" * 64,
                           readback="b" * 64))


def test_terminal_without_done_rejected():
    out = classify(_evidence([("ENTRY_BOOT", FRESH)],
                             {"state": "stopped"}, None))
    assert out["verdict"] == "REJECT_TERMINAL_WITHOUT_DONE"


def test_done_only_rejected():
    out = classify(_evidence([], {"state": "done"},
                             {"state": "MEASURED"}, manifest=None))
    assert out["verdict"] == "REJECT_DONE_ONLY"


def test_t35_and_t45_clock_flags():
    stale = {"boot_ts": BOOT, "last_marker_ts": STALE}
    assert silence_report(stale) == (True, True, True)
    fresh = {"boot_ts": BOOT, "last_marker_ts": FRESH}
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
    with pytest.raises(ValidationError):
        classify(_evidence([("B", FRESH), ("A", STALE)],
                           {"state": "stopped"}, None))


def test_no_markers_no_done_is_non_evidentiary():
    out = classify(_evidence([], {"state": "running"}, None))
    assert out["verdict"] == "NON_EVIDENTIARY_EVIDENCE_STALE"


def test_self_lint_ascii_80cols(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "ok.py").write_text("# fine
", encoding="ascii")
    assert selflint.lint_tree(pkg) == []
