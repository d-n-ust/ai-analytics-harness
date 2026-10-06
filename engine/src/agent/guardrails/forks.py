"""Metric forks and their resolution, as the semantic layer declares them in `meta.terms`.

Two governed metrics that a bare word can reach ("users" as active users or active accounts) are a
fork. Which one answers is not decided here and not decided in governance.yml: each metric declares,
in its own `config.meta.terms`, the words it answers and when (always, for named teams, or only on
request). preflight reads those declarations and decides; this module asks it, so the agent at run
time and preflight in CI apply the same decision.

    resolve(metric, team, semantic)  -> the metric to query and the decision record, or (metric, None)
                                        when the metric is in no declared fork
    companions(metric, team, semantic) -> the other metrics to report alongside it, when the
                                        declared outcome is to show every reading
"""
from __future__ import annotations

from functools import lru_cache

import preflight


@lru_cache(maxsize=8)
def _facts(spec_dir: str) -> tuple:
    return tuple(f for f in preflight.load_metricflow(spec_dir) if f.kind == "metric")


def facts_of(semantic) -> tuple:
    """The layer's metrics with their declarations, read once per layer directory."""
    spec_dir = getattr(semantic, "spec_dir", None)
    return _facts(str(spec_dir)) if spec_dir else ()


def _fork_terms(facts: tuple, metric: str) -> list[str]:
    """The words `metric` claims that another metric also claims: the forks it is in."""
    mine = [c for f in facts if f.label == metric for c in f.claims]
    others = {w for f in facts if f.label != metric for c in f.claims for w in c.words}
    return [c.term for c in mine if set(c.words) & others]


def _decision(parameter, value, basis, disclose="", state="applied", why=""):
    return {"parameter": parameter, "value": value, "basis": basis, "quote": "", "disclose": disclose,
            "state": state, "why": why}


def _listing(outcome) -> str:
    return "; ".join(f"{m} ({r})" if r else m for m, r in zip(outcome.metrics, outcome.readings, strict=False))


def resolve(metric: str, team: str | None, semantic) -> tuple[str, dict | None]:
    """The metric to query for `metric` and the decision behind it, from the declared fork.

    One reading answers for this team: that metric is used and the others are disclosed. Several
    answer: the metric stands and every reading must be reported. None answers: the choice is the
    user's, so the call does not run and the agent asks."""
    facts = facts_of(semantic)
    for term in _fork_terms(facts, metric):
        outcome = preflight.readings(facts, term, team)
        if outcome is None:
            continue
        why = f"meta.terms: '{term}'"
        if outcome.action == "ask":
            return metric, _decision("metric", "?", "none", state="ungrounded",
                                     why=f"'{term}' has several governed readings and none is declared for "
                                         f"the {team or 'unnamed'} team: {_listing(outcome)}")
        if outcome.action == "one":
            routed, reading = outcome.metrics[0], outcome.readings[0]
            others = preflight.readings(facts, term, None)
            rest = [f"{m} ({r})" for m, r in zip(others.metrics, others.readings, strict=False)
                    if m != routed] if others else []
            return routed, _decision(
                "metric", routed, "governed_principle", why=why,
                disclose=(f"'{term}' has several governed readings. For the {team} team it means {routed}"
                          f"{f' ({reading})' if reading else ''}" + (f"; also governed: {', '.join(rest)}"
                                                                      if rest else "") + "."))
        return metric, _decision(
            "metric", metric, "governed_principle", why=why,
            disclose=f"'{term}' has several governed readings, and the rule is to show every one: "
                     f"{_listing(outcome)}. Report each figure with its reading.")
    return metric, None


def companions(metric: str, team: str | None, semantic) -> list[tuple[str, str, str]]:
    """(other metric, its reading, the term) for every reading that must be shown beside `metric`."""
    facts = facts_of(semantic)
    out = []
    for term in _fork_terms(facts, metric):
        outcome = preflight.readings(facts, term, team)
        if outcome is not None and outcome.action == "show_all" and metric in outcome.metrics:
            out += [(m, r, term) for m, r in zip(outcome.metrics, outcome.readings, strict=False) if m != metric]
    return out
