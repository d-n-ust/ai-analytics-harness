"""Metric forks and their resolution, as the semantic layer declares them in `meta.terms`.

Two governed metrics that a bare word can reach ("users" as active users or active accounts) are a
fork. Which one answers is not decided here and not decided in governance.yml: each metric declares,
in its own `config.meta.terms`, the words it answers and when (always, for named teams, or only on
request). preflight reads those declarations and decides; this module asks it, so the agent at run
time and preflight in CI apply the same decision.

    resolve(metric, team, semantic, term) -> the metric to query and the decision record, or
                                        (metric, None) when the metric is in no declared fork, or the
                                        question does not use the fork's word
    vocabulary(semantic)             -> every declared word, for the question check to choose from
    longest_term(question, term, …)  -> the longest declared phrase containing the chosen word
    companions(metric, team, semantic) -> the other metrics to report alongside it, when the
                                        declared outcome is to show every reading
"""
from __future__ import annotations

import re
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
    """Every word the layer declares for a metric, with its synonyms: the closed list the question
    check reads the question against ("users", "customers", "paying customers", "app opens", ...).
    A word one metric claims routes the question to it; a word several claim is a fork."""
    out: dict[str, set] = {}
    for f in facts_of(semantic):
        for c in f.claims:
            out.setdefault(c.term, set()).update(c.synonyms)
    return {t: tuple(sorted(s)) for t, s in sorted(out.items())}


def _tokens(text: str) -> list[str]:
    """Words as compared: lower case, hyphens and underscores as spaces, punctuation dropped, a
    plural s ignored on words longer than three letters."""
    words = re.sub(r"[^a-z0-9 ]", " ", str(text).lower().replace("-", " ").replace("_", " ")).split()
    return [w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words]


def _occurs(phrase: list[str], words: list[str]) -> bool:
    n = len(phrase)
    return bool(n) and any(words[i:i + n] == phrase for i in range(len(words) - n + 1))


def longest_term(question: str, term: str, semantic) -> str:
    """The declared term to route on when the question check chose `term`: the term of the longest
    declared phrase that contains one of `term`'s words and occurs in the question, or `term`.

    "How many paying customers are on the yearly plan?" names a counted thing as "paying
    customers", which contains the fork word "customers". The longer phrase is the one the layer
    declared for this, so it wins and the fork is not consulted. Which word names the counted thing
    is the model's judgement ("Android users open the app" counts opens, not users); this only
    settles which declared phrase that word is part of."""
    facts = facts_of(semantic)
    words = _tokens(question)
    mine = [_tokens(w) for f in facts for c in f.claims if c.term == term for w in c.words]
    best, best_len = term, max((len(w) for w in mine if _occurs(w, words)), default=0)
    for f in facts:
        for c in f.claims:
            for w in c.words:
                toks = _tokens(w)
                if (len(toks) > best_len and _occurs(toks, words)
                        and any(_occurs(m, toks) for m in mine)):
                    best, best_len = c.term, len(toks)
    return best


def rivals(a: str, b: str, semantic) -> bool:
    """Do two metrics claim a word in common? Then the layer already decides between them."""
    facts = facts_of(semantic)
    words = lambda m: {w for f in facts if f.label == m for c in f.claims for w in c.words}  # noqa: E731
    return bool(words(a) & words(b))


def _decision(parameter, value, basis, disclose="", state="applied", why=""):
    return {"parameter": parameter, "value": value, "basis": basis, "quote": "", "disclose": disclose,
            "state": state, "why": why}


def _listing(outcome) -> str:
    return "; ".join(f"{m} ({r})" if r else m for m, r in zip(outcome.metrics, outcome.readings, strict=False))


