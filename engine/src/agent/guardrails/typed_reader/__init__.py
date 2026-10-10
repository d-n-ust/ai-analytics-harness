"""The typed reader: a language model marks the question, code resolves it against closed lists.

    reading_for(question, metric, semantic, cursor, governance, cache) -> (reading, cost)
    replay(stored, question, metric, semantic, cursor, governance) -> reading

The same signature and the same reading as `decisions.reading_for`, so `decisions.check` holds every
call against it unchanged. The guardrail option `typed_reader` selects it.

The steps (03_typed_reader/design.md in experiment 07):
  1. propose   two proposal models of different families mark the phrases (language.py); neither
               sees any part of the layer; where they disagree, one narrow question settles each point
  2. account   every value word, date word, series word and "by ..." phrase must be marked; one retry
               names the words that are not, then the reader asks (resolve.py)
  3. resolve   each phrase against the values of the layer's dimensions and the calendar (resolve.py)
  4. judge     a phrase the lists do not settle alone: an analyst's reading (a misspelling, a synonym,
               or a narrower thing answered with the broader value) is applied and stated in the
               answer; something no list has is refused; anything unclear is asked about
  5. confirm   one narrow yes/no per structural judgement (a series, values combined or compared,
               something left out, several periods) and per word the reading does not use

Every model request and its answer is kept with the reading, keyed by the exact request. A replay
runs the code steps again and reuses an answer only for an identical request; a request the store
does not hold marks the reading stale instead of being sent.
"""
from __future__ import annotations

import hashlib
import json
import time

from .. import decisions as _decisions
from . import language, resolve

__all__ = ["reading_for", "replay"]


# A structural check is a veto: it flags a judgement the model reads as more likely wrong than right.
# Calibration (findings section 36): wrong readings 0.26 or less, right ones 0.73 or more.
VETO = 0.5


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
            started = time.monotonic()
            output, cost, served = send()
            self.cost += cost
            # The served version, not the alias asked for: an alias can change what it serves.
            self.store[key] = {"kind": kind, **record, "output": output, "served": served,
                               "seconds": round(time.monotonic() - started, 2)}
        self.used[key] = self.store[key]
        return self.store[key]["output"]

    def propose(self, question: str, missed: list, model: str = language.PROPOSAL_MODEL) -> dict:
        request = language.proposal_request(question, missed, model)
        out = self._get("propose", request, lambda: language.propose(request), {"missed": missed})
        return {"figures": out.get("figures") or [], "time": out.get("time") or [], "series": out.get("series"),
                "breakdown": out.get("breakdown") or [], "premise": out.get("premise")}

    def decide(self, kind: str, questions: dict, question: str) -> dict:
        return self._get(kind, [questions, question], lambda: _decisions._ask(questions, question),
                         {"questions": sorted(questions)})


def _seasons(cursor, governance: dict | None) -> dict:
    """{(season, year): (first day, last day)} from the calendar governance names (`calendar`), or {}."""
    table = ((governance or {}).get("calendar") or {}).get("table")
    if not table or cursor is None:
        return {}
    rows = cursor.execute(f"SELECT season, season_year, min(date_day), max(date_day) FROM {table} "
                          f"GROUP BY 1, 2").fetchall()
    return {(str(s), int(y)): (a, b) for s, y, a, b in rows}


def _other_hemisphere(reading: dict, surface: dict, cursor, governance: dict | None) -> bool:
    """Does a figure lie wholly in the hemisphere the calendar's seasons are not for ("summer in
    Brazil")? Read from the rows each figure keeps, so a region, a country code or a name all count."""
    home = ((governance or {}).get("calendar") or {}).get("hemisphere")
    dims = {d["name"]: d for d in surface["parameters"]["filters"]["dimensions"]}
    hemi = next((d for d in dims.values() if d["column"] == "hemisphere"), None)
    if not home or hemi is None or cursor is None or not reading["filters"]:
        return False
    quote = lambda v: "'" + str(v).replace("'", "''") + "'"                # noqa: E731
    figures = max(len(r) for r in reading["filters"].values())
    for i in range(figures):
        where = []
        for dim, readings in reading["filters"].items():
            r = readings[min(i, len(readings) - 1)]
            values = r if isinstance(r, list) else [r]
            where.append(f"{dims[dim]['expr']} IN ({', '.join(map(quote, values))})")
        seen = {h for (h,) in cursor.execute(f"SELECT DISTINCT {hemi['expr']} FROM {hemi['table']} "
                                              f"WHERE {' AND '.join(where)}").fetchall()}
        if seen and home not in seen:
            return True
    return False


