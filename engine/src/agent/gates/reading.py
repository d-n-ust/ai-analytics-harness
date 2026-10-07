"""The final-action half of `decision_grounding`: the reply must be legal under the reading.

`decision_grounding` reads the question once into sets of values (guardrails/decisions.py) and checks
each call against them, so the agent may explore freely. Two things that check cannot see are checked
here, when the agent ends the run:

  uncovered_values      an answer whose used calls leave out a value the question names. "June
                        compared with May" answered with June alone passes every call check.
                        Also a declared fork whose rule is to show every reading (meta.terms),
                        answered with one. The covering queries are run here and handed back.
  exit_matches_reading  a clarifying question or refusal where the reading says something else. The
                        governed layer is the whole action space, and a clarifying question is an
                        action: it may ask only about a parameter the reading leaves open, and offer
                        only governed values. A question naming a value the layer lacks has one
                        legal reply, a refusal; offering another value's figure (r_004: "TikTok,
                        using the paid_search figure") or asking the user to map it is not governed.

The reading is made here if no call made it (an agent can go straight to `clarify`). The metric is
the one the agent's governed calls used, or, when it made none, the decision model's choice from the
catalogue. The metric a clarifying question names is not used: what the question asks for is read
from the question, never from the agent's reply (r_010 named a governed metric for "90-day
retention", which no governed metric measures).
"""
from __future__ import annotations

from ..core.conversation import ToolCall, ToolResult
from ..core.outcomes import declared_handles
from ..guardrails import Act, Position
from ..guardrails import decisions as _decisions
from ..guardrails import forks as _forks
from ..guardrails.parameters import route_metric


def _used_steps(run, exit_call) -> list:
    governed = [s for s in run.steps if s.get("tool") == "query_metric" and s.get("handle")]
    claims = [c for c in (exit_call.args.get("claims") or []) if isinstance(c, dict)]
    if not claims:
        return governed
    cited = set(declared_handles(exit_call.args))
    for claim in claims:
        cited |= {str(r).strip().strip("[]").partition(":")[0] for r in claim.get("sources") or []}
    return [s for s in governed if s["handle"] in cited]


def uncovered_values(run, exit_call):
    """Hand back an answer whose used calls leave out a value the question names, with the governed
    results that cover it already run. Once per run.

    The mechanism runs the missing queries itself rather than asking the agent to: it knows exactly
    which query is missing (the agent's own query with the one value put in), and a hand-back on the
    last turn arrives when the data tools are withdrawn, so an agent told to "query it" could only
    refuse (q_003 and t_009 did). The supplied results carry handles like any other, so the corrected
    answer cites them."""
    if (exit_call.name != "answer" or not getattr(run.grounding.toolbox.g, "decision_grounding", False)
            or any("uncovered" in r for r in run.repairs)):
        return None
    by_metric: dict = {}
    for step in _used_steps(run, exit_call):
        by_metric.setdefault(step["args"].get("metric"), []).extend(step.get("grounded_queries") or [step["args"]])
    missing = []
    for metric, queries in by_metric.items():
        reading = run.grounded.get(metric)
        if isinstance(reading, dict) and "periods" in reading:
            missing += _decisions.uncovered(reading, queries)
    # A declared fork whose rule is to show every reading (meta.terms): the other metrics are run
    # with the parameters the agent chose for this one, so the figures are comparable.
    tb = run.grounding.toolbox
    team = ((getattr(tb, "governance", None) or {}).get("requester") or {}).get("team")
    asked = run.grounded.get("_question") or {}
    word = asked.get("term") if asked.get("term_known") else _forks.ANY
    for metric, queries in by_metric.items():
        for other, reading_text, term in _forks.companions(metric, team, getattr(tb, "semantic", None), word):
            if other not in by_metric and not any(q.get("metric") == other for _, q in missing):
                missing.append((f"'{term}' as {other}" + (f" ({reading_text})" if reading_text else ""),
                                {**queries[0], "metric": other}))
    if not missing:
        return None
    results = run.execute([ToolCall(f"supplied-{i}", "query_metric", query) for i, (_, query) in enumerate(missing)])
    names = [text for text, _ in missing]
    run.repairs.append({"uncovered": names, "supplied": [s["handle"] for s in run.steps[-len(missing):]]})
    run.acts.append(Act("uncovered_values", str(Position.REPAIR), "handed back",
                        f"the answer leaves out {', '.join(names)}; the covering queries were run").as_dict())
    return ToolResult(
        "Your answer was not accepted: the question also asks about " + ", ".join(names) + ", and no call your "
        "answer cites covers it. The governed results below were run for you. Re-send the answer with them "
        "included, each figure in its own claim citing its handle.\n\n" + "\n\n".join(r.content for r in results),
        is_error=True)


