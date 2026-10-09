"""Guardrail `decision_grounding` (BEFORE): read the question once, then check every governed call.

The same job as `parameter_grounding` (guardrails/parameters.py), with the proposal step replaced by
a decision model (Jev, on OpenRouter's Decisions API). The model is given the question and, for every
value the layer allows, one yes/no question: does the question ask about this value? Every option is
generated from the layer by code, so the model can only name a value that exists:

  each categorical filter   how the question restricts it (names values to keep / names values
                            to leave out / does not / names a value the layer lacks), and one
                            yes/no per member: does the question name it?
  period                    one yes/no per month, quarter and half-year of the calendar years the
                            metric's coverage touches; code decides whether a period is covered
  shape                     total / breakdown / trend / cause (a choice)
  breakdown dimension       the dimensions, time, the governed `canonical_segments` rule, `not_in_list`
  time grain                day / week / month / `not_mentioned`

Asking per value makes the reading a SET: "June compared with May" is yes to two months, and "not
Android" names Android to leave out, which reads as one filter over every other platform. `read` turns the answers into those sets once per metric.
`check` then holds each call the agent makes against them: a value the agent set is kept when the
question allows it and the call is blocked, naming the allowed values, when it does not; a value it
left out is filled from the question or a governed rule. The agent stays free to explore, and no call
is rewritten into a different one. `uncovered` is the answer-side check: given the calls an answer
used, what the question asks for that none of them covers.

The policy is applied by code: a confident value proceeds; an unlisted value or a period outside the
data refuses; a needed value that is not mentioned, or an unsure one, asks. Rules (canonical_segments,
trend_granularity, show_small_choice_sets) are applied by code.

The trade-off against `parameter_grounding`, stated so a reader of a result knows it: the evidence for
a value is the model's probability, not a quoted span of the question.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import urllib.error
import urllib.request

from ..core.conversation import ToolResult  # noqa: F401  (re-exported for the loop's blocked path)
from .parameters import _decision, _lines_up, _period_span, _trend_grain, _ungrounded, surface_for

__all__ = ["ground", "read", "check", "uncovered", "reading_for", "choose_metric", "exit_verdict",
           "ReadingUnavailable",
           "refusal_verdict", "reading_text", "question_level", "read_question", "substitution_refusal",
           "CONFIDENT", "MODEL"]

# Pinned: the alias `~typesafe/jev-latest` moves when the provider ships a version, and a reading
# must be reproducible. Every request also records the version that served it (reading["model"]).
MODEL = "typesafe/jev-1.13-20260917"
# Act on a choice only at or above this probability; below it, ask. 0.7 is where the 120-decision
# fair test (2026-10-03) had no wrong decision left; it is a starting point, not a tuned value.
CONFIDENT = 0.7
# An option counts as a plausible reading of an unsure choice from this probability up.
PLAUSIBLE = 0.15
# Beside a value read with confidence, another value competes only when the model leans towards it.
# Below this, it is the noise every request carries (0.18 for March next to 0.98 for Q2), and in the
# t_009 trap it is the wrong neighbour itself (organic 0.45 beside content_seo 0.78 for "SEO").
LEAN = 0.5
_TIMEOUT = 60

_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
           "October", "November", "December")


# ── the option lists, generated from the layer ────────────────────────────────────────────────

def _dimensions(surface: dict) -> list:
    """One entry per column: the metric's own dimension wins over the same column reached by join."""
    seen, out = set(), []
    for d in sorted(surface["parameters"]["filters"]["dimensions"], key=lambda d: d["joined"]):
        if d["column"] not in seen and d["members"]:
            seen.add(d["column"])
            out.append(d)
    return out


# Who consumes two facts the reading depends on. The defaults are the production setting; governance
# `fact_consumers` overrides them for the readiness audit's controlled test, which holds the code
# fixed and varies only this (02_readiness_audit/controlled.py):
#   value_words  code: the values of every closed dimension are looked up in the question and applied;
#                model: only the decision model reads the question for them
#   coverage     code: periods placed on the calendar, coverage decided by code; model: the decision
#                model is asked whether the period is outside the data (the reader before D5); none:
#                not checked by the reader
CONSUMERS = {"value_words": "code", "coverage": "code"}


def _consumer(surface: dict, fact: str) -> str:
    return (surface.get("consumers") or CONSUMERS)[fact]


def _with_consumers(surface: dict, governance: dict | None) -> dict:
    return {**surface, "consumers": {**CONSUMERS, **((governance or {}).get("fact_consumers") or {})}}


def claimed(question: str, surface: dict) -> dict:
    """PURE. {dimension: [(word, [value])]}: the values of the closed dimensions that the question
    contains, found by code before any model reads the question. The values are the closed lists the
    layer models ("mobile" is a value of device_type), so a word for a value is the value itself.
    The longest phrase wins where phrases overlap. A value of two dimensions ("unknown") is left out:
    which one it means is a judgement, not a lookup. A two-letter code matches only as written in
    capitals: "IN" is India, "in" is a preposition."""
    from .forks import _tokens
    if _consumer(surface, "value_words") != "code":
        return {}
    raw = _tokens(question, cased=True)
    words = [w.lower() for w in raw]
    found = []                                            # (start, end, dimension, word, values)
    for d in _dimensions(surface):
        for m in d["members"]:
            word = str(m)
            if word.lower() in ("true", "false"):
                continue
            phrase, against = (([word], raw) if len(word) <= 2 else (_tokens(word), words))
            found += [(i, i + len(phrase), d["name"], word, [m]) for i in range(len(words) - len(phrase) + 1)
                      if phrase and against[i:i + len(phrase)] == phrase]
    owners: dict = {}
    for *_span, dim, word, _v in found:
        owners.setdefault(word.lower(), set()).add(dim)
    taken, out = set(), {}
    for start, end, dim, word, values in sorted(found, key=lambda f: (f[0] - f[1], f[0])):
        if len(owners[word.lower()]) > 1 or taken & set(range(start, end)):
            continue
        taken |= set(range(start, end))
        if (word, values) not in out.get(dim, []):
            out.setdefault(dim, []).append((word, values))
    return out


def _dimension_of(key: str) -> str | None:
    """The dimension a filter question is about ("mode:", "lacks:", "named:"); None for the others."""
    kind, _, rest = key.partition(":")
    return rest.split(":")[0] if kind in ("mode", "lacks", "named") else None


# The words that turn a value into an exclusion, and the quantifier before them ("on every platform
# except web"). Told in the prompt that "web" is a platform value, the model still read that phrase as
# leaving out a channel the layer lacks (0.90), and with only the value masked as well (0.68). With the
# whole phrase masked, "on [platform]", it did not (0.93 no restriction). A plain mention is left as
# written: masking "Android" in "Google Android phones" made "Google" read as a channel (3 of 3).
_EXCLUDING = r"(?:except(?:\s+for)?|excluding|but\s+not|but|other\s+than|apart\s+from|besides|without|not(?:\s+(?:on|from|in))?)"


def _masked(question: str, found: dict) -> str:
    """The question with each exclusion of a value found by code ("on every platform except web",
    "non-web") replaced by the word's dimension in brackets: "on [platform]". The dimensions the
    lookup did not settle are read on this text. Unchanged when nothing is excluded."""
    for dim, words in found.items():
        label = dim.split("__")[-1]
        every = rf"(?:(?:every|all|any|each)\s+(?:of\s+)?(?:the\s+|our\s+)?{label}s?\s*,?\s*)?"
        for word, _values in words:
            value = r"[\s_-]+".join(map(re.escape, word.split())) + "s?"
            question = re.sub(rf"\b(?:{every}{_EXCLUDING}\s+(?:the\s+)?{value}|non-?{value})\b", f"[{label}]",
                              question, flags=re.I)
    return question


def _clause(member, description: str) -> str:
    for part in description.replace(";", ",").split(","):
        if str(member).lower() in part.lower().split() or f"{member} (" in part or f"{member} is" in part:
            return part.strip()
    return ""


def _periods(lo: dt.date, hi: dt.date, coverage: str = "code") -> dict:
    """Every month, quarter and half-year of the calendar years the coverage window touches, as
    query_metric periods. Periods outside the window are offered too, so that the question's period
    is placed on the calendar by the reader and its coverage is then decided by code (`read`): a
    model asked "is this outside the data?" refused "summer 2026", which is partly inside, also when
    asked whether it lies wholly outside (p 0.70). A period no option fits ("in 2019", "summer") is
    therefore asked about, with the coverage window shown, rather than judged. With the coverage fact
    consumed by the model, only the periods that overlap the window are offered, as before D5."""
    out = {}
    for y in range(lo.year, hi.year + 1):
        for m in range(1, 13):
            out[f"{y}-{m:02d}"] = f"{_MONTHS[m - 1]} {y}."
        for q in range(1, 5):
            out[f"{y}-Q{q}"] = f"Q{q} {y}: {_MONTHS[3 * q - 3]} to {_MONTHS[3 * q - 1]} {y}."
        for h in (1, 2):
            out[f"{y}-H{h}"] = (f"The {'first' if h == 1 else 'second'} half of {y}: "
                                f"{'January to June' if h == 1 else 'July to December'} {y}.")
    return {p: t for p, t in out.items() if coverage != "model" or _covered(p, lo, hi)}