def resolve(metric: str, team: str | None, semantic, term=ANY) -> tuple[str, dict | None]:
    """The metric to query for `metric` and the decision behind it, from the layer's declarations.

    `term` is the declared word the question uses for what it counts, when the question check has
    read it. Then that word decides, whichever metric the agent called: one metric answers it for
    this team (that metric is used, and any rival readings disclosed); several answer (the metric
    stands and every reading must be reported); none (the choice is the user's: the call does not
    run and the agent asks). "How many customers did we have in June?" from Product routes to
    active_users even when the agent called paying_users. A question that uses no declared word, or
    names a metric itself, routes nothing (h_013 was rerouted from the metric it named).

    Without a question check (`term` ANY), the agent's own metric decides: its fork words route."""
    facts = facts_of(semantic)
    if term is not ANY:
        return _decide(facts, metric, team, term, semantic) if term is not None else (metric, None)
    # Without the question's word, every fork word of the metric is weighed: a word that asks wins,
    # then one that reroutes; otherwise the metric stands and every disclosure is kept.
    decided = [_decide(facts, metric, team, word, semantic) for word in _fork_terms(facts, metric, ANY)]
    decided = [(m, d) for m, d in decided if d is not None]
    for m, d in decided:
        if d["state"] == "ungrounded":
            return m, d
    for m, d in decided:
        if m != metric:
            return m, d
    if decided:
        first = decided[0][1]
        return metric, {**first, "disclose": " ".join(d["disclose"] for _, d in decided if d.get("disclose"))}
    return metric, None


@lru_cache(maxsize=8)
def _specs(spec_dir: str) -> dict:
    from pathlib import Path

    from ontology.parameters import load_layer
    text = "\n---\n".join(p.read_text() for p in sorted(Path(spec_dir).glob("*.y*ml")))
    return load_layer(text)[1]


def _inputs(semantic, metric: str, seen: frozenset = frozenset()) -> set:
    """The metrics a ratio or derived metric is computed from, at any depth, read from the layer."""
    spec_dir = getattr(semantic, "spec_dir", None)
    spec = (_specs(str(spec_dir)) if spec_dir else {}).get(metric) or {}
    params = spec.get("type_params") or {}
    names = [(params.get(k) or {}).get("name") for k in ("numerator", "denominator")]
    names += [(m or {}).get("name") for m in params.get("metrics") or []]
    out = {n for n in names if n and n not in seen}
    for n in list(out):
        out |= _inputs(semantic, n, seen | {metric})
    return out


def _decide(facts: tuple, metric: str, team: str | None, word: str, semantic=None) -> tuple[str, dict | None]:
    outcome = preflight.readings(facts, word, team)
    if outcome is None:
        return metric, None
    # A word names part of what a ratio counts ("habits per active customer" uses "habits"), so it
    # never moves the question from the ratio to one of its own inputs (h_006, t_010).
    if semantic is not None and set(outcome.metrics) & _inputs(semantic, metric):
        return metric, None
    why = f"meta.terms: '{word}'"
    every = preflight.readings(facts, word, None)
    claimed = set(every.metrics) if every else set()
    if outcome.action == "ask":
        return metric, _decision("metric", "?", "none", state="ungrounded",
                                 why=f"'{word}' has several governed readings and none is declared for "
                                     f"the {team or 'unnamed'} team: {_listing(outcome)}")
    if outcome.action == "one":
        routed, reading = outcome.metrics[0], outcome.readings[0]
        rest = [f"{m} ({r})" if r else m for m, r in zip(every.metrics, every.readings, strict=False)
                if m != routed] if every else []
        if not rest:
            # One metric claims the word. Nothing to disclose when the agent called it.
            return (metric, None) if routed == metric else (routed, _decision(
                "metric", routed, "governed_principle", why=why,
                disclose=f"The question asks for '{word}', which the layer declares for {routed}."))
        return routed, _decision(
            "metric", routed, "governed_principle", why=why,
            disclose=(f"'{word}' has several governed readings. For the {team} team it means {routed}"
                      f"{f' ({reading})' if reading else ''}; also governed: {', '.join(rest)}."))
    shown = metric if metric in outcome.metrics else outcome.metrics[0]
    return shown, _decision(
        "metric", shown, "governed_principle", why=why,
        disclose=f"'{word}' has several governed readings, and the rule is to show every one: "
                 f"{_listing(outcome)}. Report each figure with its reading.")


def companions(metric: str, team: str | None, semantic, term=ANY) -> list[tuple[str, str, str]]:
    """(other metric, its reading, the word) for every reading that must be shown beside `metric`."""
    facts = facts_of(semantic)
    words = ([term] if term is not None else []) if term is not ANY else _fork_terms(facts, metric, ANY)
    out = []
    for word in words:
        outcome = preflight.readings(facts, word, team)
        if outcome is not None and outcome.action == "show_all" and metric in outcome.metrics:
            out += [(m, r, word) for m, r in zip(outcome.metrics, outcome.readings, strict=False) if m != metric]
    return out
