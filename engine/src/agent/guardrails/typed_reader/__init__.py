"""The typed reader: a language model marks the question, code resolves it against closed lists.

    reading_for(question, metric, semantic, cursor, governance, cache) -> (reading, cost)
    replay(stored, question, metric, semantic, cursor, governance) -> reading

The same signature and the same reading as `decisions.reading_for`, so `decisions.check` holds every
call against it unchanged. The guardrail option `typed_reader` selects it.

The steps (03_typed_reader/design.md in experiment 07):
  1. propose   the proposal model marks the phrases (language.py); it sees no part of the layer
  2. account   every value word, date word, series word and "by ..." phrase must be marked; one retry
               names the words that are not, then the reader asks (resolve.py)
  3. resolve   each phrase against the values of the layer's dimensions and the calendar (resolve.py)
  4. suggest   a phrase no list holds: a misspelling of a listed value is corrected and disclosed;
               anything else is asked about or refused (the decision model chooses only the reply)
  5. confirm   one yes/no per judgement of the proposal; an unconfirmed one makes the reader ask

Every model request and its answer is kept with the reading, keyed by the exact request. A replay
runs the code steps again and reuses an answer only for an identical request; a request the store
does not hold marks the reading stale instead of being sent.
"""
from __future__ import annotations

import hashlib
import json

from .. import decisions as _decisions
from . import language, resolve

__all__ = ["reading_for", "replay"]


class _Stale(Exception):
    """A replay needs a request the stored reading did not make."""


class _Language:
    """The model requests of one question, with their answers. Live, a request not yet made is sent
    and recorded; in a replay it raises `_Stale`."""

    def __init__(self, store: dict | None = None, live: bool = True):
        self.store, self.live, self.cost, self.used = dict(store or {}), live, 0.0, {}

    def _get(self, kind: str, payload, send, record: dict):
        key = hashlib.sha256(json.dumps([kind, payload], sort_keys=True, default=str).encode()).hexdigest()[:16]
        if key not in self.store:
            if not self.live:
                raise _Stale(kind)
            output, cost = send()
            self.cost += cost
            self.store[key] = {"kind": kind, **record, "output": output}
        self.used[key] = self.store[key]
        return self.store[key]["output"]

    def propose(self, question: str, missed: list) -> dict:
        request = language.proposal_request(question, missed)
        out = self._get("propose", request, lambda: language.propose(request), {"missed": missed})
        return {"figures": out.get("figures") or [], "time": out.get("time") or [], "series": out.get("series"),
                "breakdown": out.get("breakdown") or [], "premise": out.get("premise")}

    def decide(self, kind: str, questions: dict, question: str) -> dict:
        def send():
            answers, cost, _model = _decisions._ask(questions, question)
            return answers, cost
        return self._get(kind, [questions, question], send, {"questions": sorted(questions)})


def _seasons(cursor, governance: dict | None) -> dict:
    """{(season, year): (first day, last day)} from the calendar governance names (`calendar`), or {}."""
    table = (governance or {}).get("calendar")
    if not table or cursor is None:
        return {}
    rows = cursor.execute(f"SELECT season, season_year, min(date_day), max(date_day) FROM {table} "
                          f"GROUP BY 1, 2").fetchall()
    return {(str(s), int(y)): (a, b) for s, y, a, b in rows}


def _read(question: str, metric: str, context: tuple, seasons: dict, lang: _Language) -> dict:
    surface, principles, lo, hi = context
    outcomes = []
    proposal = lang.propose(question, [])
    missed = resolve.unaccounted(question, proposal, surface) + resolve.missing_quotes(question, proposal)
    if missed:
        proposal = lang.propose(question, missed)
        missed = resolve.unaccounted(question, proposal, surface) + resolve.missing_quotes(question, proposal)
        if missed:
            outcomes.append(_decisions._ungrounded("reading", "the question's words "
                                                   + ", ".join(f'"{w}"' for w in missed) + " are not accounted for"))

    terms = [[{**t, **resolve.lookup(t["quote"], surface)} for t in f.get("terms") or []]
             for f in proposal["figures"]]
    for t in (t for f in terms for t in f):
        for value, dims in t["ambiguous"]:
            outcomes.append(_decisions._ungrounded("filter", f"\"{value}\" is a value of "
                                                   f"{' and of '.join(d.split('__')[-1] for d in dims)}; ask which"))
    unresolved = list(dict.fromkeys(t["quote"] for f in terms for t in f if not t["values"] and not t["ambiguous"]))
    if unresolved:
        answers = lang.decide("suggest", language.suggestion_questions(unresolved, surface), question)
        for i, quote in enumerate(unresolved):
            s = resolve.suggested(quote, answers.get(f"sug{i}"), surface)
            if s["kind"] == "corrected":
                for t in (t for f in terms for t in f if t["quote"] == quote):
                    t["values"], t["rest"], t["why"] = [(s["dim"], s["value"])], s["rest"], s["why"]
            elif s["kind"] == "refuse":
                outcomes.append(_decisions._refuse("filter", "ungoverned_dimension_value", s["why"]))
            else:
                outcomes.append(_decisions._ungrounded("filter", s["why"]))

    reading = resolve.build(proposal, terms, surface, principles, lo, hi, seasons, outcomes)
    if not any(d["state"] in ("refuse", "ungrounded") for d in reading["decisions"]):
        questions, rule = language.confirmation_questions(proposal, terms, reading["periods"])
        answers = lang.decide("confirm", questions, question)
        for key, how in rule.items():
            p = _decisions._yes(answers, key)
            if (p < _decisions.CONFIDENT) if how == "low" else (p >= _decisions.CONFIDENT):
                reading["decisions"].append({**_decisions._ungrounded(
                    "reading", f"not confirmed: {questions[key]['instructions']}"), "confidence": p})
    return {**reading, "proposal": proposal, "language": lang.used, "model": language.PROPOSAL_MODEL}


def reading_for(question: str, metric: str, semantic, cursor, governance: dict | None,
                cache: dict) -> tuple[dict | None, float]:
    """The reading of the question for one metric, and the cost of its requests (0.0 from the cache).
    None when the metric's surface or coverage cannot be read. The proposal is made once per question
    and shared by every metric (`cache["_typed"]`)."""
    if metric in cache:
        return cache[metric], 0.0
    context = _decisions._context(metric, semantic, cursor, governance)
    if context is None:
        return None, 0.0
    lang = _Language(cache.get("_typed"))
    reading = _read(question, metric, context, _seasons(cursor, governance), lang)
    cache["_typed"] = lang.store
    cache[metric] = reading
    return reading, lang.cost


def replay(stored: dict, question: str, metric: str, semantic, cursor, governance: dict | None) -> dict | None:
    """The stored reading decided again by the current code, with no request. `stale` is set when the
    current code would make a request the stored reading did not; the stored reading is returned."""
    context = _decisions._context(metric, semantic, cursor, governance)
    if context is None:
        return None
    try:
        return _read(question, metric, context, _seasons(cursor, governance),
                     _Language(stored.get("language"), live=False))
    except _Stale as exc:
        return {**stored, "stale": str(exc)}
