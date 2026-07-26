"""Guardrails at position AFTER: the checks a completed answer passes before it is served.

Industry calls these output guardrails. Three of them, each switched on separately so their
contributions are measured apart:

  governed_numbers   the served number is a governed result, or a comparison of two of the
                     same metric — never a composition of different ones
  output_validation  that number must be well-formed for its unit
  trajectory_verify  the metric must actually answer the question (judge.py — the one guardrail
                     here whose verdict is an opinion rather than a proof)

All three are refuse-only and asymmetric: a False verdict downgrades a confident answer to a
refusal, and none can ever rescue one. They can only add safety, never coverage.

Everything below takes what it needs as arguments rather than reaching for handles, so the
deterministic parts stay testable with plain dicts — the property that made the previous
verifier module worth keeping pure.
"""

from __future__ import annotations

import logging

from ..numbers import parse_numbers
from . import Position, Verdict, judge, note

_log = logging.getLogger(__name__)

# The judge's finding, named rather than cast onto the model's refusal vocabulary. It used to be
# coarsened into REFUSAL_REASONS — three kinds onto no_governed_definition, scope onto `other` —
# and then graded against what the question expected, which it mostly could not say.
_V_REASON = {kind: f"verifier_wrong_{kind}" for kind in
             ("thing", "kind", "scope", "definition", "segment")}

# --------------------------------------------------------------------------- #
# Deterministic output checks: provenance (governed_numbers, R7) + validation (R8)
# --------------------------------------------------------------------------- #
def num_match(a: float, b: float) -> bool:
    """Is one of these numbers a ROUNDING of the other?

    This is an identity test, not an approximation test — governed_numbers asks whether the
    served number IS a governed result (or a comparison of two), and the only difference it
    should forgive is the model writing 2685.08 for 2685.0766666.

    It used to be a tolerance band, `abs(a - b) <= max(0.5, 0.005 * abs(b))`, which failed at
    both ends. The 0.5 floor is large for a ratio: days_per_user 2.27 and 2.69 — two different
    weeks — counted as the same number, and the check validated whichever it happened to reach
    first. The 0.5% term is large for a count: 371 and 372 matched, which the old docstring
    explicitly promised they would not.

    Rounding to significant figures is deliberately not forgiven. A model writing 2690 for
    2685.08 has not served a governed result; it has served an approximation of one, and this
    guardrail exists to tell those apart."""
    if a == b:
        return True
    return any(a == round(b, k) or b == round(a, k) for k in range(7))


def step_values(step: dict) -> list:
    """The typed numeric results a query_metric step returned. Prefers the typed `result_values`
    the dispatcher now records; falls back to parsing the display text only for older traces
    (which had no typed field), so the checks never depend on scraping numbers out of prose/SQL."""
    v = step.get("result_values")
    if v is not None:
        return [float(x) for x in v]
    return parse_numbers(step.get("result"))


# Tools whose results are GOVERNED: the layer compiled them, or the tree derived them from
# metrics the layer compiled, through an identity it declares. Asked by capability rather than
# hardcoded at each use — the previous check named `query_metric` in three places, so the metric
# tree could produce eighteen governed figures and be refused as hand-composed.
_GOVERNED_TOOLS = ("query_metric", "explain_change")


def _governed_results(steps: list):
    """Every number a governed tool produced, with a label for what it is."""
    for s in steps or []:
        if s.get("tool") not in _GOVERNED_TOOLS or s.get("error"):
            continue
        args = s.get("args") or {}
        label = args.get("metric") or args.get("node") or s.get("tool")
        for v in step_values(s):
            yield label, v