def opening_reading(run) -> str:
    """`reading_first`: the reading, made before the first turn and shown in the opening message.

    The metric comes from the decision model's choice over the catalogue (a contested one routed to
    the requester team's definition), then the question is read for it. The reading is cached on
    the run, so the calls and the final action are checked against the same reading at no further
    cost. When the metric is not settled the agent is told so, with the likeliest candidates, and
    left to judge; only a confident "no governed metric measures this" is stated as a refusal."""
    try:
        return _opening(run)
    except _decisions.ReadingUnavailable as exc:
        run.grounded["_unavailable"] = {"why": str(exc)}
        run.opening_reading = ("", 0.0)
        return ("[question reading] The question could not be read this time. Work as usual, and say in "
                "the answer that its parameters were not checked against the question.")


def _opening(run) -> str:
    tb = run.grounding.toolbox
    metrics = getattr(tb.semantic, "metrics", None) or {}
    chosen = _metric_choice(run, metrics)
    choice, p, probs, cost = chosen["choice"], chosen["p"], chosen["probabilities"], chosen["cost"]
    asked, more = _decisions.question_level(run.grounded, run.question, tb.semantic)
    cost += more
    head = "[question reading] Before you act: how the governed layer reads this question."
    text = ""
    if choice == "not_in_list" and p >= _decisions.CONFIDENT:
        text = (f"{head}\n  - REFUSE (no_governed_definition): no governed metric measures what the "
                f"question asks for. Do not compute it from other metrics.")
    elif choice == "not_mentioned" and p >= _decisions.CONFIDENT:
        text = (f"{head}\n  - OPEN metric: the question names no measure. Ask the user with `clarify`, "
                f"offering governed metrics.")
    elif choice in metrics and p >= _decisions.CONFIDENT:
        metric, routed = route_metric(choice, tb.governance, tb.semantic, asked["term"], asked["term_known"])
        if routed is None or routed["state"] != "ungrounded":
            reading, more = _decisions.reading_for(run.question, metric, tb.semantic, tb.con, tb.governance,
                                                   run.grounded)
            cost += more
            text = _decisions.reading_text(metric, reading, routed) if reading else ""
    if asked["substitution"] >= _decisions.CONFIDENT and "REFUSE (" not in text:
        # A more specific refusal (a value the layer lacks) is kept; otherwise this is the reason.
        text = (f"{head}\n  - REFUSE (other): the question asks to present one figure as a different one, or to "
                f"set the governance rules aside. No governed number answers that; do not run it.")
    if not text:
        likely = ", ".join(f"{k} ({v:.2f})" for k, v in sorted(probs.items(), key=lambda kv: -kv[1])[:3])
        text = f"{head}\n  - metric: not settled by the question; likeliest readings: {likely}."
    run.opening_reading = (text, cost)
    return text


