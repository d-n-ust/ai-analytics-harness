"""Reading the trace — THE one module that knows the step schema.

The trace is the system's central contract: the repair chain is a trace-reader, so it can only
guarantee what the trace represents (findings §51). Steps are stored as plain dicts because they
ARE the persistence format (rows carry them verbatim); the stringly-typed risk that comes with
dicts is contained by this module being the ONLY reader — every gate consumes the trace through
these functions, and the key names appear nowhere else.

The step schema, as written by the loop's execute():

    tool           the tool name                     args          the call's arguments
    error          bool: the tool errored            blocked_by    guardrail that refused, or ""
    result         clipped display text              result_values typed numeric results
    result_labels  what each value is                evidence      typed EvidenceRecord dicts
    handle         r1, r2 … citation handle          acts          per-call guardrail acts

Evidence records (findings §51): {"kind": "governed", "metric", "args"} for a governed evaluation
(including a define-authored spec's metric/derived leaves), {"kind": "raw", "sql"} for agent SQL,
{"kind": "resolution", "verdict", "metric", "measure"} for an answerability decision.

Readers that need the semantic layer take a `value_of(args, metric)` callable instead of the
layer itself — pure functions with their one effect injected, so a test drives them with a dict
lookup and no warehouse.
"""
from __future__ import annotations

# The binary compositions a derived value can be: two governed-metric readings mapped to one. A
# contest in either input propagates THROUGH the composition. Op-agnostic on purpose — the same
# propagation rule covers a ratio (spend_per_signup), a difference (a hand-computed change), and
# any other binary combination.
COMPOSE = {
    "ratio":      lambda a, b: (a / b) if b else None,
    "difference": lambda a, b: a - b,
    "sum":        lambda a, b: a + b,
    "product":    lambda a, b: a * b,
}


def leaf(name) -> str:
    """The last segment of a dimension name: `activity__platform` and `platform` are one thing."""
    return str(name).strip().rsplit("__", 1)[-1].lower()


def as_number(value):
    """A declared `value`, as a number — or None when it is not one.

    The answer tool declares `value` as `"type": "number"` and a model can still put a string
    there. A string that parses is the number the model meant; one that does not is prose, and
    prose leaves `value` unset by design, so the numeric checks stand down rather than blow up.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def reported(served: list, value: float) -> bool:
    """Is this figure in the text the reader receives? Half a percent of slack, so a rounded
    rendering of the same number still counts as having been reported."""
    return any(abs(n - value) <= 0.005 * abs(value) for n in served)


def scalar(values):
    """The single number in a value_of result ({label: value}), or None when it is not one row."""
    if isinstance(values, dict) and len(values) == 1:
        (v,) = values.values()
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return v
    return None


def window_of(args: dict) -> str:
    """One string naming the time window a call asked for, or "" when it asked for none."""
    if args.get("period"):
        return str(args["period"])
    if args.get("start") or args.get("end"):
        return f"{args.get('start') or '…'}..{args.get('end') or '…'}"
    return ""


def governed_calls(steps) -> list:
    """(metric, args) for every governed evaluation the run actually made — what the answer
    stands on. Read off the trace rather than off the model's `source_metric`, which is optional
    and which a wrong answer has no reason to fill in correctly. A define-authored spec's
    governed leaves are governed calls too — recorded on the step as typed evidence, read here so
    contest disclosure, applied segment, direction and the change checks treat a spec-computed
    number exactly like a queried one."""
    seen = []
    for step in steps:
        if step.get("blocked_by"):
            continue
        args = step.get("args") or {}
        metric = args.get("metric")
        if step.get("tool") == "query_metric" and metric:
            seen.append((metric, args))
        for e in step.get("evidence") or ():
            if e.get("kind") == "governed" and e.get("metric"):
                seen.append((e["metric"], dict(e.get("args") or {})))
    return seen


def resolved_metrics(steps) -> set:
    """Metrics the run's own answerability checks resolved the question to — the typed
    `resolution` records. One semantic judgement per fact: a gate that would re-judge the
    question→metric fit stands down when a resolution already covers it."""
    return {e.get("metric") for s in steps if not s.get("blocked_by")
            for e in (s.get("evidence") or ())
            if e.get("kind") == "resolution" and e.get("verdict") == "governed"}


def evidence_scalars(steps) -> list:
    """Every number the run's successful calls returned, off the recorded step values."""
    out = []
    for step in steps:
        if step.get("blocked_by") or step.get("error"):
            continue
        for v in step.get("result_values") or ():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out.append(float(v))
    return out