def _covered(period: str, lo: dt.date, hi: dt.date) -> bool:
    """Does any day of the period lie inside the coverage window?"""
    first, last = _period_span(period)
    return first <= hi and last >= lo


def _questions(surface: dict, principles: list, lo: dt.date, hi: dt.date) -> tuple[dict, dict]:
    """The Decisions request, and the map from each yes/no question back to the value it asks about.

    A value the question may name is asked about ON ITS OWN, as a yes/no question, so the reading
    is a SET: "June compared with May" is yes to both months, "not Android" is yes to every other
    platform. A single choice per parameter could hold only one of them, and a second call for
    May then ran as June."""
    questions, back = {}, {}
    for d in _dimensions(surface):
        label, members = d["column"].replace("_", " "), ", ".join(map(str, d["members"]))
        # How the question restricts the dimension, asked once: naming values to keep and naming
        # values to leave out are different readings of the same names ("Android users" against
        # "users not on Android"), and a yes/no on each value alone cannot tell them apart.
        back[f"mode:{d['name']}"] = (d["name"], "mode")
        questions[f"mode:{d['name']}"] = {
            "type": "choice", "instructions": f"How does the question restrict the {label}? The values are: "
                                              f"{members}. Layer description: {d['description']}",
            "criteria": {"only": f"It names the {label} value or values to include.",
                         "except": f"It names a {label} value or values to leave out (not X, except X, "
                                   f"excluding X, non-X).",
                         "none": f"It does not restrict the {label}.",
                         "unlisted": f"It names a {label} value that is not in the list."}}
        # Asked apart from `mode` because a question can name a missing value AND a governed one ("TikTok,
        # using the paid_search figure"); one choice must pick one of them, and the missing value has
        # to win: no governed number answers a question about a value the layer does not have.
        back[f"lacks:{d['name']}"] = (d["name"], "lacks")
        questions[f"lacks:{d['name']}"] = {
            "type": "noul", "instructions": f"Does the question name a {label} that has no counterpart among: "
                                            f"{members}?",
            "criteria": {"true": f"Yes: it names a {label} that none of these values is, contains, or overlaps, "
                                 f"so it cannot be expressed with them at all, even if the question also names "
                                 f"listed values or asks to use one of them instead.",
                         "false": f"No: every {label} it names is one of these, a part of one (a country inside "
                                  f"a region, for example), or a group of them; or it names no {label}."}}
        for i, m in enumerate(d["members"]):
            clause = _clause(m, d["description"])
            key = f"named:{d['name']}:{i}"
            back[key] = (d["name"], m)
            questions[key] = {
                "type": "noul",
                "instructions": f"Does the question name the {label} {m}, either to include it or to leave it "
                                f"out?" + (f" ({clause})" if clause else ""),
                "criteria": {"true": f"It names {m}, a word that means {m}, a part of {m} (a place inside a "
                                     f"region, for example), or a group that contains {m}, as a {label} to "
                                     f"include or to leave out.",
                             "false": f"It does not name {m}."}}
    coverage = _consumer(surface, "coverage")
    for p, text in _periods(lo, hi, coverage).items():
        key = f"period:{p}"
        back[key] = ("period", p)
        questions[key] = {
            "type": "noul", "instructions": f"Does the question ask about this period: {text}",
            "criteria": {"true": "The question names this exact period, alone or as one of several periods "
                                 "it compares.",
                         "false": "The question names a different period, a longer or shorter one that only "
                                  "overlaps this one, or no period at all."}}
    # A stated fact about the data ("now that referral signups have stopped"): which kind, and which
    # value it is about. The value it is about is not what the question asks to count (h_012 counted
    # referral beside paid search and added them up), and whether the fact holds is checked by a
    # governed query, not judged (reading_for).
    questions["premise"] = {
        "type": "choice", "instructions": "Does the question take something about the data as already given?",
        "criteria": {"none": "No: it only asks for figures.",
                     "stopped": "Yes: it states as given that something stopped, ended, dried up or had none.",
                     "other": "Yes: it states as given some other fact (a rise, a fall, a launch, a cause)."}}
    about = {"none": "The stated fact, if any, is about none of these values."}
    for d in _dimensions(surface):
        label = d["column"].replace("_", " ")
        for i, m in enumerate(d["members"]):
            about[f"p:{d['name']}:{i}"] = f"The stated fact is about {label} {m}."
            back[f"p:{d['name']}:{i}"] = (d["name"], m)
    questions["premise_about"] = {"type": "choice", "criteria": about,
                                  "instructions": "If the question takes a fact as given, which value is that fact "
                                                  "about?"}
    if coverage == "model":                     # the reader before D5, kept as the controlled test's arm
        questions["outside"] = {
            "type": "noul", "instructions": f"Does the question name a period outside the data, which covers "
                                            f"{lo} to {hi}?",
            "criteria": {"true": "Yes, at least one period it names lies outside that range.", "false": "No."}}
    questions["shape"] = {"type": "choice", "instructions": "What shape of answer does the question ask for?",
                          "criteria": {"total": "A single number, or one number for each of a few named "
                                                "values or periods being compared.",
                                       "breakdown": "The number split by a category.",
                                       "trend": "How the number changes over time.",
                                       "cause": "Why something happened: a cause or explanation, not a number."}}
    segments = next((p for p in principles if p.get("slot") == "group_by"), None)
    crit = {d["name"]: f"Split by {d['column'].replace('_', ' ')}. ({d['description']})" for d in _dimensions(surface)}
    if segments:
        crit[segments["id"]] = f"The question asks for a breakdown without naming the dimension: {segments['when']}"
    # Time is an option too: "month by month" read as a breakdown would otherwise have no dimension to
    # split by, and be refused as one the layer lacks. metric_time is the group_by a trend takes.
    crit["metric_time"] = "Split by time: one number per day, week or month (\"month by month\", \"over time\")."
    crit["not_in_list"] = "The question asks to split by something that is not one of the listed options."
    questions["breakdown"] = {"type": "choice", "criteria": crit,
                              "instructions": "If the question asks for a breakdown, by what?"}
    questions["time_grain"] = {"type": "choice", "instructions": "Does the question state the size of time buckets?",
                               "criteria": {"day": "Daily.", "week": "Weekly.", "month": "Monthly.",
                                            "quarter": "Quarterly.", "year": "Yearly.",
                                            "not_mentioned": "The question does not state a bucket size."}}
    return questions, back


# ── the request ───────────────────────────────────────────────────────────────────────────────

class ReadingUnavailable(Exception):
    """The decision model could not answer this time: a timeout, a server error, a network failure,
    or a malformed reply. The run falls back to the plain agent for the question and says so; it is
    not an error row. A configuration fault (no key, rejected credentials, unknown model) is NOT this:
    it would fail every row the same way, and a run that silently fell back on every question would
    measure the plain agent under the grounded arm's name, so it stays a hard error."""


def _ask(questions: dict, state: str) -> tuple[dict, float, str]:
    """(answers, cost in USD, the model version that served the request). Raises ReadingUnavailable
    for a transient failure; a configuration fault propagates."""
    from ..runtime.providers import load_env
    load_env()
    base = (os.environ.get("OPEN_ROUTER_BASE_URL") or "").rstrip("/").removesuffix("/v1")
    key = os.environ.get("OPEN_ROUTER_API_KEY")
    if not base or not key:
        raise RuntimeError("decision_grounding needs OPEN_ROUTER_BASE_URL and OPEN_ROUTER_API_KEY")
    body = json.dumps({"model": MODEL, "questions": questions, "state": state}).encode()
    req = urllib.request.Request(base + "/alpha/decisions", data=body, headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=_TIMEOUT))
        return r["answers"], float((r.get("usage") or {}).get("cost") or 0.0), str(r.get("model") or MODEL)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403, 404):
            raise
        raise ReadingUnavailable(f"decision model HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as exc:
        raise ReadingUnavailable(f"decision model unavailable: {type(exc).__name__}") from exc


# ── the policy, applied by code ───────────────────────────────────────────────────────────────
#
# Two steps with different jobs. `read` turns the decision model's answers into what the question
# asks for: a set of values per parameter, plus the refusals, open parameters and rules that follow.
# It runs once per metric per question. `check` holds one call against that reading. A value the
# agent set is kept when the question allows it and blocked, with the allowed values named, when it
# does not; a value the agent left out is filled from the question or a governed rule. Nothing the
# agent set is replaced, so a call for May runs as May or does not run. Earlier, one reading was
# turned into one query and every call to the metric was replaced by it, and the second call of
# "June compared with May" silently ran as June.

def _refuse(parameter: str, reason: str, why: str) -> dict:
    return {**_decision(parameter, "?", "none", state="refuse", why=why), "reason": reason}


def _yes(answers: dict, key: str) -> float:
    return float((answers.get(key) or {}).get("noul") or 0.0)


def _pick(answers: dict, name: str) -> tuple:
    a = answers.get(name) or {}
    choice = a.get("choice")
    return choice, (a.get("probabilities") or {}).get(choice, 0.0)


def _p(answers: dict, name: str, option: str) -> float:
    """The probability the reader gave one option of a choice, whether or not it was the one chosen."""
    return float(((answers.get(name) or {}).get("probabilities") or {}).get(option) or 0.0)


def _norm(value):
    """A filter value for comparison. A list (one IN filter) compares as the set of its members."""
    if isinstance(value, (list, tuple)):
        return frozenset(str(v).strip().lower() for v in value)
    return str(value).strip().lower()


def _shown(dim: str, values) -> str:
    return " or ".join("no filter" if v is None else
                       f"{dim} in ({', '.join(map(str, v))})" if isinstance(v, list) else f"{dim} = {v}"
                       for v in values)


def _fixed_by_metric(builtin: str | None, dim: str) -> bool:
    """Does the metric's own filter already decide this dimension? Then no reading of it matters."""
    return bool(builtin) and _norm(builtin).startswith(_norm(dim) + " ")


def _merged(spans: list) -> list:
    out: list = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1] + dt.timedelta(days=1):
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def _within(span, spans: list) -> bool:
    """Is the span inside the union of the spans?"""
    return any(a <= span[0] and span[1] <= b for a, b in _merged(spans))


