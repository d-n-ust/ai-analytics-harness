"""The gate's guarantee as a PROPERTY, over a generated call space — NO LLM.

test_structural.py proves the gate against seven hand-picked calls. The guarantee it claims
is universal — "they hold regardless of what the model does, which is why they can be proven
exhaustively" — and a hand-written list can only ever prove the cases someone thought of.
Both holes this file catches sit one keystroke from a case that WAS on the list: the same
scope named by a governed synonym, and the same scope asked for as a breakdown.

The property under test, stated without reference to how the gate is implemented:

    if a governed call is SERVED, then every governed member it reports a number ABOUT
    must be inside coverage for that call's window.

"Reports a number about" is read from the rows that actually came back — a result with a
`region` column reports one number per region, so it reports about every region in it. A
global total reports about no region in particular, which is why an unfiltered March total
is legitimately served while `region=APAC` in March is not.

The oracle is `SemanticLayer.in_coverage` and `resolve_member`: both independently tested,
and neither is the thing under test. The gate's defect is not that they are wrong, it is
that the gate does not consult them for every way a scope can be named.

    uv run python tests/test_gate_properties.py
"""

from __future__ import annotations

import sys

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from agent.guardrails import LADDER
from agent.prompt import build_grounding
from semantic.semantic import SemanticLayer
from warehouse.warehouse import open_warehouse

_CON = open_warehouse(create_star_views=True)
_SL = SemanticLayer(_CON)
# gate + fence + member resolution: the configuration whose whole claim is that no
# out-of-coverage number can be reached, by any route.
_TB = build_grounding(_CON, rung=6, guardrails=LADDER[5]).toolbox

COVERAGE_DIMS = ("region", "country")

# Metrics that are time-filterable AND sliceable by both coverage-bearing dimensions.
METRICS = ["value_moments", "active_users", "power_users"]

# Every one of these names the SAME governed scope: the APAC region. The gate must not
# care which spelling a question happens to use.
APAC_NAMES = [("region", "APAC"), ("region", "apac"), ("region", "Asia Pacific"),
              ("region", "asia pacific"), ("country", "PH"), ("country", "philippines"),
              ("country", "ID"), ("country", "indonesia")]

# Boundaries that matter: before data starts (2025-09-01), around the APAC launch
# (2026-05-01), and at the end of data (2026-07-12).
DATES = ["2025-07-01", "2025-09-01", "2026-02-01", "2026-03-31", "2026-04-30",
         "2026-05-01", "2026-05-15", "2026-06-30", "2026-07-12"]

SCOPES = ["none", "filter_region", "filter_country", "group_region", "group_country"]


def _call(metric: str, scope: str, spelling: str, start: str, end: str) -> dict:
    args: dict = {"metric": metric, "start": start, "end": end}
    if scope == "filter_region":
        args["filters"] = {"region": spelling}
    elif scope == "filter_country":
        args["filters"] = {"country": spelling}
    elif scope == "group_region":
        args["group_by"] = ["region"]
    elif scope == "group_country":
        args["group_by"] = ["country"]
    return args


def _serve(args: dict):
    """(blocked, columns, rows) for one governed call through the real dispatcher."""
    text, is_error, _ = _TB.dispatch("query_metric", args)
    if is_error:
        return True, [], []
    lines = text.split("\n")
    cols = [c.strip() for c in lines[0].removeprefix("columns:").split(",")]
    rows = []
    for line in lines[1:]:
        if line.startswith("(") and line.endswith(")"):
            # A one-column row prints as "(472,)", so the split leaves a trailing empty field.
            cells = [p.strip().strip("'") for p in line[1:-1].split(",")]
            rows.append([c for c in cells if c != ""])
    return False, cols, rows


def _reported_members(cols, rows, args) -> set:
    """The governed members this result reports a number ABOUT — read from the rows that came
    back, not from the call's arguments, so the oracle cannot inherit the gate's blind spot."""
    out = set()
    for dim in COVERAGE_DIMS:
        if dim in cols:
            i = cols.index(dim)
            out |= {(dim, r[i]) for r in rows if i < len(r) and r[i] not in (None, "None")}
        elif isinstance(args.get("filters"), dict) and dim in args["filters"]:
            raw = args["filters"][dim]
            out.add((dim, _SL.resolve_member(dim, raw) or raw))
    return out


def _outside_coverage(members: set, start, end) -> list:
    bad = []
    for dim, member in members:
        kw = {"region": member} if dim == "region" else {"country": member}
        ok, detail = _SL.in_coverage(start, end, **kw)
        if not ok:
            bad.append((dim, member, detail))
    return bad