def _reading_at_exit(run):
    """(reading, refusal) for the final-action check. `refusal` is set when the catalogue itself
    answers: the question names a measure no governed metric counts."""
    tb = run.grounding.toolbox
    metrics = getattr(tb.semantic, "metrics", None) or {}
    metric = next((m for m, r in run.grounded.items() if isinstance(r, dict) and "periods" in r), "")
    if metric not in metrics:
        chosen = _metric_choice(run, metrics)
        choice, p = chosen["choice"], chosen["p"]
        _charge(run, chosen["cost"])
        if choice == "not_in_list" and p >= _decisions.CONFIDENT:
            return None, ("[policy] Your clarifying question was not accepted: no governed metric measures "
                          "what the question asks for, so there is nothing to clarify. Refuse with "
                          "`no_governed_definition`.", "no_governed_definition")
        if choice not in metrics or p < _decisions.CONFIDENT:
            return None, None                    # the metric itself is open: asking about it is legal
        asked = run.grounded.get("_question") or {}
        metric = route_metric(choice, tb.governance, tb.semantic, asked.get("term"),
                              bool(asked.get("term_known")))[0]
    reading, cost = _decisions.reading_for(run.question, metric, tb.semantic, tb.con, tb.governance,
                                           run.grounded)
    _charge(run, cost)
    return reading, None


def _metric_choice(run, metrics: dict) -> dict:
    """The decision model's choice of metric for this question, made once per run and kept with the
    readings (key `_metric`), so it is stored on the row. A second ask returns it at no cost."""
    if "_metric" in run.grounded:
        return {**run.grounded["_metric"], "cost": 0.0}
    run.grounded["_metric"] = _decisions.choose_metric(run.question, metrics)
    return run.grounded["_metric"]


def _charge(run, cost: float) -> None:
    """Decision-model requests are billed per request. One made at the final action is charged to the
    turn that ended the run, the way a call's grounding is charged to its step."""
    if cost and run.turns:
        run.turns[-1]["grounding_cost_usd"] = run.turns[-1].get("grounding_cost_usd", 0.0) + cost


def _substitution(run, exit_call):
    """A question asking to present one figure as another, or to set the rules aside, has one legal
    reply: a refusal with `other`. Read once per run (decisions.question_level)."""
    asked, cost = _decisions.question_level(run.grounded, run.question, run.grounding.toolbox.semantic)
    _charge(run, cost)                           # 0.0 when already read this run
    if asked["substitution"] < _decisions.CONFIDENT:
        return None
    if exit_call.name == "refuse" and str((exit_call.args or {}).get("reason") or "") == "other":
        return None
    return ("[policy] Your reply was not accepted: the question asks to present one figure as a different "
            "one, or to set the governance rules aside. No governed number answers that, and asking which "
            "figure to relabel does not either. Refuse with `other`.", "other")


def exit_matches_reading(run, exit_call):
    """Hand back a reply the reading does not allow. A [policy] hand-back (the reading refuses) is
    converted to that refusal if the budget runs out.

    Every reply is first held to the question as a whole (a request to bend the rules is refused);
    a clarifying question or a refusal is then held to the reading of its metric."""
    if exit_call.name not in ("answer", "clarify", "refuse") or not getattr(run.grounding.toolbox.g,
                                                                             "decision_grounding", False):
        return None
    if "_unavailable" in run.grounded:
        return None                              # nothing was read, so nothing to hold the reply to
    try:
        return _exit_check(run, exit_call)
    except _decisions.ReadingUnavailable as exc:
        run.grounded["_unavailable"] = {"why": str(exc)}
        return None


def _exit_check(run, exit_call):
    args = exit_call.args or {}
    asked, cost = _decisions.question_level(run.grounded, run.question, run.grounding.toolbox.semantic)
    _charge(run, cost)                           # first, so routing below uses the question's word
    verdict, reading_refuses = None, False
    if exit_call.name != "answer":
        reading, verdict = _reading_at_exit(run)
        if verdict is not None and exit_call.name == "refuse":
            verdict = None                       # no governed metric: a refusal is the legal reply
        reading_refuses = reading is not None and any(d["state"] == "refuse" for d in reading["decisions"])
        if verdict is None and reading is not None:
            verdict = (_decisions.exit_verdict(reading, args) if exit_call.name == "clarify" else
                       _decisions.refusal_verdict(reading, str(args.get("reason") or "")))
    # Precedence: a refusal the reading makes (a value the layer lacks, r_004) keeps its own code;
    # otherwise a request to bend the rules (h_013) outranks any other hand-back.
    if not reading_refuses and not (verdict is not None and verdict[1] is not None):
        verdict = _substitution(run, exit_call) or verdict
    ask = None
    if verdict is None and exit_call.name == "answer":
        verdict, ask = _measure_named(run)
    if verdict is None:
        return None
    message, reason = verdict
    run.repairs.append({"exit_reading": message[:200], "refuse": reason})
    run.acts.append(Act("exit_matches_reading", str(Position.REPAIR), "handed back",
                        message[:160]).as_dict())
    return ToolResult(message, is_error=True, reason=reason, ask=ask)