def _settle(periods: list, scores: dict | None = None) -> list:
    """The periods the question names, once each. A reading may say yes to a period and to the
    periods inside it. When those inside periods fill it exactly (April, May and June for Q2), they
    are the same period said twice and the longer one is kept.

    When they do not fill it, the scores decide which the question names. "June compared with May"
    read together with Q2 scores the two months above the quarter: the quarter only overlaps them
    and is dropped (r_007). "Month by month for the first half of 2026" scores H1 at 0.98 and
    January and June at 0.75: the half-year is the period and the months are its parts, so it is
    kept and they are absorbed (h2_002, where dropping H1 left February to May open). Without
    scores the longer period is dropped, as before."""
    spans = {p: _period_span(p) for p in periods}
    keep = set(periods)
    for p in sorted(periods, key=lambda p: spans[p][0] - spans[p][1]):     # longest first
        inside = [q for q in keep if q != p and spans[p][0] <= spans[q][0] and spans[q][1] <= spans[p][1]]
        if p not in keep or not inside:
            continue
        if _within(spans[p], [spans[q] for q in inside]) or (
                scores and scores.get(p, 0) > max(scores.get(q, 0) for q in inside)):
            keep -= set(inside)
        else:
            keep.discard(p)
    return [p for p in periods if p in keep]


def read(answers: dict, surface: dict, principles: list, back: dict, lo: dt.date, hi: dt.date,
         found: dict | None = None) -> dict:
    """PURE. What the question asks for, from the decision model's answers.

    Returns {filters: {dim: [values]}, periods: [...], group_by: [...], separate, grain, rule,
    builtin, decisions}. A value list holds every value the question names; `None` in it is the
    reading "no filter", which only a small choice set produces. `decisions` records the basis of
    each value and any refusal or open parameter; a reading with either lets no call run.

    `found` holds the dimension values the question contains (`claimed`). They are named by code,
    not by the model, and a dimension with one is restricted: only whether the question keeps or
    leaves out those values is the model's reading. A group is a value of a modelled attribute
    ("mobile" is a device_type), so it is one figure."""
    found = found or {}
    by_id = {p["id"]: p for p in principles}
    small = next((p for p in principles if p.get("max_options")), None)    # show_small_choice_sets
    builtin = surface.get("filter")
    decisions, filters = [], {}
    if builtin:
        decisions.append(_decision("metric_filter", builtin, "governed_declaration",
                                   disclose=f"{surface['metric']} applies {builtin} by definition.",
                                   why="declared by the metric; not selectable"))

    premise = _premise(answers, back)
    dims: dict = {}
    for key, (dim, value) in back.items():
        if dim == "period" or value in ("mode", "lacks") or key.startswith("p:"):
            continue
        entry = dims.setdefault(dim, {"members": [], "named": [], "maybe": []})
        entry["members"].append(value)
        p = _yes(answers, key)
        if any(value in vs for _w, vs in found.get(dim, ())):
            entry["named"].append(value)
        elif p >= CONFIDENT:
            entry["named"].append(value)
        elif p >= PLAUSIBLE:
            entry["maybe"].append((value, p))
    for e in dims.values():
        e["unsure"] = [v for v, p in e["maybe"] if p >= (LEAN if e["named"] else PLAUSIBLE)]
    # A dimension confidently restricted to named values settles every dimension it determines in
    # the data (each country has one region): a restriction there that names nothing is implied by it,
    # not open (h_007: "countries other than the US" also read as "region: leaves something out").
    determines = surface["parameters"]["filters"].get("determines") or {}
    modes = {dim: _restriction(answers, dim, dim in found) for dim in dims}
    settled = {dim for dim, e in dims.items() if e["named"]
               and modes[dim][0] in ("only", "except") and modes[dim][1] >= CONFIDENT}
    # The metric's own filter settles a dimension too (paying_users fixes status = 'active'), and so
    # every dimension it determines (is_active): h2_005 asked about is_active, which no question can
    # change on this metric.
    settled |= {dim for dim in determines if _fixed_by_metric(builtin, dim)}
    implied_by = {child: parent for parent in settled for child in determines.get(parent, ()) if child != parent}
    redundant = _redundant(dims, modes, settled, determines)
    for dim, e in dims.items():
        name = dim.split("__")[-1]
        mode, p_mode = modes[dim]
        if dim in redundant:
            other = redundant[dim].split("__")[-1]
            decisions.append(_decision("filter", f"{name}: implied", "none", state="dropped",
                                       why=f"the {other} filter already keeps only these rows"))
            continue
        if dim in implied_by and not e["named"]:
            parent = implied_by[dim].split("__")[-1]
            if mode in ("only", "except") or e["unsure"]:
                by = "the metric's own" if _fixed_by_metric(builtin, implied_by[dim]) else "the"
                decisions.append(_decision("filter", f"{name}: implied", "none", state="dropped",
                                           why=f"implied by {by} {parent} filter: each {parent} has one "
                                               f"{name}"))
            continue
        # A term with no counterpart counts against THIS dimension only when the question restricts
        # it: asked alone, the model files an unmatched word under every dimension ("iPhone" read as
        # a channel with no counterpart, 0.82).
        lacks = _yes(answers, f"lacks:{dim}")
        p_unrestricted = ((answers.get(f"mode:{dim}") or {}).get("probabilities") or {}).get("none", 0.0)
        if lacks >= CONFIDENT and p_unrestricted < LEAN and not _fixed_by_metric(builtin, dim):
            decisions.append({**_refuse("filter", "ungoverned_dimension_value",
                                        f"it names a {name} value the layer does not have; the governed "
                                        f"{name} values are {', '.join(map(str, e['members']))}"),
                              "confidence": lacks})
            continue
        if _fixed_by_metric(builtin, dim):
            if mode in ("only", "except"):
                decisions.append(_decision("filter", _shown(dim, e["named"]), "none", state="dropped",
                                           why="the metric already applies its own filter on this dimension"))
            continue
        if p_mode < CONFIDENT and mode != "none" or e["unsure"] and mode in ("only", "except"):
            # Unsure how, or which values. A small set of readings is shown; otherwise ask.
            # "No filter" is a reading only when the model finds an unrestricted question plausible.
            p_none = ((answers.get(f"mode:{dim}") or {}).get("probabilities") or {}).get("none", 0.0)
            readings = e["named"] + e["unsure"] + ([None] if p_none >= PLAUSIBLE else [])
            if small and mode == "only" and e["named"] + e["unsure"] and len(readings) <= small["max_options"]:
                filters[dim] = readings
                decisions.append(_decision("filter", _shown(dim, readings), "governed_principle",
                                           disclose=f"The question does not settle {name}; showing each "
                                                    f"reading: {_shown(dim, readings)}.",
                                           why=f"principle {small['id']}"))
            else:
                decisions.append({**_ungrounded("filter", f"{name}: unsure how the question restricts it "
                                                f"({mode}, p {p_mode:.2f}; unsure about "
                                                f"{', '.join(map(str, e['unsure'])) or 'none'})"),
                                  "confidence": p_mode})
        elif mode == "unlisted":
            decisions.append({**_refuse("filter", "ungoverned_dimension_value",
                                        f"it names a {name} value the layer does not have; the governed "
                                        f"{name} values are {', '.join(map(str, e['members']))}"),
                              "confidence": p_mode})
        elif mode in ("only", "except") and not e["named"]:
            decisions.append(_ungrounded("filter", f"{name}: the question restricts it, but not to a value "
                                         f"that can be identified"))
        elif mode == "only":
            # Only a "stopped" premise names a value that is not counted ("now that referral has
            # stopped, how many through paid search"); in "why did Android opens drop" the value the
            # premise is about is the one counted (r_005).
            counted = [m for m in e["named"]
                       if not (premise.get("kind") == "stopped" and (dim, m) == premise.get("about"))]
            if not counted:                     # only the premise names this dimension: no restriction
                continue
            filters[dim] = counted
            decisions.append({**_decision("filter", _shown(dim, counted), "question",
                                          disclose=_meanings(dim, counted, surface),
                                          why="a value of the dimension, found in the question by code" if dim in found else ""),
                              "confidence": p_mode})
        elif mode == "except":
            # One reading: everything but the named values, as ONE filter (an IN list), because "not
            # Android" asks for one number. Values named to include are each their own reading.
            filters[dim] = [[m for m in e["members"] if m not in e["named"]]]
            decisions.append({**_decision("filter", _shown(dim, filters[dim]), "question",
                                          disclose=_meanings(dim, filters[dim][0], surface),
                                          why=f"the question asks for every {name} except "
                                              f"{', '.join(map(str, e['named']))}: this filter IS that, one figure"),
                              "confidence": p_mode})

    shape, p_shape = _pick(answers, "shape")
    group_by, separate = [], False
    # "Week by week" is a trend and a breakdown by time at once, and the reader splits its confidence
    # between the two (0.62 and 0.30). Both mean one number per time bucket, so they are added.
    p_series = _p(answers, "shape", "trend") + _p(answers, "shape", "breakdown") * _p(answers, "breakdown", "metric_time")
    if shape == "cause" and p_shape >= CONFIDENT:
        # A governed metric reports what happened, not why; the layer holds no causal evidence.
        decisions.append({**_refuse("group_by", "no_causal_evidence",
                                    "the question asks why something happened, and the governed layer "
                                    "holds no causal evidence"), "confidence": p_shape})
    elif p_series >= CONFIDENT:
        group_by = ["metric_time"]
        decisions.append({**_decision("group_by", group_by, "question"), "confidence": p_series})
    elif p_shape < CONFIDENT:
        # The shape only decides what to fill into a call that names no breakdown. Unsure, nothing
        # is filled and the agent's own call stands; asking the user would be about our form, not
        # about their question ("compare June with May" read as a total or as a two-point trend).
        pass
    elif shape == "breakdown":
        dim, p = _pick(answers, "breakdown")
        rule = by_id.get(dim, {})
        if p < CONFIDENT:
            decisions.append({**_ungrounded("group_by", f"breakdown: unsure ({dim}, p {p:.2f})"), "confidence": p})
        elif dim == "not_in_list":
            decisions.append({**_refuse("group_by", "dimension_not_supported",
                                        "the question asks to split by something the layer does not have"),
                              "confidence": p})
        elif rule.get("slot") == "group_by":
            group_by = [d for d in rule.get("default", []) if d not in filters]
            separate = rule.get("combine") == "separate"
            decisions.append({**_decision("group_by", group_by, "governed_principle", disclose=rule.get("disclose", ""),
                                          why=f"principle {rule['id']}"), "confidence": p})
        else:
            group_by = [dim]
            decisions.append({**_decision("group_by", group_by, "question"), "confidence": p})

    said = {p: _yes(answers, f"period:{p}") for _, (k, p) in back.items() if k == "period"}
    periods = _settle([p for p, v in said.items() if v >= CONFIDENT], said)
    unsure = [p for p, v in said.items() if (LEAN if periods else PLAUSIBLE) <= v < CONFIDENT
              and not any(_within(_period_span(q), [_period_span(p)]) or _within(_period_span(p), [_period_span(q)])
                          for q in periods)]
    # A period with no day in the data is refused, also beside a covered one: "June 2026 against June
    # 2025" cannot be compared. A period partly inside reaches the coverage check on the call.
    coverage = _consumer(surface, "coverage")
    uncovered = [p for p in periods if coverage == "code" and not _covered(p, lo, hi)]
    if uncovered:
        decisions.append(_refuse("period", "out_of_coverage", f"{' and '.join(uncovered)} "
                                 f"{'is' if len(uncovered) == 1 else 'are'} outside the data ({lo} to {hi})"))
    elif coverage == "model" and not periods and _yes(answers, "outside") >= CONFIDENT:
        decisions.append(_refuse("period", "out_of_coverage", f"the period asked about is outside the data ({lo} to {hi})"))
    elif unsure:
        decisions.append(_ungrounded("period", f"unsure whether the question includes {', '.join(unsure)}"))
    elif not periods:
        decisions.append(_ungrounded("period", "the question states no period that can be placed on the "
                                     "calendar, and no rule supplies one"))
    else:
        decisions.append(_decision("period", " or ".join(periods), "question"))

    grain, p_grain = _pick(answers, "time_grain")
    return {"filters": filters, "periods": periods, "group_by": group_by, "separate": separate, "premise": premise,
            "values": {dim: e["members"] for dim, e in dims.items()},
            "period_options": [p for _, (k, p) in back.items() if k == "period"
                               and (coverage == "none" or _covered(p, lo, hi))],
            "grain": grain if grain not in (None, "not_mentioned") and p_grain >= CONFIDENT else None,
            "rule": next((r for r in principles if r.get("slot") == "time_grain"), None),
            "builtin": builtin, "decisions": decisions}