def _read(question: str, metric: str, context: tuple, cursor, governance: dict | None, lang: _Language) -> dict:
    surface, principles, lo, hi = context
    outcomes = []
    proposal = resolve.normalised(lang.propose(question, []), surface, principles, question)
    second = resolve.normalised(lang.propose(question, [], language.SECOND_MODEL), surface, principles, question)
    if resolve.canonical(proposal, surface) != resolve.canonical(second, surface):
        asked = language.reconcile_questions(proposal, second, surface)
        answers = lang.decide("reconcile", asked, question) if asked else {}
        proposal = resolve.normalised(resolve.reconciled(proposal, second, answers, surface), surface, principles, question)
    missed = resolve.unaccounted(question, proposal, surface) + resolve.missing_quotes(question, proposal)
    if missed:
        proposal = resolve.normalised(lang.propose(question, missed), surface, principles, question)
        missed = resolve.unaccounted(question, proposal, surface) + resolve.missing_quotes(question, proposal)
        if missed:
            proposal = resolve.marked_by_code(question, proposal, missed, surface)
            missed = resolve.unaccounted(question, proposal, surface) + resolve.missing_quotes(question, proposal)
        if missed:
            outcomes.append(_decisions._ungrounded("reading", "the question's words "
                                                   + ", ".join(f'"{w}"' for w in missed) + " are not accounted for"))

    terms = [[{**t, **resolve.lookup(t["quote"], surface)} for t in f.get("terms") or []]
             for f in proposal["figures"]]
    for t in (t for f in terms for t in f):
        for value, dims in t["ambiguous"]:
            chosen = resolve.named_dimension(question, dims, surface)
            if chosen:
                member = next(m for d in _decisions._dimensions(surface) if d["name"] == chosen
                              for m in d["members"] if str(m).lower() == value.lower())
                t["values"] = t["values"] + [(chosen, member)]
            else:
                outcomes.append(_decisions._ungrounded("filter", f"\"{value}\" is a value of "
                                                       f"{' and of '.join(d.split('__')[-1] for d in dims)}; ask which"))
    # Phrases the lists do not settle alone: no listed value in them ("Deutschland"), or a listed value
    # beside other words ("desktop accounts"). One request judges all of them.
    open_ = {t["quote"]: t["values"] for f in terms for t in f
             if not t["ambiguous"] and (not t["values"] or t["rest"])}
    if open_:
        answers = lang.decide("suggest", language.suggestion_questions(list(open_), surface), question)
        judged = {q: resolve.judged(q, v, answers.get(f"sug{i}"), surface) for i, (q, v) in enumerate(open_.items())}
        unsure = [q for q, s in judged.items() if s["kind"] == "ask"]
        if unsure:
            kinds = lang.decide("kind", language.kind_questions(unsure, surface), question)
            for i, q in enumerate(unsure):
                said = {k.split(":", 1)[1]: _decisions._yes(kinds, k) for k in kinds if k.startswith(f"kind{i}:")}
                judged[q] = resolve.judged(q, open_[q], answers.get(f"sug{list(open_).index(q)}"), surface, said)
        for quote, s in judged.items():
            if s["kind"] == "assumed" and s.get("inner"):
                # Narrower values the model also found plausible: the narrowest it confirms wins.
                said = lang.decide("inner", language.inner_questions(quote, s["inner"]), question)
                for i, (dim, value) in enumerate(s["inner"]):
                    if _decisions._yes(said, f"in{i}") >= resolve.ANALYST:
                        s = {**s, "dim": dim, "value": next(m for d in _decisions._dimensions(surface)
                                                            if d["name"] == dim for m in d["members"] if str(m) == value),
                             "why": f"read \"{quote}\" as {dim.split('__')[-1]} {value}, which is broader: "
                                    f"it includes more than \"{quote}\""}
                        break
            if s["kind"] == "assumed":
                for t in (t for f in terms for t in f if t["quote"] == quote):
                    t["values"], t["why"] = [(s["dim"], s["value"])], s["why"]
            elif s["kind"] == "refuse":
                outcomes.append(_decisions._refuse("filter", "ungoverned_dimension_value", s["why"]))
            elif s["kind"] == "ask":
                outcomes.append(_decisions._ungrounded("filter", s["why"]))

    reading = resolve.build(proposal, terms, surface, principles, lo, hi, _seasons(cursor, governance), outcomes)
    seasonal = any(resolve.SEASON.fullmatch(str(t.get("value") or "")) for t in proposal["time"])
    if seasonal and _other_hemisphere(reading, surface, cursor, governance):
        reading["decisions"].append(_decisions._ungrounded(
            "period", "the season named is for the northern hemisphere, and the figure lies in the southern one; "
                      "ask which months are meant"))
    # The checks run on every reading that is not refused, also one that already asks (about a missing
    # period, say): the user's reply settles the period, and a misread value must not survive it.
    if not any(d["state"] == "refuse" for d in reading["decisions"]):
        reading, vetoed, answers = _checked(question, proposal, terms, reading, surface, lang, "confirm")
        # A vetoed two-way judgement has one alternative ("US and GB" combined -> compared). It is built,
        # checked by its own narrow questions, and adopted only if every check passes and each flipped
        # judgement is confirmed (0.7). "Compare US and GB" was combined by both proposal models.
        alternative = resolve.flipped(proposal, terms, vetoed) if vetoed else None
        if alternative is not None:
            alt_proposal, alt_terms = alternative
            alt = resolve.build(alt_proposal, alt_terms, surface, principles, lo, hi, _seasons(cursor, governance),
                                list(outcomes))
            checked, _alt_vetoed, alt_answers = _checked(question, alt_proposal, alt_terms, alt, surface, lang, "recheck")
            structural = [k for k in alt_answers if not k.startswith("lw")]
            series_gone = "series" not in vetoed or _decisions._yes(answers, "series") <= 1 - _decisions.CONFIDENT
            unexplained = len(checked["decisions"]) > len(alt["decisions"]) + 0 and any(
                d["parameter"] == "filter" and "does not use" in d.get("why", "") for d in checked["decisions"])
            if series_gone and not unexplained and all(_decisions._yes(alt_answers, k) >= _decisions.CONFIDENT
                                                       for k in structural):
                reading, proposal, terms = checked, alt_proposal, alt_terms
    return {**reading, "proposal": proposal, "language": lang.used,
            "seconds": round(sum(e.get("seconds", 0) for e in lang.used.values()), 2)}


