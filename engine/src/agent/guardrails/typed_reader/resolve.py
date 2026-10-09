"""The typed reader's code steps: no model is called here.

A language model has marked what each phrase of the question does (the proposal, `language.py`).
This module checks that every word the layer knows was marked (accounting), resolves each marked
phrase against the closed lists (the values of the layer's dimensions, the calendar, the dimension
names and the governed rules), and builds the reading that `decisions.check` holds every call
against. The decision model's answers enter only as flags (confirmation) and as suggestions for a
phrase no list holds; neither can add a value that is not in a list.

Design: 03_typed_reader/design.md in experiment 07, sections 3 to 7.
"""
from __future__ import annotations

import datetime as dt
import re

from ..decisions import CONFIDENT, PLAUSIBLE, _dimensions, _meanings, _refuse, _covered
from ..forks import _tokens
from ..parameters import _decision, _period_span, _ungrounded

# ── accounting ─────────────────────────────────────────────────────────────────────────────────
_MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"
DATE_WORDS = re.compile(rf"\b(?:{_MONTHS}|spring|summer|autumn|fall|winter|(?:19|20)\d\d|q[1-4]|h[12]|first half|"
                        r"second half|last (?:week|month|quarter|year)|this (?:week|month|quarter|year)|"
                        r"year to date|ytd)\b", re.I)
SERIES_WORDS = re.compile(r"\b(?:week by week|month by month|day by day|weekly|monthly|daily|quarterly|trend|"
                          r"over time|change[ds]?)\b", re.I)
BY_PHRASE = re.compile(r"\b(?:by|per|for each)\s+(\w+(?:\s+\w+)?)", re.I)
# Words that join a value to the rest of a phrase and restrict nothing ("users on Android").
_JOINING = {"the", "a", "an", "of", "on", "from", "in", "for", "with", "and", "or", "who", "that"}


def _values(surface: dict):
    """(dimension, value) for every value of a closed dimension that a question can name."""
    for d in _dimensions(surface):
        for m in d["members"]:
            if str(m).lower() not in ("true", "false"):
                yield d, m


def _phrase(value) -> tuple[list, bool]:
    """The tokens a value is written as, and whether case matters: a two-letter code ("IN") matches
    only as written in capitals, because it collides with ordinary words ("in")."""
    text = str(value)
    return (_tokens(text, cased=True), True) if len(text) <= 2 else (_tokens(text), False)


def _quotes(proposal: dict) -> list[str]:
    out = [t["quote"] for f in proposal.get("figures") or [] for t in f.get("terms") or []]
    out += [t["quote"] for t in proposal.get("time") or []] + [b["quote"] for b in proposal.get("breakdown") or []]
    if proposal.get("series"):
        out.append(proposal["series"].get("quote") or "")
    if proposal.get("premise"):
        out.append(proposal["premise"].get("quote") or "")
    return [q for q in out if q]


def unaccounted(question: str, proposal: dict, surface: dict) -> list[str]:
    """PURE. The words the layer knows (a dimension value, a date word, a series word, a "by ..."
    phrase) that lie inside no marked phrase. Empty when the proposal accounts for the question."""
    spans = [(i, i + len(q)) for q in _quotes(proposal) for i in [question.lower().find(q.lower())] if i >= 0]
    covered = lambda a, b: any(a < e and b > s for s, e in spans)        # noqa: E731
    hits = []
    for _d, m in _values(surface):
        for found in re.finditer(rf"\b{re.escape(str(m))}s?\b", question, 0 if len(str(m)) <= 2 else re.I):
            hits.append((found.start(), found.end(), found.group()))
    hits += [(x.start(), x.end(), x.group()) for x in DATE_WORDS.finditer(question)]
    hits += [(x.start(), x.end(), x.group()) for x in SERIES_WORDS.finditer(question)]
    hits += [(x.start(1), x.end(1), "by " + x.group(1)) for x in BY_PHRASE.finditer(question)]
    return sorted({h for a, b, h in hits if not covered(a, b)})


def missing_quotes(question: str, proposal: dict) -> list[str]:
    """PURE. Marked phrases that do not occur in the question: the proposal invented them."""
    return [q for q in _quotes(proposal) if q.lower() not in question.lower()]