def _restriction(answers: dict, dim: str, declared: bool) -> tuple[str, float]:
    """(mode, p): how the question restricts a dimension. With one of its values found in the
    question by code, it is restricted, and the model only decides between keeping and leaving out."""
    mode, p = _pick(answers, f"mode:{dim}")
    if not declared:
        return mode or "none", p                 # no answer: the request did not ask about it
    keep, leave = _p(answers, f"mode:{dim}", "only"), _p(answers, f"mode:{dim}", "except")
    return ("except", leave / (keep + leave)) if leave > keep else ("only", keep / (keep + leave) if keep else 1.0)


def _redundant(dims: dict, modes: dict, settled: set, determines: dict) -> dict:
    """{dimension: the dimension that makes its filter redundant}, for two settled "only" filters
    linked by a value map in the data (platform -> device_type, country -> country_name).

    "Mobile app opens": code finds device_type mobile, and the model also reads platform android and
    ios ("a group that contains android"). The platform values are exactly the mobile ones, so the
    platform filter is dropped and the value the question named stays. "iPhone users": the model reads
    platform ios and device_type mobile; every ios row is mobile, so the device_type filter is dropped.
    A pair that keeps different rows ("mobile users on iPhone" read as android) keeps both filters."""
    out: dict = {}
    for a, linked in determines.items():
        for b, values in (linked or {}).items():
            if not isinstance(values, dict) or a in out or b in out or not {a, b} <= settled & set(dims):
                continue
            if any(modes[x][0] != "only" or dims[x]["unsure"] for x in (a, b)):
                continue
            kept_a, kept_b = ({str(v) for v in dims[x]["named"]} for x in (a, b))
            to = {str(k): str(v) for k, v in values.items()}
            if kept_a == {k for k, v in to.items() if v in kept_b}:
                out[a] = b                        # the same rows: keep the coarser value
            elif {to[k] for k in kept_a if k in to} <= kept_b:
                out[b] = a                        # b keeps every row a keeps, and more
    return out


def _meanings(dim: str, values, surface: dict) -> str:
    """The declared meaning of each value a figure includes, as one sentence for the answer."""
    column = dim.split("__")[-1]
    meanings = next((d.get("meanings") or {} for d in surface["parameters"]["filters"]["dimensions"]
                     if d["name"] == dim), {})
    flat = [x for v in values for x in (v if isinstance(v, list) else [v])]
    said = [f"{column} {v} ({meanings[str(v)]})" for v in flat if str(v) in meanings]
    return f"The figure includes {' and '.join(said)}." if said else ""


def _premise(answers: dict, back: dict) -> dict:
    """PURE. {kind, about: (dim, value) | None, p}: a fact the question takes as given, when the decision
    model reads one with confidence; {} otherwise."""
    kind, p = _pick(answers, "premise")
    if kind in (None, "none") or p < CONFIDENT:
        return {}
    key, p_about = _pick(answers, "premise_about")
    about = back.get(key) if key and key.startswith("p:") and p_about >= CONFIDENT else None
    return {"kind": kind, "about": about, "p": p}