def period_pairs(steps) -> list:
    """(metric, earlier_args, later_args) for every metric queried at two orderable windows with
    otherwise-identical arguments — the before/after shape, read off the trace.

    The shared basis for reading a period-over-period change: `before_after_from_calls` takes the
    two VALUES of the base metric from it, and the change disclosure takes the two WINDOWS so a
    governed rival can be evaluated at the same pair. Grouping only — no warehouse calls."""
    from collections import defaultdict

    from warehouse.config import resolve_period
    _TIME = {"period", "start", "end", "time_grain", "metric"}

    def _sig(args):
        return tuple(sorted((k, str(v)) for k, v in args.items() if k not in _TIME))

    def _start(args):
        if args.get("period"):
            try:
                return str(resolve_period(args["period"])[0])
            except Exception:                                               # noqa: BLE001
                return None
        return str(args["start"]) if args.get("start") else None

    groups = defaultdict(dict)                     # (metric, sig) -> {start_date: args}
    for metric, args in governed_calls(steps):
        start = _start(args)
        if start is not None:
            groups[(metric, _sig(args))].setdefault(start, args)
    pairs = []
    for (metric, _s), by_time in groups.items():
        if len(by_time) < 2:
            continue
        times = sorted(by_time)
        pairs.append((metric, by_time[times[0]], by_time[times[-1]]))
    return pairs


def before_after_from_calls(steps, value_of):
    """The earlier and later value of one metric queried at two time windows, or None.

    Both values must be SCALAR (one number). A pair of GROUPED calls — each quarter broken out by
    month, or by channel and region — still compares two windows of one metric, so the grouping
    is STRIPPED and the two period totals re-read through the layer (the layer computes the
    total itself, so additivity is its problem, not a hand-sum here). The premise machinery was
    blind to exactly this shape: "why did signups collapse" answered off two channel-grouped
    quarters never yielded a pair, and the contradiction the run's own windows established went
    unchecked."""
    for metric, early, late in period_pairs(steps):
        v0 = scalar(value_of(early, metric))
        v1 = scalar(value_of(late, metric))
        if v0 is None or v1 is None:
            e = {k: v for k, v in early.items() if k not in ("group_by", "time_grain")}
            l = {k: v for k, v in late.items() if k not in ("group_by", "time_grain")}
            v0, v1 = scalar(value_of(e, metric)), scalar(value_of(l, metric))
        if v0 is not None and v1 is not None:
            return metric, v0, v1
    return None


def series_from_calls(steps, value_of):
    """(metric, prev, last) from a single time-grouped governed call, or None. A series is a
    before/after pair the run already holds — the two values arrive in ONE grouped call rather
    than two scalar ones."""
    for metric, args in governed_calls(steps):
        group_by = args.get("group_by") or ()
        if not any("metric_time" in str(gb) for gb in group_by):
            continue
        keyed = value_of(args, metric)
        if not isinstance(keyed, dict) or len(keyed) < 2:
            continue
        try:
            ordered = [keyed[k] for k in sorted(keyed)]
        except TypeError:
            continue
        v0, v1 = ordered[-2], ordered[-1]
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (v0, v1)):
            return metric, v0, v1
    return None


def change_from_calls(steps, value_of, is_change):
    """A governed CHANGE metric this run queried, and its signed scalar value, or None.

    A period-over-period change metric returns a delta whose SIGN is the direction — the model
    cannot flip it, it is the governed metric's own value. Scalar only: a change grouped into
    several rows is a set of directions, not one, and is left alone."""
    if is_change is None:
        return None
    for metric, args in governed_calls(steps):
        if not is_change(metric):
            continue
        values = value_of(args, metric)
        if isinstance(values, dict) and len(values) == 1:
            (v,) = values.values()
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return metric, v
    return None
