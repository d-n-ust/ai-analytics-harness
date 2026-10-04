"""The final-action half of `decision_grounding`: the reply must be legal under the reading.

`decision_grounding` reads the question once into sets of values (guardrails/decisions.py) and checks
each call against them, so the agent may explore freely. Two things that check cannot see are checked
here, when the agent ends the run:

  uncovered_values      an answer whose used calls leave out a value the question names. "June
                        compared with May" answered with June alone passes every call check.
                        The covering queries are run here and handed back with the correction.
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


def _reading_at_exit(run):
    """(reading, refusal) for the final-action check. `refusal` is set when the catalogue itself
    answers: the question names a measure no governed metric counts."""
    tb = run.grounding.toolbox
    metrics = getattr(tb.semantic, "metrics", None) or {}
    metric = next((m for m, r in run.grounded.items() if isinstance(r, dict) and "periods" in r), "")
    if metric not in metrics:
        choice, p, cost = _decisions.choose_metric(run.question, metrics)
        _charge(run, cost)
        if choice == "not_in_list" and p >= _decisions.CONFIDENT:
            return None, ("[policy] Your clarifying question was not accepted: no governed metric measures "
                          "what the question asks for, so there is nothing to clarify. Refuse with "
                          "`no_governed_definition`.", "no_governed_definition")
        if choice not in metrics or p < _decisions.CONFIDENT:
            return None, None                    # the metric itself is open: asking about it is legal
        metric = route_metric(choice, tb.governance)[0]
    reading, cost = _decisions.reading_for(run.question, metric, tb.semantic, tb.con, tb.governance,
                                           run.grounded)
    _charge(run, cost)
    return reading, None


def _charge(run, cost: float) -> None:
    """Decision-model requests are billed per request. One made at the final action is charged to the
    turn that ended the run, the way a call's grounding is charged to its step."""
    if cost and run.turns:
        run.turns[-1]["grounding_cost_usd"] = run.turns[-1].get("grounding_cost_usd", 0.0) + cost


def exit_matches_reading(run, exit_call):
    """Hand back a clarifying question or a refusal the reading does not allow. A [policy] hand-back
    (the reading refuses) is converted to that refusal if the budget runs out."""
    if exit_call.name not in ("clarify", "refuse") or not getattr(run.grounding.toolbox.g, "decision_grounding", False):
        return None
    args = exit_call.args or {}
    reading, verdict = _reading_at_exit(run)
    if verdict is not None and exit_call.name == "refuse":
        verdict = None                           # no governed metric: a refusal is the legal reply
    if verdict is None and reading is not None:
        verdict = (_decisions.exit_verdict(reading, args) if exit_call.name == "clarify" else
                   _decisions.refusal_verdict(reading, str(args.get("reason") or "")))
    if verdict is None:
        return None
    message, reason = verdict
    run.repairs.append({"exit_reading": message[:200], "refuse": reason})
    run.acts.append(Act("exit_matches_reading", str(Position.REPAIR), "handed back",
                        message[:160]).as_dict())
    return ToolResult(message, is_error=True, reason=reason)