def premise_verdict(reading: dict, metric: str, observed: dict) -> dict | None:
    """PURE. The decision a checked premise leads to. `observed` maps each period checked to the
    governed value for the premise's subject (None for an empty result). A "stopped" premise is
    false when any period shows a positive value: refuse with `false_premise`, naming the figure. It
    holds when every period shows nothing: the reading proceeds, and the check is disclosed."""
    premise = reading.get("premise") or {}
    if premise.get("kind") != "stopped" or not premise.get("about") or not observed:
        return None
    dim, value = premise["about"]
    name = dim.split("__")[-1]
    positive = {p: v for p, v in observed.items() if v}
    if positive:
        period, v = next(iter(positive.items()))
        figure = f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}"
        return {**_refuse("premise", "false_premise",
                          f"the question takes as given that {name} {value} stopped, but {metric} for {name} = "
                          f"{value} in {period} is {figure}"), "confidence": premise["p"]}
    return _decision("premise", f"{name} = {value} stopped", "governed_declaration",
                     disclose=f"Checked: {metric} for {name} = {value} is zero in {', '.join(observed)}, as the "
                              f"question says.", why="premise checked by a governed query")


def _span_of(args: dict):
    """The calendar span a call covers, or None for a form this check cannot place."""
    if args.get("start") or args.get("end"):
        try:
            return dt.date.fromisoformat(str(args["start"])[:10]), dt.date.fromisoformat(str(args["end"])[:10])
        except (KeyError, ValueError):
            return None
    return _period_span(str(args.get("period") or ""))


def check(reading: dict, requested: dict) -> tuple[list, list]:
    """PURE. The queries one call runs as, and the decision record.

    The agent's own values are kept when the question allows them; a call asking for anything else
    does not run, and the record names what the question allows (state `outside`). Values the call
    leaves out are filled: from the question, or from a governed rule. Several allowed values for a
    parameter the call leaves out become one query per value."""
    decisions = list(reading["decisions"])
    if any(d["state"] in ("refuse", "ungrounded") for d in decisions):
        return [], decisions
    outside, fan = [], []
    filters, group_by = {}, list(requested.get("group_by") or [])
    for dim, value in (requested.get("filters") or {}).items():
        allowed = reading["filters"].get(dim)
        name = dim.split("__")[-1]
        if _fixed_by_metric(reading["builtin"], dim):
            decisions.append(_decision("filter", f"{dim} = {value}", "none", state="dropped",
                                       why="the metric already applies its own filter on this dimension"))
        elif allowed is None:
            outside.append(f"{dim} = {value}: the question does not restrict the {name}")
        else:
            match = next((a for a in allowed if a is not None and _norm(a) == _norm(value)), None)
            if match is None:
                literal = " or ".join(f"filters={{'{dim}': {a!r}}}" for a in allowed if a is not None)
                outside.append(f"{dim} = {value}: the question asks about {_shown(dim, allowed)}"
                               + (f"; call with {literal}, or leave the {name} filter out" if literal else ""))
            else:
                filters[dim] = match
    for dim, allowed in reading["filters"].items():
        if dim in filters or dim in (requested.get("filters") or {}):
            continue
        if dim in group_by:
            # A split by a dimension the question restricts keeps the restriction: "every channel
            # apart from partnerships" split by channel ran over all five channels and served the
            # excluded one beside the others (h2_006 after the split was allowed).
            listed = [x for v in allowed if v is not None for x in (v if isinstance(v, list) else [v])]
            if listed and None not in allowed:
                filters[dim] = listed if len(listed) > 1 else listed[0]
            continue
        if len(allowed) == 1 and allowed[0] is not None:
            filters[dim] = allowed[0]
        else:
            fan.append((dim, allowed))
    # A split by a dimension the question names several values of shows each of them, whether the
    # values were read as separate figures or as one list ("every channel apart from partnerships",
    # h2_006: the list was allowed and the split over it was blocked four times).
    may_split = set(reading["group_by"]) | {"metric_time"} | {
        d for d, a in reading["filters"].items()
        if len(a) > 1 or any(isinstance(x, list) and len(x) > 1 for x in a)}
    outside += [f"group_by {g}: the question does not ask to split by {g.split('__')[-1]}"
                for g in group_by if g not in may_split]
    group_by = group_by or list(reading["group_by"])

    base = {k: v for k, v in requested.items() if k not in ("filters", "group_by", "time_grain")}
    periods = reading["periods"]
    if any(requested.get(k) for k in ("period", "start", "end")):
        span = _span_of(requested)
        if span is None or not _within(span, [_period_span(p) for p in periods]):
            asked = requested.get("period") or f"{requested.get('start')}..{requested.get('end')}"
            outside.append(f"period {asked}: the question asks about {' and '.join(periods)}")
    elif len(periods) == 1:
        base["period"] = periods[0]
    else:
        fan.append(("period", periods))
    if outside:
        return [], decisions + [_decision("call", "outside the question", "none", state="outside",
                                          why="; ".join(outside))]

    queries = [{**base, **({"filters": filters} if filters else {}), **({"group_by": group_by} if group_by else {}),
                **({"time_grain": requested["time_grain"]} if requested.get("time_grain") else {})}]
    for key, values in fan:
        out = []
        for q in queries:
            for v in values:
                if key == "period":
                    out.append({**q, "period": v})
                else:
                    f = {**(q.get("filters") or {}), **({key: v} if v is not None else {})}
                    out.append({**{k: x for k, x in q.items() if k != "filters"}, **({"filters": f} if f else {})})
        queries = out
    if reading["separate"]:
        rule_dims = [g for g in group_by if g in reading["group_by"]]
        if len(rule_dims) > 1:
            queries = [{**q, "group_by": [g for g in group_by if g not in rule_dims or g == d]}
                       for q in queries for d in rule_dims]

    for q in queries:
        if "metric_time" not in (q.get("group_by") or []):
            continue
        span, rule = _span_of(q), reading["rule"]
        if reading["grain"]:
            if q.get("time_grain") and q["time_grain"] != reading["grain"]:
                outside.append(f"time_grain {q['time_grain']}: the question asks for {reading['grain']} buckets")
            q["time_grain"] = reading["grain"]
            if span and not _lines_up(q["time_grain"], *span):
                # The grain is the user's, so it is kept; the engine cuts the edge buckets at the
                # period, and the answer says they are partial (D13).
                decisions.append(_decision("time_grain", q["time_grain"], "question",
                                           disclose=f"The first and last {q['time_grain']} buckets are partial: "
                                                    f"they count only the days from {span[0]} to {span[1]}.",
                                           why="the question's grain does not line up with the period"))
        elif q.get("time_grain"):
            if rule and rule.get("buckets_within_period") and span and not _lines_up(q["time_grain"], *span):
                outside.append(f"time_grain {q['time_grain']}: its buckets cross the edges of the period "
                               f"(rule {rule['id']}); use a grain whose buckets line up with it")
        elif rule and q.get("period") and _trend_grain(rule, q["period"]):
            q["time_grain"], _points, _days, disclose = _trend_grain(rule, q["period"])
            decisions.append(_decision("time_grain", q["time_grain"], "governed_principle",
                                       disclose=disclose, why=f"principle {rule['id']}"))
        else:
            decisions.append(_ungrounded("time_grain", "a time series is asked for, but neither the question "
                                         "nor a rule gives its granularity"))
    if outside:
        return [], decisions + [_decision("call", "outside the question", "none", state="outside",
                                          why="; ".join(outside))]
    if any(d["state"] == "ungrounded" for d in decisions):
        return [], decisions
    unique = list({json.dumps(q, sort_keys=True, default=str): q for q in queries}.values())
    return unique, list({json.dumps(d, sort_keys=True, default=str): d for d in decisions}.values())


def uncovered(reading: dict, queries: list) -> list:
    """PURE. What the question asks for that none of these queries covers: a list of (what is
    missing in plain words, the query that would cover it).

    Read against the queries an answer USED (the calls its claims cite), so an exploration call does
    not count. A value is covered by a query that filters on it or splits by its dimension; a period
    by queries whose spans together contain it; a breakdown dimension by a query split by it. The
    covering query is the first used query with the one missing value put in, so it differs from a
    query the agent chose in nothing else."""
    if not queries:
        return []
    template = queries[0]
    missing = []
    for dim, values in reading["filters"].items():
        if len(values) < 2:
            continue
        for v in values:
            if any(dim in (q.get("group_by") or []) or
                   (v is None and dim not in (q.get("filters") or {})) or
                   (v is not None and dim in (q.get("filters") or {}) and _norm(q["filters"][dim]) == _norm(v))
                   for q in queries):
                continue
            f = {k: x for k, x in (template.get("filters") or {}).items() if k != dim}
            if v is not None:
                f[dim] = v
            query = {k: x for k, x in template.items() if k != "filters"}
            missing.append((_shown(dim.split("__")[-1], [v]), {**query, **({"filters": f} if f else {})}))
    spans = [s for s in (_span_of(q) for q in queries) if s]
    if len(reading["periods"]) > 1:
        missing += [(f"period {p}", {**{k: x for k, x in template.items() if k not in ("start", "end")}, "period": p})
                     for p in reading["periods"] if not _within(_period_span(p), spans)]
    for g in reading["group_by"]:
        if g != "metric_time" and not any(g in (q.get("group_by") or []) for q in queries):
            keep_time = ["metric_time"] if "metric_time" in (template.get("group_by") or []) else []
            missing.append((f"the breakdown by {g.split('__')[-1]}", {**template, "group_by": [g] + keep_time}))
    return missing


