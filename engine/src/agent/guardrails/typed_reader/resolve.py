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
# "side by side", "one by one" and "step by step" are not splits; "week by week" is a series.
BY_PHRASE = re.compile(r"(?<!side )(?<!one )(?<!step )\b(?:by|per|for each)\s+(\w+(?:\s+\w+)?)", re.I)
# Words that join a value to the rest of a phrase and restrict nothing ("users on Android").
_JOINING = {"the", "a", "an", "of", "on", "from", "in", "for", "with", "and", "or", "who", "that", "across"}


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


def normalised(proposal: dict, surface: dict, principles: list, question: str = "") -> dict:
    """PURE. The proposal with misfiled phrases moved to where the layer says they belong, before
    anything is resolved: a term made only of the metric's own words ("app" in "mobile app opens") is
    dropped, because what is counted is not a restriction; a term that names a split ("by country")
    becomes a breakdown; a breakdown whose words are values ("across EMEA") becomes a term of every
    figure. The confirmation sees the result, so a wrong move is asked about, not served."""
    own = set(_tokens(str(surface.get("metric", "")).replace("_", " ")))
    figures, breakdown = [], list(proposal.get("breakdown") or [])
    for f in proposal.get("figures") or []:
        terms = []
        for t in f.get("terms") or []:
            words = _tokens(t["quote"])
            if words and set(words) <= own:
                continue
            after_by = re.search(rf"\b(?:by|per)\s+{re.escape(t['quote'])}", question, re.I)
            if any(x["quote"].lower() == t["quote"].lower() and x["keep"] == t["keep"] for x in terms):
                continue
            if t["keep"] and split_by(t["quote"], surface, principles)[0] in ("dimension", "rule") \
                    and (_SPLIT_LEAD.match(t["quote"]) or after_by):
                breakdown.append({"quote": t["quote"] if _SPLIT_LEAD.match(t["quote"]) else after_by.group()})
                continue
            terms.append(t)
        if terms:
            figures.append({"terms": terms})
    kept = []
    for b in breakdown:
        exclusion = re.search(r"\b(?:every|all)\s+\w+\s+(?:except|other than|excluding|but)\s+(.+)$", b["quote"], re.I)
        found = lookup(exclusion.group(1), surface) if exclusion else {}
        if exclusion and (found["values"] or found["ambiguous"]):
            term = {"quote": exclusion.group(1), "keep": False}
            figures = [{"terms": f["terms"] + ([term] if term not in f["terms"] else [])} for f in figures] \
                or [{"terms": [term]}]
            continue
        if not [w for w in _tokens(_SPLIT_LEAD.sub("", b["quote"])) if w not in _NO_CATEGORY]:
            continue                                     # "a week-by-week breakdown": no category named
        found = lookup(re.sub(r"^\s*(?:across|in|for|by)\s+", "", b["quote"], flags=re.I), surface)
        if split_by(b["quote"], surface, principles)[0] == "none" and found["values"] and not found["rest"]:
            term = {"quote": b["quote"], "keep": True}
            figures = [{"terms": f["terms"] + [term]} for f in figures] or [{"terms": [term]}]
        else:
            kept.append(b)
    return {**proposal, "figures": figures, "breakdown": kept}


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
    # Words the layer itself defines restrict nothing: the metric ("app opens") and the entities its
    # dimensions belong to ("users"). "mobile app opens" and "users in Germany" were asked about.
    own = set(_tokens(str(surface.get("metric", "")).replace("_", " ")))
    own |= {w for d in surface["parameters"]["filters"]["dimensions"] for w in _tokens(d.get("entity") or "")}
    rest = [w for i, w in enumerate(words) if i not in taken and w not in _JOINING and w not in own]
    return {"values": values, "rest": rest, "ambiguous": ambiguous}


def named_dimension(question: str, dims: list, surface: dict) -> str | None:
    """PURE. Of the dimensions a value belongs to, the one whose name the question uses ("every
    platform except unknown"), or None when it names none or several."""
    columns = {d["name"]: d["column"].replace("_", " ") for d in _dimensions(surface)}
    named = [d for d in dims if re.search(rf"\b{re.escape(columns.get(d, d))}s?\b", question, re.I)]
    return named[0] if len(named) == 1 else None


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


# An analyst's reading is a weaker source than a list value or a rule (design section 13), so it needs a
# clearer answer: one option at this level and no other at PLAUSIBLE.
ANALYST = 0.85