def _same_metric_results(steps: list) -> dict:
    """Governed results grouped by the metric they are instances of.

    Only `query_metric`, because only there does one call's whole result belong to one named
    metric. A decomposition spans several, and every figure in it is already a governed result in
    its own right — the tree computed it — so it never needs to be reached by comparison."""
    groups: dict[str, list] = {}
    for s in steps or []:
        if s.get("tool") != "query_metric" or s.get("error"):
            continue
        metric = (s.get("args") or {}).get("metric")
        if metric:
            groups.setdefault(metric, []).extend(step_values(s))
    return groups


def _renderings(x: float):
    """A number, and the same number written as a percentage. Multiplying a rate by 100 changes
    how a figure is displayed, never what it means, so 53.22 stands for a governed 0.5322."""
    yield x
    yield x * 100


def account_for(declared_value, steps: list) -> str | None:
    """Where does this number come from? Returns the account, or None if there is none.

    The rule, in one line: YOU MAY COMPARE GOVERNED NUMBERS, YOU MAY NOT COMPOSE NEW ONES.

      (a) the number IS a governed result, or
      (b) it is a comparison of two governed results OF THE SAME METRIC — a difference, a ratio
          or a percent change.

    The distinction is not whether arithmetic happened; both `ARR = mrr x 12` and `value moments
    fell 11.9%` are one operation on a governed result, and no rule about the arithmetic can
    separate them. It is whether the result claims to be a NEW QUANTITY or a relationship between
    instances of an existing one. Comparing one metric across two scopes leaves its definition
    untouched — only the filter moved — so the governed definition still says what the number
    means. Combining two different metrics invents a measure nothing defines, which is exactly
    what `mrr / marketing_spend` does when a question asks for return on ad spend.

    This is why a decomposition survives: "active users rose 5.98% while days_per_user fell
    16.44%" is two same-metric comparisons side by side. The sentence combines them; no number
    does. Its predecessor accepted only (a), restricted to one tool, and refused the diagnostic
    tier twelve times in fifteen.
    """
    for metric, v in _governed_results(steps):
        for candidate in _renderings(v):
            if num_match(declared_value, candidate):
                return f"{metric} = {v:g}"
    for metric, values in _same_metric_results(steps).items():
        for a in values:
            for b in values:
                if a == b or not b:
                    continue
                for base, op in ((a - b, "difference"), (a / b, "ratio"),
                                 ((a - b) / b, "percent change")):
                    for candidate in _renderings(base):
                        if num_match(declared_value, candidate):
                            return f"{op} of two {metric} results ({a:g}, {b:g})"
    return None


def _provenance(declared_value, steps: list, source_metric, metrics, source_result=None):
    """Which governed metric produced the answer, its call args, and the value it returned
    — taken ONLY from the model's typed `source_metric` declaration, never inferred from the
    answer text. When that metric was queried more than once (say a breakdown and a total),
    the model's typed `declared_value` selects WHICH of ITS OWN calls produced the reported
    number, so the grain and the governed value are read from the right call. That is picking
    a call of an already-known metric, not guessing the metric — a value shared by two
    different metrics can never mislink, because the metric is declared. Returns
    (metric, args, value), or (None, None, None) when nothing verifiable was declared."""
    if source_metric not in metrics:
        return None, None, None
    # BY REFERENCE first. The model names the handle of the result it reported, so this is a
    # lookup. Matching numbers was only ever a way to guess the same thing, and a guess needs a
    # tolerance, and every tolerance is wrong for some metric: a 0.5 floor made two different
    # weeks of days_per_user (2.27 and 2.69) the same number, and the checks then validated a
    # figure nobody served.
    if source_result:
        named = next((s for s in (steps or []) if s.get("handle") == str(source_result).strip("[]")),
                     None)
        if named is not None and (named.get("args") or {}).get("metric") == source_metric:
            values = step_values(named)
            # num_match returns to its real job here: verifying the declared number IS that
            # result, rather than searching for which result it might have been.
            hit = next((v for v in values if num_match(declared_value, v)), None)
            return source_metric, (named.get("args") or {}), hit
    calls = [s for s in (steps or []) if s.get("tool") == "query_metric"
             and (s.get("args") or {}).get("metric") == source_metric]
    if not calls:
        return None, None, None
    # No handle given (an older trace, or the model did not name one) — fall back to the search,
    # but say when it is a guess rather than settling it silently.
    matching = [st for st in calls
                if any(num_match(declared_value, v) for v in step_values(st))]
    if len(matching) > 1:
        _log.info("provenance: %d calls to %s match the served value; taking the last",
                  len(matching), source_metric)
    for step in reversed(calls):
        # The matching cell, not the call's first one: a breakdown returns a number per group,
        # and the declared value says WHICH group the answer reported. Handing the checks the
        # first row instead means R8 range-checks a figure nobody served and R9 judges it.
        match = next((v for v in step_values(step)
                      if declared_value is not None and num_match(declared_value, v)), None)
        if match is not None:
            return source_metric, (step.get("args") or {}), match
    # Nothing the metric returned matches what was served. A single-row call is still
    # unambiguous; from a breakdown there is no defensible "the governed value", so report
    # none and let the checks refuse rather than validate an arbitrary row. (With R7 on this
    # is unreachable: an unmatched value is already a hand-composition.)
    last = step_values(calls[-1])
    return source_metric, (calls[-1].get("args") or {}), (last[0] if len(last) == 1 else None)