# ── values ─────────────────────────────────────────────────────────────────────────────────────
def lookup(quote: str, surface: dict) -> dict:
    """PURE. What a term's phrase names among the closed lists.

    {"values": [(dimension, value), ...], "rest": [words no value covers], "ambiguous": [...]}.
    Longest phrase first; a value of two dimensions ("unknown") is ambiguous, because which one it
    means is a judgement, not a lookup."""
    words, cased = _tokens(quote), _tokens(quote, cased=True)
    found = []                                                    # (start, end, dimension, value)
    for d, m in _values(surface):
        phrase, exact = _phrase(m)
        against = cased if exact else words
        found += [(i, i + len(phrase), d["name"], m) for i in range(len(words) - len(phrase) + 1)
                  if phrase and against[i:i + len(phrase)] == phrase]
    owners: dict = {}
    for _a, _b, dim, m in found:
        owners.setdefault(str(m).lower(), set()).add(dim)
    taken, values, ambiguous = set(), [], []
    for a, b, dim, m in sorted(found, key=lambda f: (f[0] - f[1], f[0])):
        if taken & set(range(a, b)):
            continue
        taken |= set(range(a, b))
        if len(owners[str(m).lower()]) > 1:
            ambiguous.append((str(m), sorted(owners[str(m).lower()])))
        elif (dim, m) not in values:
            values.append((dim, m))
    rest = [w for i, w in enumerate(words) if i not in taken and w not in _JOINING]
    return {"values": values, "rest": rest, "ambiguous": ambiguous}


def spelling_variant(word: str, value) -> bool:
    """PURE. Is `word` the value misspelled: at most two letters apart (insertion, deletion,
    substitution or an adjacent swap), on a value of at least four letters?"""
    a, b = str(word).lower(), str(value).lower()
    if len(b) < 4 or a == b:
        return False
    prev2, prev = None, list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        row = [i]
        for j, cb in enumerate(b, 1):
            cost = min(prev[j] + 1, row[j - 1] + 1, prev[j - 1] + (ca != cb))
            if prev2 is not None and i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                cost = min(cost, prev2[j - 2] + 1)
            row.append(cost)
        prev2, prev = prev, row
    return prev[-1] <= 2


def suggested(quote: str, answer: dict, surface: dict) -> dict:
    """PURE. The analyst's reply for a phrase no list holds, from the decision model's choice among
    "the same thing as value X", "a {dimension} value the layer does not have" and "something else".

    {"kind": "corrected" | "ask" | "refuse", "dim", "value", "rest", "why"}. Only a misspelling is corrected,
    and only onto a listed value that code confirms as a spelling variant; every other reading of the
    model changes the wording of a non-answer and nothing else."""
    probs = dict((answer or {}).get("probabilities") or {})
    best = max(probs, key=probs.get) if probs else "other"
    p = probs.get(best, 0.0)
    clear = p >= CONFIDENT and all(v < PLAUSIBLE for k, v in probs.items() if k != best)
    if best.startswith("value:") and clear:
        dim, _, value = best[len("value:"):].partition("=")
        member = next((m for d, m in _values(surface) if d["name"] == dim and str(m) == value), value)
        words, size = _tokens(quote), len(_tokens(str(member)))
        for i in range(len(words) - size + 1):
            if spelling_variant(" ".join(words[i:i + size]), member):
                rest = [w for w in words[:i] + words[i + size:] if w not in _JOINING]
                return {"kind": "corrected", "dim": dim, "value": member, "rest": rest,
                        "why": f"read \"{quote}\" as {dim.split('__')[-1]} {member}, a spelling of a listed value"}
        return {"kind": "ask", "why": f"\"{quote}\" is not a listed value; did you mean "
                                      f"{dim.split('__')[-1]} {member}?"}
    if best.startswith("absent:") and p >= CONFIDENT:
        dim = best[len("absent:"):]
        members = next((d["members"] for d in _dimensions(surface) if d["name"] == dim), [])
        return {"kind": "refuse", "dim": dim,
                "why": f"\"{quote}\" names a {dim.split('__')[-1]} the layer does not have; the governed "
                       f"values are {', '.join(map(str, members))}"}
    return {"kind": "ask", "why": f"\"{quote}\" matches no value of the layer"}


# ── time ───────────────────────────────────────────────────────────────────────────────────────
_SEASONS = {"SP": "spring", "SU": "summer", "FA": "autumn", "WI": "winter"}
_RELATIVE = {"last_week": "last_week", "last_month": "last_month", "last_quarter": "last_quarter",
             "year_to_date": "ytd", "ytd": "ytd"}


def _range(first: dt.date, last: dt.date) -> str:
    return f"{first.isoformat()}/{last.isoformat()}"