def _containing(surface: dict) -> dict:
    """{(dimension, value): {(dimension, value) that holds every row of it}}, from the value maps the
    layer derives from the data: android is inside mobile, DE inside EMEA, and DE and Germany hold the
    same rows (each inside the other). Each value holds itself."""
    up: dict = {}
    for a, linked in (surface["parameters"]["filters"].get("determines") or {}).items():
        for b, values in (linked or {}).items():
            if not isinstance(values, dict):
                continue
            sizes_equal = len(set(map(str, values.values()))) == len(values)
            for va, vb in values.items():
                up.setdefault((a, str(va)), set()).add((b, str(vb)))
                if sizes_equal:                                  # a second name for the same value
                    up.setdefault((b, str(vb)), set()).add((a, str(va)))
    closed: dict = {}
    for d, m in _values(surface):
        key, seen, todo = (d["name"], str(m)), set(), [(d["name"], str(m))]
        while todo:
            x = todo.pop()
            if x not in seen:
                seen.add(x)
                todo += list(up.get(x, ()))
        closed[key] = seen
    return closed


def judged(quote: str, values: list, answer: dict, surface: dict) -> dict:
    """PURE. The reader's reply for a phrase the lists do not settle alone, from the decision model's
    choice among, per value, "the same thing as" and "one kind of" (narrower), per dimension "one the
    layer does not have", and "something else". `values` are the listed values code found inside the
    phrase ("desktop" in "desktop accounts"); none for a phrase with no listed value ("Deutschland").

    {"kind": "kept" | "assumed" | "refuse" | "ask", "dim", "value", "why"}:
      kept     the phrase is the value code found in it ("desktop accounts")
      assumed  an analyst's reading, stated in the answer: a misspelling, a synonym or translation
               ("Deutschland" is Germany), or a narrower thing answered with the broader value
               ("iPhone" with ios, which also includes iPads)
      refuse   the phrase names something no list has ("TikTok")
      ask      anything else"""
    probs = dict((answer or {}).get("probabilities") or {})
    best = max(probs, key=probs.get) if probs else "other"
    p = probs.get(best, 0.0)
    kind = best.partition(":")[0]
    # Options that point at the same rows are one reading: DE and Germany, and "the same as android"
    # with "one kind of android". A narrower option also supports a broader value that holds it
    # (android counts for mobile), never the reverse. Split between two true options ("iPhone" is one
    # kind of ios and of mobile), no single option reached the bar (development run, 2026-10-10).
    holds = _containing(surface)
    mass: dict = {}
    for k, v in probs.items():
        if k.startswith(("value:", "part:")):
            dim, _, value = k.partition(":")[2].partition("=")
            mass[(dim, value)] = mass.get((dim, value), 0.0) + v
    candidates = []
    for target in mass:
        inside = [x for x in mass if target in holds.get(x, {x})]          # options this value holds
        support = sum(mass[x] for x in inside)
        rival = sum(v for k, v in probs.items() if v and not (k.startswith(("value:", "part:"))
                    and tuple(k.partition(":")[2].partition("=")[::2]) in inside))
        candidates.append((support, rival, len(holds.get(target, ())), target))   # more holders: narrower
    for bar in (CONFIDENT, ANALYST):
        clear = sorted(c for c in candidates if c[0] >= bar and c[1] < PLAUSIBLE)
        if not clear:
            continue
        support, _r, _n, (dim, value) = max(clear, key=lambda c: (c[2], c[0]))    # the narrowest, then strongest
        member = next((m for d, m in _values(surface) if d["name"] == dim and str(m) == value), value)
        label = f"{dim.split('__')[-1]} {member}"
        exact = probs.get(f"value:{dim}={value}", 0.0) >= probs.get(f"part:{dim}={value}", 0.0)
        if bar == CONFIDENT and exact and (dim, member) in values:
            return {"kind": "kept", "why": ""}
        words, size = _tokens(quote), len(_tokens(str(member)))
        spelled = any(spelling_variant(" ".join(words[i:i + size]), member) for i in range(len(words) - size + 1))
        if bar == CONFIDENT and exact and spelled:
            return {"kind": "assumed", "dim": dim, "value": member,
                    "why": f"read \"{quote}\" as {label}, a spelling of a listed value"}
        if bar == ANALYST:
            narrower = sum(v for k, v in probs.items() if k.startswith("part:")) > \
                sum(v for k, v in probs.items() if k.startswith("value:"))
            broader = f", which is broader: it includes more than \"{quote}\"" if narrower else ""
            # Values inside this one that the model also found plausible ("iPhone": ios inside mobile).
            # The caller asks about each, narrowest first, so the answer is not broader than it must be.
            inner = sorted((x for x in mass if x != (dim, value) and (dim, value) in holds.get(x, ())
                            and mass[x] >= PLAUSIBLE), key=lambda x: -len(holds.get(x, ())))
            return {"kind": "assumed", "dim": dim, "value": member, "why": f"read \"{quote}\" as {label}{broader}",
                    "inner": inner}
    # "TikTok" may read as a channel or as a platform the layer lacks; split between the two, neither
    # reached the bar and the reader asked. Not in any list, with no listed value plausible, refuses.
    absent = {k[len("absent:"):]: v for k, v in probs.items() if k.startswith("absent:")}
    listed = {k: v for k, v in probs.items() if k.startswith(("value:", "part:"))}
    if (kind == "absent" and p >= CONFIDENT) or (
            sum(absent.values()) >= CONFIDENT and all(v < PLAUSIBLE for v in listed.values())):
        dim = max(absent, key=absent.get)
        members = next((d["members"] for d in _dimensions(surface) if d["name"] == dim), [])
        return {"kind": "refuse", "dim": dim,
                "why": f"\"{quote}\" names something the layer does not have; the governed "
                       f"{dim.split('__')[-1]} values are {', '.join(map(str, members))}"}
    if values:
        found = " and ".join(f"{d.split('__')[-1]} {v}" for d, v in values)
        return {"kind": "ask", "why": f"\"{quote}\" holds {found} and other words; ask whether it means {found}"}
    return {"kind": "ask", "why": f"\"{quote}\" matches no value of the layer"}


