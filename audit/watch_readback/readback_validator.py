"""Fail-closed watch/readback evidence validator.

Classifies watched training-lane evidence into an admission verdict.
Stdlib only. No network, no provider access, no writes. Fail closed.
"""

import json

SCHEMA = "szl.watch-readback/v1"

INTERVENE_AFTER_S = 2100  # T+35 minutes
OWNER_STOP_AFTER_S = 2700  # T+45 minutes

GET_VERBS = ("GET", "HEAD")

VERDICTS = (
    "COMPLETE_SET_ADMITTED",
    "REJECT_TERMINAL_WITHOUT_DONE",
    "REJECT_DONE_ONLY",
    "REJECT_INCOMPLETE_MARKER_SET",
    "REJECT_MUTATIONS_RECORDED",
    "NON_EVIDENTIARY_EVIDENCE_STALE",
)


class ValidationError(ValueError):
    """Raised on malformed evidence. Fail closed; nothing is UNKNOWN."""


def _parse_ts(value):
    if not isinstance(value, str) or len(value) < 19:
        raise ValidationError("bad timestamp: %r" % (value,))
    # ISO-8601 UTC to epoch seconds, stdlib only.
    import calendar

    try:
        return calendar.timegm(time_tuple(value))
    except Exception as exc:
        raise ValidationError("unparsable timestamp: %r" % (value,)) from exc


def time_tuple(value):
    import datetime

    try:
        dt = datetime.datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError as exc:
        raise ValidationError("bad ISO ts: %r" % (value,)) from exc
    return dt.timetuple()


def _require(condition, message):
    if not condition:
        raise ValidationError(message)


def check_marker_order(markers):
    """Markers must be (name, ts) tuples in non-decreasing ts order."""
    _require(isinstance(markers, list) and markers, "markers must be list")
    prev = None
    for item in markers:
        _require(isinstance(item, (list, tuple)) and len(item) == 2,
                 "marker must be (name, ts)")
        name, ts = item
        _require(isinstance(name, str) and name, "marker name")
        epoch = _parse_ts(ts)
        if prev is not None and epoch < prev:
            raise ValidationError("markers out of order: %r" % (name,))
        prev = epoch
    return True


def verify_zero_mutations(recorded_calls):
    """Every recorded provider call must be read-only (GET/HEAD)."""
    _require(isinstance(recorded_calls, list), "calls must be a list")
    for call in recorded_calls:
        _require(isinstance(call, dict), "call must be dict")
        verb = call.get("verb")
        if verb not in GET_VERBS:
            raise ValidationError(
                "provider mutation recorded: %r" % (call,))
    return True


def silence_report(evidence):
    """Return (intervene_due, owner_stop_due, is_stale) for the lane."""
    _require(isinstance(evidence, dict), "evidence must be dict")
    boot = _parse_ts(evidence["boot_ts"])
    _require("last_marker_ts" in evidence, "last_marker_ts required")
    last = _parse_ts(evidence["last_marker_ts"])
    age = last - boot
    return (
        age >= INTERVENE_AFTER_S - 1,
        age >= OWNER_STOP_AFTER_S - 1,
        age >= INTERVENE_AFTER_S - 1,
    )


def classify(evidence):
    """Return the admission verdict for one watched lane.

    Required keys: boot_ts, last_marker_ts, markers (ordered list),
    terminal (dict with state), done (dict or None), manifest_sha256,
    readback_sha256 (manifest must equal readback to admit), calls.
    """
    _require(isinstance(evidence, dict), "evidence must be dict")
    for key in ("boot_ts", "last_marker_ts", "markers", "terminal",
                "done", "calls"):
        _require(key in evidence, "missing key: %s" % key)
    verify_zero_mutations(evidence["calls"])
    check_marker_order(evidence["markers"])

    terminal = evidence["terminal"]
    _require(isinstance(terminal, dict) and "state" in terminal,
             "terminal must carry state")
    _require(terminal["state"] in ("stopped", "done", "failed"),
             "terminal state not terminal-class")

    done = evidence["done"]
    have_done = isinstance(done, dict) and bool(done)
    has_markers = len(evidence["markers"]) > 0
    has_manifest = bool(evidence.get("manifest_sha256"))
    readback_matches = (
        evidence.get("manifest_sha256")
        == evidence.get("readback_sha256")
    )

    if terminal["state"] == "stopped" and not have_done:
        verdict = "REJECT_TERMINAL_WITHOUT_DONE"
    elif have_done and not (has_markers and has_manifest):
        verdict = "REJECT_DONE_ONLY"
    elif have_done and has_markers and has_manifest:
        _require(readback_matches, "readback sha256 mismatch")
        verdict = "COMPLETE_SET_ADMITTED"
    elif has_markers and not have_done:
        stale = silence_report(evidence)[2]
        verdict = ("NON_EVIDENTIARY_EVIDENCE_STALE" if stale
                   else "REJECT_INCOMPLETE_MARKER_SET")
    else:
        verdict = "NON_EVIDENTIARY_EVIDENCE_STALE"

    return {
        "schema": SCHEMA,
        "verdict": verdict,
        "intervention_due": silence_report(evidence)[0],
        "owner_stop_due": silence_report(evidence)[1],
    }


def classify_json(payload):
    """Parse a JSON evidence bundle and classify. Fail closed."""
    try:
        evidence = json.loads(payload)
    except Exception as exc:
        raise ValidationError("malformed JSON evidence") from exc
    return classify(evidence)