def ground(question: str, requested: dict, semantic, cursor, governance: dict | None,
           cache: dict) -> tuple[list, list, float]:
    """The queries this call runs as, the decision record, and the decision request's cost in USD.

    The question is read once per metric (the reading is cached; every later call costs nothing) and
    each call is checked against the reading. When no surface or coverage can be read, the agent's
    own call stands."""
    reading, cost = reading_for(question, requested.get("metric", ""), semantic, cursor, governance, cache)
    if reading is None:
        return [requested], [], 0.0
    queries, decisions = check(reading, requested)
    return queries, decisions, cost


def reading_for(question: str, metric: str, semantic, cursor, governance: dict | None,
                cache: dict) -> tuple[dict | None, float]:
    """The reading of the question for one metric, and the request's cost (0.0 from the cache).
    None when the metric's surface or coverage cannot be read."""
    if metric in cache:
        return cache[metric], 0.0
    context = _context(metric, semantic, cursor, governance)
    if context is None:
        return None, 0.0
    found = claimed(question, context[0])
    questions, _back = _questions(*context)
    # The dimensions the lookup did not settle are read without an exclusion of a value it found
    # (`_masked`): "every platform except web" was read as leaving out a channel too.
    masked = _masked(question, found)
    other = {k: q for k, q in questions.items() if masked != question and _dimension_of(k) not in (None, *found)}
    answers, cost, model = _ask({k: q for k, q in questions.items() if k not in other}, question)
    if other:
        more, extra, _model = _ask(other, masked)
        answers, cost = {**answers, **more}, cost + extra
    # The raw answers and the serving version are kept with the reading, so a stored row can be
    # replayed (`replay`) and the reading evaluated as a component without a new request.
    reading = {**_decide(answers, metric, semantic, context, found), "model": model}
    if not _refuses(reading):
        residual, more, _model = _ask(residual_question(metric, reading, (governance or {}).get("segments")), question)
        cost += more
        reading = with_residual(reading, residual)
    cache[metric] = reading
    return cache[metric], cost


def replay(stored: dict, metric: str, semantic, cursor, governance: dict | None, question: str = "") -> dict | None:
    """The stored reading decided again from its stored answers by the current code: no request, so
    a change to the reading logic is checked on past runs at no cost. None when the metric can no
    longer be read. `residual_stale` is set when the residual question the current reading would ask
    is not the one that was answered (it is conditioned on the reading); its stored answer is then
    applied as it stands, and the result is a guess for that part. With the question, the dimension
    values it contains are looked up again (`claimed`); without it, none are."""
    context = _context(metric, semantic, cursor, governance)
    if context is None:
        return None
    reading = _decide(stored["answers"], metric, semantic, context, claimed(question, context[0]) if question else {})
    if _refuses(reading):
        return reading
    asked = stored.get("residual")
    if asked is None:          # the stored reading refused, so the residual was never asked
        return {**reading, "residual_stale": True}
    return {**with_residual(reading, asked["answers"]), "residual_stale": summary(metric, reading) != summary(metric, stored)}


def _context(metric: str, semantic, cursor, governance: dict | None) -> tuple | None:
    """(surface, principles, lo, hi): what a reading of `metric` is made against. None when the
    surface or the coverage window cannot be read."""
    surface = surface_for(semantic, cursor, metric)
    lo, hi = (semantic.coverage_window(metric) if hasattr(semantic, "coverage_window") else (None, None))
    if surface is None or not lo or not hi:
        return None
    surface = _with_consumers(surface, governance)
    return surface, list((governance or {}).get("methodological_rules") or []), lo, hi


def _decide(answers: dict, metric: str, semantic, context: tuple, found: dict) -> dict:
    """The reading from the decision model's answers and the dimension values found in the question, with
    the premise checked against the data."""
    surface, principles, lo, hi = context
    _, back = _questions(surface, principles, lo, hi)
    reading = {**read(answers, surface, principles, back, lo, hi, found), "answers": answers,
               "claimed": {dim: [list(wv) for wv in ws] for dim, ws in found.items()}}
    verdict = premise_verdict(reading, metric, _premise_observed(semantic, metric, reading))
    return {**reading, "decisions": reading["decisions"] + [verdict]} if verdict is not None else reading


def _refuses(reading: dict) -> bool:
    return any(d["state"] == "refuse" for d in reading["decisions"])


def _premise_observed(semantic, metric: str, reading: dict) -> dict:
    """The governed value for the premise's subject in each period the question names: the data,
    not the model, decides whether the premise holds. {} when there is nothing to check."""
    premise = reading.get("premise") or {}
    if premise.get("kind") != "stopped" or not premise.get("about") or not reading["periods"] \
            or not hasattr(semantic, "query_with_sql"):
        return {}
    dim, value = premise["about"]
    observed = {}
    for period in reading["periods"]:
        try:
            _sql, cols, rows = semantic.query_with_sql(metric, filters={dim: value}, period=period)
        except Exception:                                       # noqa: BLE001 — a check that cannot run decides nothing
            return {}
        observed[period] = rows[0][-1] if rows and rows[0] else None
    return observed


def summary(metric: str, reading: dict) -> str:
    """What the reading found, in plain words, for the residual question to compare against."""
    parts = [f"the metric {metric}"]
    for dim, values in reading["filters"].items():
        shown = [("in (" + ", ".join(map(str, v)) + ")") if isinstance(v, list) else "any" if v is None else f"= {v}"
                 for v in values]
        parts.append(f"{dim.split('__')[-1]} " + " or ".join(shown))
    if reading["periods"]:
        parts.append("period " + " and ".join(reading["periods"]))
    if reading["group_by"]:
        parts.append("split by " + ", ".join(g.split("__")[-1] for g in reading["group_by"]))
    if reading.get("builtin"):
        parts.append(f"always {reading['builtin'].split('__')[-1]}")
    return "; ".join(parts)


def residual_question(metric: str, reading: dict, segments: dict | None = None) -> dict:
    """The residual, asked AFTER the reading and conditioned on it.

    Every other question asks about a value the layer has, so a group it does not have ("emerging
    markets", "power users") is never asked about and reads as no restriction (h_015 and h_019 served
    the unrestricted totals). Asked in general, the question also fired on restrictions the reading
    had expressed ("countries other than the US" 0.75, above the bar); asked about what lies BEYOND the
    reading, the two targets scored 0.85 and 0.86 and no question with an answer scored above 0.48."""
    governed = "; ".join(f"{name} ({' '.join(str((s or {}).get('means') or '').split())})"
                         for name, s in (segments or {}).items())
    return {"beyond": {
        "type": "noul",
        "instructions": f"The question has been read as asking for: {summary(metric, reading)}. Does it ALSO "
                        "narrow down who or what is counted by something this reading does not include?"
                        + (f" Governed segments that exist: {governed}." if governed else ""),
        "criteria": {"true": "Yes: it limits the count to a group, kind or condition (a market, a tier, a "
                             "behaviour, a cohort) that the reading above leaves out.",
                     "false": "No: every restriction it makes is in the reading above, or it makes none "
                              "beyond it."}}}


def with_residual(reading: dict, answers: dict) -> dict:
    """PURE. The reading with the residual's verdict: a restriction it leaves out is open. Open, not
    refused: the group may map onto governed values the user can name ("emerging markets" as
    countries), or onto nothing; asking covers both, and a refusal stays legal."""
    p = _yes(answers, "beyond")
    decisions = list(reading["decisions"])
    if p >= CONFIDENT:
        decisions.append({**_ungrounded("group", "the question narrows who or what is counted by something the "
                                        "reading does not include, and no dimension value or governed segment "
                                        "expresses it"), "confidence": p})
    return {**reading, "decisions": decisions, "residual": {"p": p, "answers": answers}}


# ── the question as a whole: which fork word it uses, and whether it asks to bend the rules ───────

def question_questions(vocabulary: dict[str, tuple[str, ...]]) -> tuple[dict, dict]:
    """The question-level request. Two things are properties of the question, not of any metric:

      term          which declared word it uses for what it counts ("customers", "app opens",
                    "marketing spend"), or a metric named directly, or none. The layer declares what
                    each word means for each team, so the word decides the metric
                    (guardrails/forks.py).
      substitution  whether it asks to present one figure as another, or to set the rules aside.
                    No governed number answers such a request, whatever else it names (h_013)."""
    back = {f"t{i}": term for i, term in enumerate(vocabulary)}
    crit = {key: f"It uses the word '{term}'" + (f" (or {', '.join(vocabulary[term])})" if vocabulary[term] else "")
                 + " for what it asks to count." for key, term in back.items()}
    crit["named"] = ("It names one specific governed metric by its own name (for example active_accounts or "
                     "acquisition_spend), not a general word.")
    crit["none"] = "It uses none of these words."
    questions = {
        "term": {"type": "choice", "criteria": crit,
                 "instructions": "Which of these words does the question use for what it asks to count?"},
        "substitution": {
            "type": "noul",
            "instructions": "Does the question ask to present one figure as a different one, or to set the "
                            "governance rules aside?",
            "criteria": {"true": "It asks to report one value's or metric's number under another's name, to use "
                                 "one figure in place of another, or to ignore or bypass the rules.",
                         "false": "It asks for figures as they are defined."}}}
    return (questions if back else {"substitution": questions["substitution"]}), back