def _infer_source_metric(declared_value, steps: list, metrics) -> str | None:
    """The governed metric a served number came from, when exactly ONE of them produced it.

    Provenance is normally the model's own typed declaration and never inferred, so that a value
    two metrics happen to share cannot mislink. That property is preserved here by attributing
    only when a single queried metric returned this number — there is then nothing to confuse it
    with. Without this, an answer that names no `source_metric` (or a number recovered from the
    answer text) satisfies R7 and then skips R8 and R9 for want of a declaration, which is the
    same hole one level down."""
    hits = {(s.get("args") or {}).get("metric") for s in steps or []
            if s.get("tool") == "query_metric"
            and any(num_match(declared_value, v) for v in step_values(s))}
    named = {m for m in hits if m in metrics}
    return named.pop() if len(named) == 1 else None


def output_validation(metric_def: dict, value) -> Verdict:
    """Deterministic checks on the RETURNED value, not the metric selection: a governed
    query that came back empty/null, or a value impossible for its `unit`, must not be
    served as an answer. Refuse-only. This is where the metric-selection check can't see —
    it never looks at *what came back*."""
    if value is None:
        return Verdict(False, "result_empty", guardrail="output_validation", detail=
                       "the metric produced no number for this request, so there is nothing to "
                       "report; refuse.",
                       missing="the governed query returned no value (empty/null result)")
    unit = (metric_def or {}).get("unit")
    if value < 0 and unit in ("count", "currency", "share"):
        return Verdict(False, "implausible_value", guardrail="output_validation", detail=
                       f"the governed result {value} is impossible for a {unit} metric; refuse.",
                       missing=f"a {unit} value cannot be negative (got {value})")
    if unit == "share" and value > 100:
        return Verdict(False, "implausible_value", guardrail="output_validation", detail=
                       f"the governed result {value} is out of range for a share; refuse.",
                       missing=f"a share above 100 (got {value})")
    return Verdict.ok()