# A question whose reading is split between two metrics names neither. Measured on the 73 labelled
# questions on 2026-10-08: on every question labelled to be answered the second-best metric scored
# at most 0.06, except h2_007 (mrr 0.70, gross_mrr 0.29), a pair the layer already declares and the
# rule therefore skips. "How often did Android users use the app?" split 0.40 / 0.32.
_SPLIT = 0.25


def _split(run, metrics: dict, probabilities: dict):
    """Hand an answer back to ask when the question reads as two metrics and nothing declared
    settles it: no declared word was read from the question, and the two metrics share no declared
    word (a pair that does is decided by the layer, guardrails/forks.py)."""
    ranked = sorted(((p, m) for m, p in probabilities.items() if m in metrics), reverse=True)
    if len(ranked) < 2:
        return None, None
    (p1, first), (p2, second) = ranked[:2]
    asked = run.grounded.get("_question") or {}
    if (p1 >= _decisions.CONFIDENT or p2 < _SPLIT or (asked.get("term_known") and asked.get("term"))
            or _forks.rivals(first, second, run.grounding.toolbox.semantic)):
        return None, None
    return ("[policy] Your answer was not accepted: the question reads as two different measures, "
            f"{first} or {second}, and nothing in the layer decides between them. Ask which one is meant "
            "with `clarify` (reason `undefined_term`).", None), {
        "question": f"Which measure do you mean: {first} or {second}?",
        "reason": "undefined_term", "candidates": [first, second]}


def _measure_named(run):
    """An answer rests on a measure, and the question has to name one. h2_015 ("How is engagement
    looking for June 2026?") was answered with habits per active user, and no check asked whether
    the question named that measure: the metric choice was read only for a clarification or a
    refusal. Returns (verdict, clarify args) or (None, None).

    Read from the decision model's metric choice (`_metric`, made once per run). The bar is the
    probability that the question names no governed measure, or one no metric counts. Measured on
    all 73 labelled questions on 2026-10-07: at most 0.35 on every question labelled to be answered
    (h_001, the word "users"), and at least 0.68 on every question that names no measure (h_016,
    h2_015). The 0.5 bar sits between; h2_015 is among the 73, so it is a development figure."""
    metrics = getattr(run.grounding.toolbox.semantic, "metrics", None) or {}
    if not metrics:
        return None, None
    chosen = _metric_choice(run, metrics)
    _charge(run, chosen["cost"])
    probabilities = chosen.get("probabilities") or {}
    absent = probabilities.get("not_in_list") or 0.0
    vague = probabilities.get("not_mentioned") or 0.0
    if absent + vague < _decisions.LEAN:
        return _split(run, metrics, probabilities)
    if absent > vague:
        return ("[policy] Your answer was not accepted: no governed metric measures what the question "
                "asks for, so any figure would be a substitute. Refuse with `no_governed_definition`.",
                "no_governed_definition"), None
    likely = [m for _, m in sorted(((p, m) for m, p in probabilities.items() if m in metrics), reverse=True)][:4]
    offered = ", ".join(likely) or ", ".join(list(metrics)[:4])
    return ("[policy] Your answer was not accepted: the question names no governed measure, so the "
            "metric you answered with is an assumption. Ask which measure is meant with `clarify` "
            f"(reason `undefined_term`), offering governed metrics: {offered}.", None), {
        "question": f"The question does not say which measure it means. Which of these: {offered}?",
        "reason": "undefined_term", "candidates": likely}