def _checked(question: str, proposal: dict, terms: list, reading: dict, surface: dict, lang: _Language,
             kind: str) -> tuple[dict, list, dict]:
    """(reading with the checks' results, the vetoed structural judgements, the answers). Narrow checks
    in one request: each structural judgement, and each word of the question no part of the reading
    uses. Code lists the words, so a restriction no list knows and the proposal left unmarked
    ("Germani") is put before the decision model by name."""
    words = resolve.leftover_words(question, proposal, surface)
    questions = {**language.structure_questions(proposal, reading, terms), **language.leftover_questions(words)}
    answers = lang.decide(kind, questions, question) if questions else {}
    decisions, vetoed = list(reading["decisions"]), []
    for key in (k for k in questions if not k.startswith("lw")):
        p = _decisions._yes(answers, key)
        if p < VETO:
            vetoed.append(key)
            decisions.append({**_decisions._ungrounded("reading", f"not confirmed: {questions[key]['instructions']}"),
                              "confidence": p})
    named = [w for i, w in enumerate(words) if _decisions._yes(answers, f"lw{i}") >= _decisions.CONFIDENT]
    if named:
        decisions.append(_decisions._ungrounded(
            "filter", f"the question names {', '.join(chr(34) + w + chr(34) for w in named)}, which the reading "
                      f"does not use; ask what it means"))
    return {**reading, "decisions": decisions}, vetoed, answers


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
    reading = _read(question, metric, context, cursor, governance, lang)
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
        return _read(question, metric, context, cursor, governance, _Language(stored.get("language"), live=False))
    except _Stale as exc:
        return {**stored, "stale": str(exc)}