def verify_answer(semantic, question: str, answer_text: str | None, steps: list,
                  record=None, source_metric: str | None = None, declared_value=None,
                  source_result: str | None = None,
                  run_output_validation: bool = True, run_governed_numbers: bool = False,
                  verify_traj=None) -> Verdict:
    """Run the output guardrails on a completed answer. Return (ok, reason, missing, explanation);
    ok=False means convert the answer into a refuse. Each check is toggled by its own rung so
    the deltas are measured separately: `run_governed_numbers` (R7, the served number is a
    governed result or a comparison of two of the same metric), `run_output_validation` (R8,
    well-formed value), and `verify_traj` (R9, the trajectory judge). `source_metric`/
    `declared_value` are the model's typed provenance. The checks apply to a NUMERIC answer, so
    prose (no `declared_value`) passes through untouched. Refuse-only: it can turn an answer into
    a refusal, never the reverse."""
    if semantic is None or not answer_text or declared_value is None:
        return Verdict.ok()

    if run_governed_numbers:
        account = account_for(declared_value, steps)
        note(record, "governed_numbers", Position.AFTER,
             "allowed" if account else "refused",
             account or "the served number is neither a governed result nor a comparison of two")
        if account is None:
            # Nothing governed produces this number, and no comparison of one metric with itself
            # reaches it — so it is a COMPOSITION, and no governed definition covers what was
            # asked (ARR = mrr x 12; revenue per dollar spent from mrr and marketing_spend).
            # Report that root cause rather than a vague 'out_of_scope': a coverage gap is one
            # typed signal, so downstream can label it and name the metric worth defining.
            return Verdict(
                False, "no_governed_definition", guardrail="governed_numbers", detail=
                "this number was composed from different metrics (a rate times a count, metric A "
                "over metric B), not read from a governed result or reached by comparing one "
                "metric with itself. No governed definition covers what was asked — refuse and "
                "name the metric that would need to exist, rather than serve a hand-built figure.",
                missing="no governed result produces this number, and no comparison of a single "
                        "metric across scopes reaches it (it combines different metrics)")

    if source_metric is None:              # undeclared, but attributable when unambiguous
        source_metric = _infer_source_metric(declared_value, steps, semantic.metrics)
    metric, args, value = _provenance(declared_value, steps, source_metric, semantic.metrics,
                                      source_result)
    if metric is None:                     # a numeric answer we can't attribute -> measure it
        _log.info("output checks: numeric answer with no usable source_metric; not verified")
        return Verdict.ok()                # no governed metric to check against
    metric_def = semantic.metrics[metric]

    if run_output_validation:                         # R8: the returned value is empty or impossible
        verdict = output_validation(metric_def, value)
        note(record, "output_validation", Position.AFTER,
             "refused" if not verdict.allowed else "allowed",
             verdict.reason or f"{value:g} is well-formed for a {metric_def.get('unit')}")
        if not verdict.allowed:
            return verdict

    if verify_traj is not None:            # R9: does this metric + SQL actually answer the question?
        ok_v, mismatch, reason_v = verify_traj(question, metric, metric_def, args, value,
                                               declared_value, answer_text)
        note(record, "trajectory_verify", Position.AFTER, "allowed" if ok_v else "refused",
             reason_v if not ok_v else "the judge found no mismatch")
        if not ok_v:
            return Verdict(False, _V_REASON.get(mismatch, "verifier_other"), reason_v,
                           missing=f"verifier[{mismatch}]: {reason_v}"[:180],
                           guardrail="trajectory_verify")

    return Verdict.ok()


# --------------------------------------------------------------------------- #
# The hook: run every AFTER guardrail on one completed answer.
# --------------------------------------------------------------------------- #
def served_text(args: dict) -> str:
    """Everything the analyst said, as one string — the claim the judge is checking the number
    against.

    Both fields, because the answer tool splits one claim across them and which field holds the
    substance varies: 'is the app healthy?' comes back with the assessment in `answer`, while
    'which lever weakened?' answers `frequency` and puts the whole argument in `explanation`.
    Shown only `answer`, the judge would be reading one word. evals/grade.py already scores
    diagnostic and keyword cases on both fields for the same reason — this keeps the judge
    checking the text the grader grades.
    """
    return " ".join(str(args.get(k) or "").strip() for k in ("answer", "explanation")).strip()