def read_question(answers: dict, back: dict) -> dict:
    """PURE. {term, term_known, substitution}: the fork word the question uses (None for none or a
    metric named directly), whether that is known with confidence, and the substitution probability."""
    choice, p = _pick(answers, "term")
    return {"term": back.get(choice), "term_known": bool(back) and p >= CONFIDENT,
            "substitution": _yes(answers, "substitution")}


def question_level(cache: dict, question: str, semantic) -> tuple[dict, float]:
    """The question-level reading, made once per run and kept with the readings (`_question`), so it
    is stored on the row. A later ask returns it at no cost."""
    if "_question" in cache:
        return cache["_question"], 0.0
    from .forks import longest_term, vocabulary
    questions, back = question_questions(vocabulary(semantic))
    answers, cost, model = _ask(questions, question)
    read = read_question(answers, back)
    if read["term"]:
        # The model judges which declared word names the counted thing; code settles which declared
        # phrase that word belongs to ("paying customers" over "customers").
        read = {**read, "chosen": read["term"], "term": longest_term(question, read["term"], semantic)}
    cache["_question"] = {**read, "answers": answers, "model": model}
    return cache["_question"], cost


def unchecked(why: str) -> dict:
    """The decision recorded when the question could not be read: the call runs as written, and the
    reader is told so."""
    return _decision("parameters", "as the agent wrote them", "none", why=why,
                     disclose="The question could not be read this time, so this query's parameters were "
                              "not checked against it.")


def substitution_refusal() -> dict:
    return _refuse("request", "other", "the question asks to present one figure as a different one, or to set "
                                       "the governance rules aside; no governed number answers that")


def reading_text(metric: str, reading: dict, routed: dict | None = None) -> str:
    """The reading as the agent reads it before its first call: what the question allows, what it
    leaves open, and what the layer lacks. The same reading every call and the final action are
    checked against, so a call written from it runs on the first try."""
    lines = ["[question reading] Before you act: how the governed layer reads this question. Every "
             "query_metric call is checked against it; a value it does not allow will not run.",
             f"  - metric: {metric}" + (f" ({routed['disclose']})" if routed and routed.get("disclose") else "")]
    refusals = [d for d in reading["decisions"] if d["state"] == "refuse"]
    open_ = [d for d in reading["decisions"] if d["state"] == "ungrounded"]
    for dim, values in reading["filters"].items():
        how = (f"one figure for {_shown(dim, values)}" if len(values) == 1 else
               f"one figure for EACH of {_shown(dim, values)}")
        literal = " or ".join(f"filters={{'{dim}': {v!r}}}" for v in values if v is not None)
        lines.append(f"  - filter {dim}: {how}" + (f"; call with {literal}" if literal else "")
                     + ("; a list is ONE query and one figure, never a sum of separate queries"
                        if any(isinstance(v, list) for v in values) else ""))
    if reading["periods"]:
        lines.append(f"  - period: {' and '.join(reading['periods'])}"
                     + (" (one figure for each)" if len(reading["periods"]) > 1 else ""))
    if reading["group_by"]:
        lines.append(f"  - breakdown: {', '.join(reading['group_by'])}"
                     + (" (each dimension in its own query)" if reading["separate"] else ""))
    lines += ["  - not read as a restriction: every other dimension. If the question names or narrows by "
              "anything not listed here, the layer may not have it: ask the user or refuse, and do not "
              "answer for everyone instead."]
    lines += [f"  - {d['parameter']}: {d['disclose']}" for d in reading["decisions"]
              if d["state"] == "applied" and d.get("disclose")]
    if refusals:
        lines += [f"  - REFUSE ({d['reason']}): {d['why']}. No governed number answers the question; do "
                  f"not offer another value's figure or a mapping." for d in refusals]
    if open_:
        lines += [f"  - OPEN {d['parameter']}: {d['why']}. Ask the user with `clarify`, offering governed "
                  f"values." for d in open_]
    return "\n".join(lines)


def choose_metric(question: str, metrics: dict, words: dict | None = None) -> dict:
    """Which governed metric the question asks for, read by the decision model from the catalogue:
    {choice, p, probabilities, cost, model}. `not_in_list` and `not_mentioned` are returned as such."""
    answers, cost, model = _ask(_metric_questions(metrics, words), question)
    a = answers.get("metric") or {}
    probabilities = a.get("probabilities") or {}
    choice = a.get("choice")
    return {"choice": choice, "p": probabilities.get(choice, 0.0), "probabilities": probabilities,
            "cost": cost, "model": model}


def exit_verdict(reading: dict, args: dict) -> tuple[str, str | None] | None:
    """PURE. Is this clarifying question a legal final action, given the reading of the question?

    Returns None when it is, or (message, refusal reason) when it is not; a refusal reason means
    the only legal action is to refuse. Three rules, in order:

      1. the reading refuses (the question names a value the layer does not have, a period outside
         the data, a cause): refuse, whatever else the question names. A substitute value or a
         mapping offered to the user would be a number the layer does not govern.
      2. the options offered must be governed values of the parameter asked about.
      3. a parameter the reading settles is not a question for the user."""
    refused = next((d for d in reading["decisions"] if d["state"] == "refuse"), None)
    if refused is not None:
        return (f"[policy] Your clarifying question was not accepted: {refused['why']}. No governed "
                f"number answers this question, so do not offer another value's figure or ask the user "
                f"to map it to one. Refuse with `{refused['reason']}`.", refused["reason"])
    parameter = str(args.get("parameter") or "")
    options = [str(o) for o in (args.get("options") or [])]
    # Any governed value of the metric may be offered, not only one of the parameter named: "Europe"
    # is fairly asked about as the countries GB, DE, FR as well as the region EMEA.
    governed = {_norm(v) for values in reading["values"].values() for v in values} | \
               {_norm(p) for p in reading["period_options"]}
    foreign = [o for o in options if _norm(o) not in governed]
    if parameter != "metric" and foreign:
        listing = "; ".join(f"{d.split('__')[-1]}: {', '.join(map(str, v))}" for d, v in reading["values"].items())
        return (f"Your clarifying question was not accepted: {', '.join(foreign)} "
                f"{'is' if len(foreign) == 1 else 'are'} not governed values. Ask again offering only governed "
                f"values ({listing}), or refuse if none fits.", None)
    if parameter != "metric" and not any(d["state"] == "ungrounded" for d in reading["decisions"]):
        settled = "; ".join(f"{d['parameter']} {d['value']}" + (f" ({d['disclose']})" if d.get("disclose") else "")
                            for d in reading["decisions"]
                            if d["state"] == "applied" and d["basis"] in ("question", "governed_principle"))
        return (f"Your clarifying question was not accepted: the question and the governed rules already "
                f"settle every parameter ({settled}). Answer it with query_metric, showing every reading a "
                f"rule lists, or refuse if no governed number answers it.", None)
    return None


# Refusal codes that claim a PARAMETER value is missing from the layer. Only these are second-guessed
# against the reading: a false premise or a cause question is a refusal the reading knows nothing about.
_PARAMETER_REFUSALS = ("ungoverned_dimension_value", "dimension_not_supported")


def refusal_verdict(reading: dict, reason: str) -> tuple[str, str | None] | None:
    """PURE. Is this refusal legal under the reading? None when it is, or (message, refusal reason).

      1. the reading refuses: the refusal must carry the reading's code (TikTok is a missing VALUE,
         `ungoverned_dimension_value`, not a missing dimension).
      2. a refusal claiming a parameter value is missing, where the reading finds that parameter
         only OPEN (Europe is part of EMEA, not absent from the layer): ask instead."""
    refused = next((d for d in reading["decisions"] if d["state"] == "refuse"), None)
    if refused is not None:
        if reason == refused["reason"]:
            return None
        return (f"[policy] Your refusal was not accepted as sent: {refused['why']}. Refuse with "
                f"`{refused['reason']}`.", refused["reason"])
    open_filters = [d for d in reading["decisions"] if d["state"] == "ungrounded" and d["parameter"] == "filter"]
    if reason in _PARAMETER_REFUSALS and open_filters:
        return (f"Your refusal was not accepted: the layer is not missing this value. "
                f"{open_filters[0]['why']}. Ask the user with `clarify`, offering the governed values.", None)
    return None