def period_of(value: str, seasons: dict) -> tuple[str | None, str]:
    """PURE. (period, why): a TIMEX3 value as a period the call check reads. A month, quarter or half
    stays named; a year, a season, an interval or a relative name becomes an explicit range. A season
    comes from the calendar's season attribute (`seasons`: {(season, year): (first, last)}); a season
    the calendar does not hold is undeclared. (None, reason) when the value cannot be placed."""
    from warehouse.config import resolve_period
    v = str(value or "").strip()
    if re.fullmatch(r"\d{4}-(\d{2}|Q[1-4]|H[12])", v, re.I):
        return v.upper(), ""
    if re.fullmatch(r"\d{4}", v):
        return _range(*_period_span(v)), ""
    m = re.fullmatch(r"(\d{4})-(SP|SU|FA|WI)", v, re.I)
    if m:
        span = seasons.get((_SEASONS[m.group(2).upper()], int(m.group(1))))
        return (_range(*span), "") if span else (None, f"no declared season {v}")
    if "/" in v:
        parts = [period_of(x, seasons)[0] for x in v.split("/", 1)]
        spans = [_period_span(x) if x else None for x in parts]
        if all(spans):
            return _range(spans[0][0], spans[1][1]), ""
        return None, f"the interval {v} cannot be placed"
    if v.lower() in _RELATIVE:
        return _range(*resolve_period(_RELATIVE[v.lower()])), ""
    return None, f"\"{v}\" cannot be placed on the calendar"


def readable(period: str) -> str:
    """A period in words, for a confirmation question and an answer."""
    months = [x.capitalize() for x in _MONTHS.split("|")]
    span = _period_span(period)
    if re.fullmatch(r"\d{4}-\d{2}", period):
        return f"{months[span[0].month - 1]} {span[0].year}"
    if re.fullmatch(r"\d{4}-Q[1-4]", period):
        return f"{period[-2:]} {period[:4]} ({months[span[0].month - 1]} to {months[span[1].month - 1]})"
    if re.fullmatch(r"\d{4}-H[12]", period):
        return f"the {'first' if period.endswith('1') else 'second'} half of {period[:4]}"
    return f"{span[0].isoformat()} to {span[1].isoformat()}" if span else period


# ── breakdown ──────────────────────────────────────────────────────────────────────────────────
_TIME_UNITS = {"day": "day", "week": "week", "month": "month", "quarter": "quarter", "year": "year"}


def split_by(quote: str, surface: dict, principles: list) -> tuple[str, str]:
    """PURE. (kind, target) for a breakdown phrase: ("dimension", name), ("rule", id) for a governed
    rule that names its own words, ("time", unit), ("near", what) when the phrase holds a dimension
    name or a rule's word among other words ("customer segment"), or ("none", "") when the layer has
    no such split."""
    words = _tokens(re.sub(r"^\s*(?:split\s+)?(?:by|per|for each|across)\s+", "", quote, flags=re.I))
    names = [("dimension", d["name"], _tokens(d["column"])) for d in _dimensions(surface)]
    names += [("rule", r["id"], _tokens(w)) for r in principles if r.get("slot") == "group_by"
              for w in r.get("words") or ()]
    for kind, target, name in names:
        if words == name:
            return kind, target
    if len(words) == 1 and words[0] in _TIME_UNITS:
        return "time", _TIME_UNITS[words[0]]
    near = [" ".join(name) for _k, _t, name in names
            if any(words[i:i + len(name)] == name for i in range(len(words) - len(name) + 1))]
    return ("near", " or ".join(dict.fromkeys(near))) if near else ("none", "")


# ── the reading ────────────────────────────────────────────────────────────────────────────────
def _figure_filters(terms: list, surface: dict) -> dict:
    """{dimension: value or [values]} for one figure: kept values, minus left-out values, on each
    dimension; a dimension with only left-out values is its complement."""
    members = {d["name"]: d["members"] for d in _dimensions(surface)}
    keep: dict = {}
    drop: dict = {}
    for t in terms:
        for dim, value in t["values"]:
            (keep if t["keep"] else drop).setdefault(dim, []).append(value)
    out = {}
    for dim in list(keep) + [d for d in drop if d not in keep]:
        chosen = [v for v in (keep.get(dim) or members[dim]) if v not in drop.get(dim, [])]
        out[dim] = chosen[0] if len(chosen) == 1 else chosen
    return out


