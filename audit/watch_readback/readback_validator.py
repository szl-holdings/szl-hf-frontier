"""Fail-closed watch/readback evidence validator.

Classifies watched training-lane evidence into an admission verdict.
Stdlib only. No network, no provider access, no writes. Fail closed.
"""

import calendar
import datetime
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
    try:
        dt = datetime.datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError as exc:
        raise ValidationError(
            "unparsable timestamp: %r" % (value,)) from exc
    return calendar.timegm(dt.timetuple())


def _require(condition, message):
    if not condition:
        raise ValidationError(message)


def check_marker_order(markers):
    """Markers must be (name, ts) pairs; ts non-decreasing. May be empty."""
    _require(isinstance(markers, list), "markers must be a list")
    prev = None
    for item in markers:
        _require(isinstance(item, (list, tuple)) and len(item) == 2,
                 "marker must be (name, ts)")
        name, ts = item
        _require(isinstance(name, str) and name != "", "marker name")
        epoch = _parse_ts(ts)
        if prev is not None and epoch < prev:
            raise ValidationError("markers out of order: %r" % (name,))
        prev = epoch
    return True


def verify_zero_mutations(recorded_calls):
    """Every recorded provider call must be read-only (GET/HEAD)."""
    _require(isinstance(recorded_calls, list), "calls must be a list")
    for call in recorded_calls:
        _require(isinstance(call, dict), "call must be a dict")
        if call.get("verb") not in GET_VERBS:
            raise ValidationError(
                "provider mutation recorded: %r" % (call,))
    return True


def silence_report(lane_clock):
    """Return (intervention_due, owner_stop_due, evidence_stale)."""
    _require(isinstance(lane_clock, dict), "clock must be a dict")
    for key in ("boot_ts", "last_marker_ts"):
        _require(key in lane_clock, "missing key: %s" % key)
    boot = _parse_ts(lane_clock["boot_ts"])
    last = _parse_ts(lane_clock["last_marker_ts"])
    age = last - boot
    if age < 0:
        # Markers that predate boot are not fresh evidence of this
        # boot (the r5 shape): treat the clock as stale immediately.
        return (True, True, True)
    return (age >= INTERVENE_AFTER_S,
            age >= OWNER_STOP_AFTER_S,
            age >= INTERVENE_AFTER_S)


def classify(evidence):
    """Return the admission verdict for one watched lane.

    Required keys: boot_ts, last_marker_ts, markers (ordered, may be
    empty), terminal (dict with state in stopped/done/failed/running),
    done (dict or None), calls. Admitting additionally requires
    manifest_sha256 == readback_sha256.
    """
    _require(isinstance(evidence, dict), "evidence must be a dict")
    for key in ("boot_ts", "last_marker_ts", "markers", "terminal",
                "done", "calls"):
        _require(key in evidence, "missing key: %s" % key)
    verify_zero_mutations(evidence["calls"])
    check_marker_order(evidence["markers"])

    terminal = evidence["terminal"]
    _require(isinstance(terminal, dict) and "state" in terminal,
             "terminal must carry state")
    _require(
        terminal["state"] in ("stopped", "done", "failed", "running"),
        "terminal state is not observation-class")

    done = evidence["done"]
    have_done = isinstance(done, dict) and bool(done)
    has_markers = len(evidence["markers"]) > 0
    has_manifest = bool(evidence.get("manifest_sha256"))
    clock = {"boot_ts": evidence["boot_ts"],
             "last_marker_ts": evidence["last_marker_ts"]}

    live = terminal["state"] == "running"
    if terminal["state"] in ("stopped", "failed") and not have_done:
        verdict = "REJECT_TERMINAL_WITHOUT_DONE"
    elif have_done and not (has_markers and has_manifest):
        verdict = "REJECT_DONE_ONLY"
    elif have_done and has_markers and has_manifest:
        if evidence.get("manifest_sha256") != (
                evidence.get("readback_sha256")):
            raise ValidationError("readback sha256 mismatch")
        verdict = "COMPLETE_SET_ADMITTED"
    elif live and not have_done:
        stale = silence_report(clock)[2] or not has_markers
        verdict = ("NON_EVIDENTIARY_EVIDENCE_STALE" if stale
                   else "REJECT_INCOMPLETE_MARKER_SET")
    else:
        verdict = "REJECT_INCOMPLETE_MARKER_SET"

    intervene_due, owner_stop_due, _ = silence_report(clock)
    return {
        "schema": SCHEMA,
        "verdict": verdict,
        "intervention_due": intervene_due,
        "owner_stop_due": owner_stop_due,
    }


def classify_json(payload):
    """Parse a JSON evidence bundle and classify. Fail closed."""
    try:
        evidence = json.loads(payload)
    except Exception as exc:
        raise ValidationError("malformed JSON evidence") from exc
    return classify(evidence)
