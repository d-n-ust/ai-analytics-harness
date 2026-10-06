"""Metric forks and their resolution, as the semantic layer declares them in `meta.terms`.

Two governed metrics that a bare word can reach ("users" as active users or active accounts) are a
fork. Which one answers is not decided here and not decided in governance.yml: each metric declares,
in its own `config.meta.terms`, the words it answers and when (always, for named teams, or only on
request). preflight reads those declarations and decides; this module asks it, so the agent at run
time and preflight in CI apply the same decision.

    resolve(metric, team, semantic, term) -> the metric to query and the decision record, or
                                        (metric, None) when the metric is in no declared fork, or the
                                        question does not use the fork's word
    vocabulary(semantic)             -> the fork words, for the question check to choose from
    companions(metric, team, semantic) -> the other metrics to report alongside it, when the
                                        declared outcome is to show every reading
"""
from __future__ import annotations

from functools import lru_cache

import preflight


# The question's word is not known (the arm has no question check): route on the agent's call, as
# before. A known word, or None for "the question uses no fork word", restricts routing to it.
ANY = object()


@lru_cache(maxsize=8)
def _facts(spec_dir: str) -> tuple:
    return tuple(f for f in preflight.load_metricflow(spec_dir) if f.kind == "metric")


def facts_of(semantic) -> tuple:
    """The layer's metrics with their declarations, read once per layer directory."""
    spec_dir = getattr(semantic, "spec_dir", None)
    return _facts(str(spec_dir)) if spec_dir else ()


def _fork_claims(facts: tuple, metric: str) -> list:
    """The claims of `metric` on words another metric also claims: the forks it is in."""
    mine = [c for f in facts if f.label == metric for c in f.claims]
    others = {w for f in facts if f.label != metric for c in f.claims for w in c.words}
    return [c for c in mine if set(c.words) & others]


def _fork_terms(facts: tuple, metric: str, term=ANY) -> list[str]:
    """The fork words of `metric`, or only the one the question uses when that is known."""
    claims = _fork_claims(facts, metric)
    if term is not ANY:
        claims = [c for c in claims if term is not None and term in c.words]
    return [c.term for c in claims]


def vocabulary(semantic) -> dict[str, tuple[str, ...]]:
    """Every fork word in the layer, with its synonyms: the closed list the question check reads the
    question against ("users", "habits", "marketing spend", "revenue" in experiment 07)."""
    facts = facts_of(semantic)
    out: dict[str, set] = {}
    for f in facts:
        for c in _fork_claims(facts, f.label):
            out.setdefault(c.term, set()).update(c.synonyms)
    return {t: tuple(sorted(s)) for t, s in sorted(out.items())}


def _decision(parameter, value, basis, disclose="", state="applied", why=""):
    return {"parameter": parameter, "value": value, "basis": basis, "quote": "", "disclose": disclose,
            "state": state, "why": why}


def _listing(outcome) -> str:
    return "; ".join(f"{m} ({r})" if r else m for m, r in zip(outcome.metrics, outcome.readings, strict=False))


def resolve(metric: str, team: str | None, semantic, term=ANY) -> tuple[str, dict | None]:
    """The metric to query for `metric` and the decision behind it, from the declared fork.

    One reading answers for this team: that metric is used and the others are disclosed. Several
    answer: the metric stands and every reading must be reported. None answers: the choice is the
    user's, so the call does not run and the agent asks.

    `term` is the fork word the question uses, when the question check has read it. The fork is a
    fact about that word, so a question that names the metric itself ("give me active_accounts"), or
    uses no fork word, routes nothing (h_013 was rerouted from the metric it named)."""
    facts = facts_of(semantic)
    for word in _fork_terms(facts, metric, term):
        outcome = preflight.readings(facts, word, team)
        if outcome is None:
            continue
        why = f"meta.terms: '{word}'"
        if outcome.action == "ask":
            return metric, _decision("metric", "?", "none", state="ungrounded",
                                     why=f"'{word}' has several governed readings and none is declared for "
                                         f"the {team or 'unnamed'} team: {_listing(outcome)}")
        if outcome.action == "one":
            routed, reading = outcome.metrics[0], outcome.readings[0]
            others = preflight.readings(facts, word, None)
            rest = [f"{m} ({r})" for m, r in zip(others.metrics, others.readings, strict=False)
                    if m != routed] if others else []
            return routed, _decision(
                "metric", routed, "governed_principle", why=why,
                disclose=(f"'{word}' has several governed readings. For the {team} team it means {routed}"
                          f"{f' ({reading})' if reading else ''}" + (f"; also governed: {', '.join(rest)}"
                                                                      if rest else "") + "."))
        return metric, _decision(
            "metric", metric, "governed_principle", why=why,
            disclose=f"'{word}' has several governed readings, and the rule is to show every one: "
                     f"{_listing(outcome)}. Report each figure with its reading.")
    return metric, None


def companions(metric: str, team: str | None, semantic, term=ANY) -> list[tuple[str, str, str]]:
    """(other metric, its reading, the term) for every reading that must be shown beside `metric`."""
    facts = facts_of(semantic)
    out = []
    for word in _fork_terms(facts, metric, term):
        outcome = preflight.readings(facts, word, team)
        if outcome is not None and outcome.action == "show_all" and metric in outcome.metrics:
            out += [(m, r, word) for m, r in zip(outcome.metrics, outcome.readings, strict=False) if m != metric]
    return out