def build(proposal: dict, terms: list, surface: dict, principles: list, lo: dt.date, hi: dt.date,
          seasons: dict, outcomes: list) -> dict:
    """PURE. The reading, in the form `decisions.check` reads, from the proposal and its resolved
    terms. `terms` holds, per figure, each term with its `values` (resolved, corrected or none) and
    `keep`. `outcomes` are the non-answers found so far (refusals and open parameters); every later
    part is still built, so the record shows the whole reading."""
    decisions = list(outcomes)
    builtin = surface.get("filter")
    if builtin:
        decisions.append(_decision("metric_filter", builtin, "governed_declaration",
                                   disclose=f"{surface['metric']} applies {builtin} by definition.",
                                   why="declared by the metric; not selectable"))
    # Figures: a dimension that differs between figures carries one reading per figure (the call
    # check runs one query each); every other dimension must be the same in every figure.
    per_figure = [_figure_filters(f, surface) for f in terms]
    filters: dict = {}
    dims = list(dict.fromkeys(d for f in per_figure for d in f))
    varying = [d for d in dims if len({repr(f.get(d)) for f in per_figure}) > 1]
    if len(varying) > 1 or any(d not in f for d in varying for f in per_figure):
        decisions.append(_ungrounded("filter", "the figures differ in more than one way; ask which numbers to show"))
    else:
        for d in dims:
            filters[d] = [f[d] for f in per_figure] if d in varying else [per_figure[0][d]]
    for dim, readings in filters.items():
        corrected = [t["why"] for f in terms for t in f if t.get("why") and any(v[0] == dim for v in t["values"])]
        listed = [x for r in readings for x in (r if isinstance(r, list) else [r])]
        disclose = " ".join(filter(None, [_meanings(dim, listed, surface)] + [c[0].upper() + c[1:] + "." for c in corrected]))
        decisions.append(_decision("filter", " or ".join(
            f"{dim} in ({', '.join(map(str, r))})" if isinstance(r, list) else f"{dim} = {r}" for r in readings),
            "question", disclose=disclose))

    periods = []
    for item in proposal.get("time") or []:
        period, why = period_of(item.get("value"), seasons)
        if period is None:
            decisions.append(_ungrounded("period", why))
        elif period not in periods:
            periods.append(period)
    # A period not wholly inside the data is refused, as the engine refuses the call (design section
    # 11: partly covered periods refuse during the comparison of the two readers).
    uncovered = [p for p in periods if not _covered(p, lo, hi)]
    partly = [p for p in periods if p not in uncovered and not (lo <= _period_span(p)[0] and _period_span(p)[1] <= hi)]
    if uncovered or partly:
        said = [f"{readable(p)} is outside the data" for p in uncovered] + \
               [f"{readable(p)} is only partly inside the data" for p in partly]
        decisions.append(_refuse("period", "out_of_coverage", f"{'; '.join(said)} ({lo} to {hi})"))
    elif not proposal.get("time"):
        decisions.append(_ungrounded("period", "the question states no period that can be placed on the "
                                     "calendar, and no rule supplies one"))
    elif periods:
        decisions.append(_decision("period", " or ".join(periods), "question"))

    group_by, separate, grain = [], False, None
    series = proposal.get("series")
    if series:
        group_by, grain = ["metric_time"], series.get("unit") if series.get("unit") in _TIME_UNITS else None
        decisions.append(_decision("group_by", group_by, "question"))
    by_id = {p["id"]: p for p in principles}
    for b in proposal.get("breakdown") or []:
        kind, target = split_by(b["quote"], surface, principles)
        if kind == "dimension" and target not in group_by:
            group_by.append(target)
            decisions.append(_decision("group_by", [target], "question"))
        elif kind == "rule":
            rule = by_id[target]
            dims_ = [d for d in rule.get("default", []) if d not in filters]
            group_by += [d for d in dims_ if d not in group_by]
            separate = rule.get("combine") == "separate"
            decisions.append(_decision("group_by", dims_, "governed_principle", disclose=rule.get("disclose", ""),
                                       why=f"principle {rule['id']}"))
        elif kind == "time":
            group_by, grain = (group_by if "metric_time" in group_by else group_by + ["metric_time"]), target
            decisions.append(_decision("group_by", ["metric_time"], "question"))
        elif kind == "near":
            decisions.append(_ungrounded("group_by", f"the question asks to split by \"{b['quote']}\"; ask whether "
                                         f"it means {target}"))
        elif kind == "none":
            decisions.append(_refuse("group_by", "dimension_not_supported",
                                     f"the question asks to split by \"{b['quote']}\", which the layer does not have"))
    if proposal.get("premise"):
        decisions.append(_ungrounded("premise", f"the question takes as given \"{proposal['premise'].get('quote')}\"; "
                                     "the typed reader does not check stated facts yet"))
    return {"filters": filters, "periods": periods, "group_by": group_by, "separate": separate, "premise": {},
            "values": {d["name"]: d["members"] for d in _dimensions(surface)},
            "period_options": periods,
            "grain": grain, "rule": next((r for r in principles if r.get("slot") == "time_grain"), None),
            "builtin": builtin, "decisions": decisions}