# ── decision_plan: ground first, then construct the terminal action ───────────────────────────
#
# `decision_grounding` grounds a query when the agent calls one. `decision_plan` moves the whole
# decision to the start of the run and takes the last step away from the generative model:
#
#   1. the metric      one Jev choice over the governed catalogue, plus `not_in_list`; a contested
#                      metric is routed to the requester team's definition (parameters.route_metric)
#   2. the parameters  as in `ground` above
#   3. the action      refuse, ask or answer, decided by code from the decision record
#   4. the output      written by the mechanism: a refusal with its reason code, a question naming
#                      what is missing, or an answer built from the values the queries returned,
#                      so no figure is retyped by a model
#
# When a plan cannot be formed (no surface, no coverage), `plan` returns None and the run continues
# through the agent loop as before.

def _metric_questions(metrics: dict, words: dict | None = None) -> dict:
    """The metric-choice request. Each option carries the words the layer declares for the metric
    (`meta.terms`): without them the model read "revenue" as no metric (0.48) and "subscribers" as
    active_subscriptions, though the layer declares both (2026-10-08 wording sweep)."""
    words = words or {}
    crit = {name: f"{name}: {' '.join((m.get('description') or '').split())[:260]}"
                  + (f" Answers to: {', '.join(words[name])}." if words.get(name) else "")
            for name, m in metrics.items()}
    crit["not_mentioned"] = ("The question names no measure, or one too vague to choose between these "
                             "(for example 'how are we doing' or 'the numbers').")
    crit["not_in_list"] = "The question names a specific measure that none of these metrics counts."
    return {"metric": {"type": "choice", "criteria": crit,
                       "instructions": "Which governed metric does the question ask for?"}}


def _fmt(v) -> str:
    if v is None:
        return "no data"
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.2f}"


def _label(label, grain: str | None) -> str:
    """A result label as a reader writes it: 2026-05 for a month, 2026-05-04 for a day or week."""
    s = str(label)
    if not s[:4].isdigit():
        return s
    return s[:7] if grain == "month" else s[:10]


def _scope(q: dict) -> str:
    parts = [f"{k.split('__')[-1]} = {v}" for k, v in (q.get("filters") or {}).items()]
    return ", ".join(parts) if parts else "all accounts the metric counts"


def _plain_filter(metric: str, governance: dict | None) -> str:
    """The metric's built-in filter in the governance file's own words (its segment's `means`)."""
    governance = governance or {}
    seg = (governance.get("measures") or {}).get(metric, {}).get("segment")
    means = ((governance.get("segments") or {}).get(seg) or {}).get("means")
    return f"{metric} counts {seg} only: {means}" if seg and means else ""


def answer_text(metric: str, queries: list, results: list, decisions: list,
                governance: dict | None = None) -> str:
    """The answer, written from the returned values. Figures are copied, never generated."""
    lines = []
    for q, r in zip(queries, results):
        pairs = list(zip(r.labels or [""], r.values or []))
        head = f"{metric} ({_scope(q)}; period {q.get('period', 'all data')})"
        if q.get("group_by"):
            by = q.get("time_grain") if q["group_by"] == ["metric_time"] else q["group_by"][0].split("__")[-1]
            pairs = sorted(pairs, key=lambda p: str(p[0]))
            lines.append(f"{head}, by {by}: " + "; ".join(f"{_label(k, q.get('time_grain'))} {_fmt(v)}"
                                                          for k, v in pairs) + ".")
        else:
            lines.append(f"{head}: {_fmt(pairs[0][1]) if pairs else 'no data'}.")
    notes = [(_plain_filter(metric, governance) or d["disclose"]) if d["parameter"] == "metric_filter" else d["disclose"]
             for d in decisions if d.get("disclose") and d["basis"] in ("governed_declaration", "governed_principle")]
    return "\n".join(lines + ([""] + notes if notes else []))


def question_text(decisions: list, lo, hi, metric_options: list) -> str:
    """The clarifying question, naming what is missing and what would settle it."""
    asks = []
    for d in decisions:
        if d["state"] != "ungrounded":
            continue
        if d["parameter"] == "period":
            asks.append(f"Which period do you mean? The data covers {lo} to {hi}; for example a month "
                        f"(2026-06), a quarter (2026-Q2) or a half-year (2026-H1).")
        elif d["parameter"] == "metric":
            asks.append("Which measure do you mean" + (f": {', '.join(metric_options)}?" if metric_options else "?"))
        else:
            asks.append(f"Please specify the {d['parameter'].replace('_', ' ')}: {d['why']}.")
    return " ".join(dict.fromkeys(asks)) or "Please specify the question further."


def refusal_text(decisions: list, surface: dict | None, question: str = "") -> tuple[str, str]:
    """(reason code, explanation) for a refusal, quoting the question and naming what the layer has."""
    d = next(x for x in decisions if x["state"] == "refuse")
    text = f"No governed number answers \"{question}\": {d['why']}." if question else \
        f"No governed number answers this question: {d['why']}."
    if d["parameter"] == "filter" and surface:
        dims = {x["column"]: x["members"] for x in surface["parameters"]["filters"]["dimensions"] if x["members"]}
        text += " The governed values are: " + "; ".join(f"{k}: {', '.join(map(str, v))}" for k, v in dims.items()
                                                       if k != "is_internal") + "."
    return d["reason"], text


def plan(question: str, toolbox, governance: dict | None) -> dict | None:
    """The whole decision for one question, made before the agent acts. Returns
    {action, reason, text, metric, queries, results, decisions, cost} or None to fall back."""
    from .parameters import route_metric
    semantic = toolbox.semantic
    metrics = getattr(semantic, "metrics", None) or {}
    if not metrics:
        return None
    from .forks import words_by_metric
    answers, cost, _model = _ask(_metric_questions(metrics, words_by_metric(semantic)), question)
    choice = (answers.get("metric") or {}).get("choice")
    probs = (answers.get("metric") or {}).get("probabilities") or {}
    p = probs.get(choice, 0.0)
    decisions: list = []
    if choice == "not_in_list" and p >= CONFIDENT:
        decisions.append({**_refuse("metric", "no_governed_definition",
                                    "no governed metric measures what the question asks for"), "confidence": p})
        return {"action": "refuse", "decisions": decisions, "cost": cost, "metric": None,
                "reason": "no_governed_definition", "queries": [], "results": [],
                "text": "No governed number answers this question: no governed metric measures what it asks for. "
                        "The governed metrics are: " + ", ".join(metrics) + "."}
    if choice == "not_mentioned" and p >= CONFIDENT:
        decisions.append({**_ungrounded("metric", "the question names no measure"), "confidence": p})
        return {"action": "ask", "decisions": decisions, "cost": cost, "metric": None, "reason": "underspecified_request",
                "queries": [], "results": [],
                "text": "Which measure, period and segment do you mean? For example: app opens, active users or "
                        "completed habits, for a month such as 2026-06."}
    if p < CONFIDENT or choice not in metrics:
        options = [k for k, v in sorted(probs.items(), key=lambda kv: -kv[1]) if v >= PLAUSIBLE and k in metrics]
        decisions.append({**_ungrounded("metric", f"unsure ({choice}, p {p:.2f})"), "confidence": p})
        return {"action": "ask", "decisions": decisions, "cost": cost, "metric": None, "reason": "underspecified_request",
                "queries": [], "results": [], "text": question_text(decisions, None, None, options or list(metrics)[:5])}
    metric, routed = route_metric(choice, governance, semantic)
    decisions.append({**_decision("metric", choice, "question"), "confidence": p})
    if routed is not None:
        decisions.append(routed)
        if routed["state"] == "ungrounded":
            return {"action": "ask", "decisions": decisions, "cost": cost, "metric": None,
                    "reason": "competing_definitions", "queries": [], "results": [],
                    "text": question_text(decisions, None, None, [])}
    surface = surface_for(semantic, toolbox.con, metric)
    lo, hi = (semantic.coverage_window(metric) if hasattr(semantic, "coverage_window") else (None, None))
    if surface is None or not lo or not hi:
        return None
    queries, more, cost2 = ground(question, {"metric": metric}, semantic, toolbox.con, governance, {})
    decisions += more
    cost += cost2
    out = {"metric": metric, "decisions": decisions, "cost": cost, "queries": queries, "results": []}
    if any(d["state"] == "refuse" for d in decisions):
        reason, text = refusal_text(decisions, surface, question)
        return {**out, "action": "refuse", "reason": reason, "text": text}
    if not queries:
        return {**out, "action": "ask", "reason": "underspecified_request",
                "text": question_text(decisions, lo, hi, [])}
    results = [toolbox.dispatch("query_metric", q) for q in queries]
    blocked = next((r for r in results if r.is_error), None)
    if blocked is not None:
        # A guardrail refused a planned query (for example a period only partly inside coverage).
        return {**out, "results": results, "action": "refuse", "reason": blocked.reason or "other",
                "text": f"No governed number answers this question: {blocked.content[:300]}"}
    return {**out, "results": results, "action": "answer", "reason": None,
            "text": answer_text(metric, queries, results, decisions, governance)}