# --------------------------------------------------------------------------- #
# 1. The property, over a generated call space
# --------------------------------------------------------------------------- #
@settings(max_examples=400, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(metric=st.sampled_from(METRICS), scope=st.sampled_from(SCOPES),
       spelling=st.sampled_from([s for _, s in APAC_NAMES]),
       start=st.sampled_from(DATES), end=st.sampled_from(DATES))
def test_served_calls_report_only_covered_scopes(metric, scope, spelling, start, end):
    if start > end:
        return
    args = _call(metric, scope, spelling, start, end)
    blocked, cols, rows = _serve(args)
    if blocked:
        return                      # refusing is always sound; over-refusal is a separate test
    bad = _outside_coverage(_reported_members(cols, rows, args), start, end)
    assert not bad, (
        f"SERVED a number for a scope outside coverage.\n  call: {args}\n"
        f"  reported about: {bad[0][0]}={bad[0][1]!r} — {bad[0][2]}")


# --------------------------------------------------------------------------- #
# 2. Metamorphic: one scope, many spellings, one verdict
# --------------------------------------------------------------------------- #
@settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(metric=st.sampled_from(METRICS),
       start=st.sampled_from(DATES), end=st.sampled_from(DATES))
def test_same_scope_same_verdict(metric, start, end):
    """`region="APAC"`, `region="asia pacific"` and `country="PH"` all name the APAC region.
    Whether a request is answerable cannot depend on which word the asker reached for."""
    if start > end:
        return
    verdicts = {}
    for dim, spelling in APAC_NAMES:
        args = {"metric": metric, "filters": {dim: spelling}, "start": start, "end": end}
        verdicts[f"{dim}={spelling}"] = _serve(args)[0]
    distinct = set(verdicts.values())
    assert len(distinct) == 1, (
        f"the same scope got different verdicts depending on its spelling, {start}..{end}:\n"
        + "\n".join(f"    {k:<28} {'BLOCKED' if v else 'SERVED'}" for k, v in verdicts.items()))


# --------------------------------------------------------------------------- #
# 3. Metamorphic: a breakdown is not a way to ask more quietly
# --------------------------------------------------------------------------- #
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(metric=st.sampled_from(METRICS),
       start=st.sampled_from(DATES), end=st.sampled_from(DATES))
def test_breakdown_no_weaker_than_filter(metric, start, end):
    """A `group_by` row IS that member's number. If asking for APAC directly is blocked, a
    regional breakdown that hands back an APAC row must be blocked too."""
    if start > end:
        return
    direct = _serve({"metric": metric, "filters": {"region": "APAC"},
                     "start": start, "end": end})[0]
    if not direct:
        return
    blocked, cols, rows = _serve({"metric": metric, "group_by": ["region"],
                                  "start": start, "end": end})
    served_apac = not blocked and any("APAC" in r for r in rows)
    assert not served_apac, (
        f"region=APAC is blocked for {start}..{end}, but the same number came back in a "
        f"breakdown:\n  rows: {rows}")


# --------------------------------------------------------------------------- #
# 4. The named cases: all-time contamination, and over-refusal
# --------------------------------------------------------------------------- #
def test_all_time_breakdown_is_blocked():
    """A call with no period at all spans every row in the warehouse, so a regional breakdown
    reports an APAC number built partly from pre-launch rows."""
    blocked, cols, rows = _serve({"metric": "value_moments", "group_by": ["region"]})
    assert blocked or not any("APAC" in r for r in rows), (
        f"an all-time regional breakdown served an APAC number that includes pre-launch "
        f"rows: {rows}")


def test_unrestricted_region_is_not_over_refused():
    """The mirror failure: EMEA carries no launch window, so a period-less EMEA question is
    answerable. Refusing it invents a coverage problem and charges the refusal to the model."""
    blocked, _, _ = _serve({"metric": "value_moments", "filters": {"region": "EMEA"}})
    assert not blocked, "a period-less EMEA query was refused, but EMEA has no launch window"


TESTS = [test_served_calls_report_only_covered_scopes, test_same_scope_same_verdict,
         test_breakdown_no_weaker_than_filter, test_all_time_breakdown_is_blocked,
         test_unrestricted_region_is_not_over_refused]


def main() -> int:
    failed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"  OK   {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            first = str(exc).split("Falsifying example")[0].strip()
            print(f"  FAIL {fn.__name__}\n       " + first.replace("\n", "\n       ")[:700])
    if failed:
        print(f"\n{failed} of {len(TESTS)} gate properties FAIL — the guarantee is not universal yet.")
    else:
        print(f"OK — {len(TESTS)} gate properties hold across the generated call space.")
    return failed


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