# ── time ───────────────────────────────────────────────────────────────────────────────────────
_SEASONS = {"SP": "spring", "SU": "summer", "FA": "autumn", "WI": "winter"}
SEASON = re.compile(r"\d{4}-(SP|SU|FA|WI)", re.I)
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
    if span and span[0] == dt.date(span[0].year, 1, 1) and span[1] == dt.date(span[0].year, 12, 31):
        return str(span[0].year)
    if re.fullmatch(r"\d{4}-H[12]", period):
        return f"the {'first' if period.endswith('1') else 'second'} half of {period[:4]}"
    if span and span[0].day == 1 and (span[1] + dt.timedelta(days=1)).day == 1:
        first, last = f"{months[span[0].month - 1]} {span[0].year}", f"{months[span[1].month - 1]} {span[1].year}"
        return first if first == last else f"{first} to {last}"
    if not span:
        return period
    day = lambda d: f"{d.day} {months[d.month - 1]} {d.year}"             # noqa: E731
    if (span[0].year, span[0].month) == (span[1].year, span[1].month):
        return f"{span[0].day} to {day(span[1])}"
    return f"{day(span[0])} to {day(span[1])}"


# ── breakdown ──────────────────────────────────────────────────────────────────────────────────
_TIME_UNITS = {"day": "day", "week": "week", "month": "month", "quarter": "quarter", "year": "year"}


# Words of a split phrase that name no category: "breakdown" alone asks for no split by a dimension.
_NO_CATEGORY = {"breakdown", "break", "down", "split", "separate", "separately", "figure", "number", "series",
                "out", "into", "broken"}
# The words before the category in a split phrase: "by", "split by", "broken down by", "across".
_SPLIT_LEAD = re.compile(r"^\s*(?:(?:broken\s+down|break\s+down|split|segmented|grouped|group)\s+)?"
                         r"(?:by|per|for each|across)\s+", re.I)


def split_by(quote: str, surface: dict, principles: list) -> tuple[str, str]:
    """PURE. (kind, target) for a breakdown phrase: ("dimension", name), ("rule", id) for a governed
    rule that names its own words, ("time", unit), ("near", what) when the phrase holds a dimension
    name or a rule's word among other words ("customer segment"), or ("none", "") when the layer has
    no such split."""
    words = _tokens(_SPLIT_LEAD.sub("", quote))
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