def check(args: dict, declared, run, record=None) -> Verdict:
    """Put an answer through the AFTER guardrails. A refusing verdict turns the answer into a
    refusal carrying the coded reason it failed for.

    `run` supplies the live handles — the semantic layer, the guardrail set, the trace, a model
    to judge with — and receives the judge's verdict back on `last_verdict`, so a stored run is
    enough to score the judge later without re-running anything."""
    g, semantic = run.grounding.guardrails, run.grounding.semantic
    if semantic is None or not (g.output_validation or g.governed_numbers or g.trajectory_verify):
        return Verdict.ok()
    if declared is None:
        for name in ("governed_numbers", "output_validation", "trajectory_verify"):
            if getattr(g, name):
                note(record, name, Position.AFTER, "stood down", "the answer is prose, not a number")
        return Verdict.ok()
    # the judge is a careful checker — run it on its own (higher-reasoning) model when given
    model = run.verifier_model or run.model
    verify_traj = _trajectory_verifier(run, model) if (g.trajectory_verify and model) else None
    return verify_answer(
        semantic, run.question, served_text(args), run.steps, record=record,
        source_metric=args.get("source_metric"), declared_value=declared,
        source_result=args.get("source_result"),
        run_output_validation=g.output_validation,
        run_governed_numbers=g.governed_numbers, verify_traj=verify_traj)


def governed_notes(args: dict, semantic) -> list[str]:
    """Modifications the LAYER applied to this query, so the judge reads them as definitional
    rather than as the analyst narrowing scope: a named segment (real_acquisition drops test
    channels), and a member's availability window (a period clipped to on/after launch is
    governed, not invented).

    Members come from the layer's own resolver, so a country scope earns its region's note and a
    synonym is recognised — the same fix the BEFORE guardrail needed, for the same reason. Only
    members the analyst NAMED get a note; a breakdown's members were not chosen, and the coverage
    check has already refused any that fall outside it."""
    a = args or {}
    if semantic is None:
        return []
    notes = []
    seg = a.get("segment")
    if seg:
        spec = semantic.governance.get("segments", {}).get(seg, {})
        notes.append(f"governed segment '{seg}' — "
                     f"{spec.get('description', 'a governed reusable filter')}")
    for dim, member in semantic.scope_members(a.get("filters")):
        starts = semantic.available_from(dim, member)
        if starts:
            notes.append(f"{dim} {member} data starts {starts}; months the question names "
                         f"before this are out of coverage (pre-launch), so the in-coverage "
                         f"window (on/after {starts}) IS the correct answer — excluding them "
                         "is required, not narrowing")
    return notes


def _trajectory_verifier(run, model):
    """A callable the judge is driven through: it recompiles the SQL the analyst ran and hands
    over the analyst's ADDED filters separately from the metric's definitional clauses — the
    separation an isolated test showed is load-bearing."""
    def go(question, metric, metric_def, args, gov_value, claim, claim_text):
        a = args or {}
        semantic = run.grounding.semantic
        sql = semantic.compile(metric, group_by=a.get("group_by"), filters=a.get("filters"),
                               time_grain=a.get("time_grain"), start=a.get("start"),
                               end=a.get("end"), period=a.get("period"),
                               resolve=run.grounding.guardrails.resolve, segment=a.get("segment"))
        window = a.get("period") or (f"{a.get('start')}..{a.get('end')}"
                                     if (a.get("start") or a.get("end")) else None)
        j = judge.verify_trajectory(
            model, question, metric, metric_def, sql, gov_value, claim,
            applied_filters=a.get("filters"), time_window=window,
            governed_notes=governed_notes(a, semantic), claim_text=claim_text)
        run.last_verdict = {"answers_question": j.answers_question, "mismatch": j.mismatch,
                            "reason": j.reason, "value_role": j.value_role,
                            "metric": metric, "sql": sql, "applied_filters": a.get("filters"),
                            "time_window": window, "governed_value": gov_value, "claim": claim,
                            "claim_text": claim_text}
        return j.answers_question, j.mismatch, j.reason
    return go