def _figure_words(terms: list) -> str:
    """One figure in plain words: "platform android and ios together", "every platform except web",
    "device type mobile and country name Brazil". Values only: saying each value's declared meaning
    made the confirmation judge the definition, which the answer discloses (21 false asks on the
    second replication set); naming a phrase's unused words made it treat "accounts" as a dropped
    restriction (6 of 8 correct readings flagged in calibration). Words beside a value are checked
    before this, in the suggestion step (`kept`)."""
    keep: dict = {}
    drop: dict = {}
    for t in terms:
        for dim, value in t["values"]:
            # An analyst's reading is said in the user's words: it was judged at the higher bar and is
            # stated in the answer, and shown as the value ("device type mobile" for "Samsung phones")
            # the round trip judged it again and said no (development run, 2026-10-10).
            said = f"\"{t['quote']}\"" if t.get("why") else str(value)
            (keep if t["keep"] else drop).setdefault(dim, []).append(said)
    parts = []
    for dim in list(keep) + [d for d in drop if d not in keep]:
        label = dim.split("__")[-1].replace("_", " ")
        named = " and ".join(keep.get(dim, []))
        said = ((named if all(v.startswith('"') for v in keep[dim]) else f"{label} {named}")
                + (" together" if len(keep[dim]) > 1 else "")) if dim in keep else f"every {label}"
        parts.append(said + (f" except {' and '.join(drop[dim])}" if drop.get(dim) else ""))
    return " and ".join(parts)


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
        assumed = list(dict.fromkeys(t["why"] for f in terms for t in f
                                     if t.get("why") and any(v[0] == dim for v in t["values"])))
        listed = [x for r in readings for x in (r if isinstance(r, list) else [r])]
        disclose = " ".join(filter(None, [_meanings(dim, listed, surface)] + [a[0].upper() + a[1:] + "." for a in assumed]))
        decisions.append(_decision("filter", " or ".join(
            f"{dim} in ({', '.join(map(str, r))})" if isinstance(r, list) else f"{dim} = {r}" for r in readings),
            "analyst_judgement" if assumed else "question", disclose=disclose))

    periods, said_as, declared = [], {}, []
    for item in proposal.get("time") or []:
        period, why = period_of(item.get("value"), seasons)
        if period is None:
            decisions.append(_ungrounded("period", why))
        elif period not in periods:
            periods.append(period)
            if SEASON.fullmatch(str(item.get("value") or "")):
                # A season is the calendar's declaration: the answer states its months, and the round
                # trip sees the user's words ("winter 2026" against "December 2025 to February 2026"
                # was read as a different winter).
                said_as[period] = item["quote"]
                declared.append(f"{item['quote'][0].upper() + item['quote'][1:]} is read as {readable(period)} "
                                f"(the company calendar).")
    # A period with no day in the data is refused. A period partly inside it is answered for the days
    # it covers, and the answer says so (the owner's decision, design section 13).
    uncovered = [p for p in periods if not _covered(p, lo, hi)]
    asked, partial = list(periods), []
    for i, p in enumerate(periods):
        first, last = _period_span(p)
        if p not in uncovered and not (lo <= first and last <= hi):
            periods[i] = _range(max(first, lo), min(last, hi))
            partial.append(f"{readable(p)} is only partly in the data; this covers {readable(periods[i])}.")
    if uncovered:
        decisions.append(_refuse("period", "out_of_coverage", f"{' and '.join(readable(p) for p in uncovered)} "
                                 f"{'is' if len(uncovered) == 1 else 'are'} outside the data ({lo} to {hi})"))
    elif not proposal.get("time"):
        decisions.append(_ungrounded("period", "the question states no period that can be placed on the "
                                     "calendar, and no rule supplies one"))
    elif periods:
        decisions.append(_decision("period", " or ".join(periods), "question", disclose=" ".join(declared + partial)))

    group_by, separate, grain, splits = [], False, None, []
    series = proposal.get("series")
    if series:
        group_by, grain = ["metric_time"], series.get("unit") if series.get("unit") in _TIME_UNITS else None
        decisions.append(_decision("group_by", group_by, "question"))
    by_id = {p["id"]: p for p in principles}
    for b in proposal.get("breakdown") or []:
        kind, target = split_by(b["quote"], surface, principles)
        if kind == "dimension" and target not in group_by:
            group_by.append(target)
            splits.append(target.split("__")[-1].replace("_", " "))
            decisions.append(_decision("group_by", [target], "question"))
        elif kind == "rule":
            rule = by_id[target]
            dims_ = [d for d in rule.get("default", []) if d not in filters]
            group_by += [d for d in dims_ if d not in group_by]
            separate = rule.get("combine") == "separate"
            # Said in the user's words: which dimensions the rule supplies is governed, not asked about.
            splits.append(" ".join(_tokens(_SPLIT_LEAD.sub("", b["quote"]))))
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
            "figures": [_figure_words(f) for f in terms if any(t["values"] for t in f)], "splits": splits,
            "asked_periods": asked, "said_as": said_as,
            "values": {d["name"]: d["members"] for d in _dimensions(surface)},
            "period_options": periods,
            "grain": grain, "rule": next((r for r in principles if r.get("slot") == "time_grain"), None),
            "builtin": builtin, "decisions": decisions}
