"""Guardrail `decision_grounding` (BEFORE): read the question once, then check every governed call.

The same job as `parameter_grounding` (guardrails/parameters.py), with the proposal step replaced by
a decision model (Jev, on OpenRouter's Decisions API). The model is given the question and, for every
value the layer allows, one yes/no question: does the question ask about this value? Every option is
generated from the layer by code, so the model can only name a value that exists:

  each categorical filter   how the question restricts it (names values to keep / names values
                            to leave out / does not / names a value the layer lacks), and one
                            yes/no per member: does the question name it?
  period                    one yes/no per month, quarter and half-year inside the metric's
                            coverage, plus "a period outside the data"
  shape                     total / breakdown / trend / cause (a choice)
  breakdown dimension       the dimensions, the governed `canonical_segments` rule, `not_in_list`
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
import urllib.error
import urllib.request

from ..core.conversation import ToolResult  # noqa: F401  (re-exported for the loop's blocked path)
from .parameters import _decision, _lines_up, _period_span, _trend_grain, _ungrounded, surface_for

__all__ = ["ground", "read", "check", "uncovered", "reading_for", "choose_metric", "exit_verdict",
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


def _clause(member, description: str) -> str:
    for part in description.replace(";", ",").split(","):
        if str(member).lower() in part.lower().split() or f"{member} (" in part or f"{member} is" in part:
            return part.strip()
    return ""


def _periods(lo: dt.date, hi: dt.date) -> dict:
    """Every month, quarter and half-year that overlaps the coverage window, as query_metric periods."""
    out = {}
    y, m = lo.year, lo.month
    while (y, m) <= (hi.year, hi.month):
        out[f"{y}-{m:02d}"] = f"{_MONTHS[m - 1]} {y}."
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    for y in range(lo.year, hi.year + 1):
        for q in range(1, 5):
            first, last = dt.date(y, 3 * q - 2, 1), dt.date(y + (q == 4), 1 if q == 4 else 3 * q + 1, 1)
            if first <= hi and last > lo:
                out[f"{y}-Q{q}"] = f"Q{q} {y}: {_MONTHS[3 * q - 3]} to {_MONTHS[3 * q - 1]} {y}."
        for h in (1, 2):
            first, last = dt.date(y, 1 if h == 1 else 7, 1), dt.date(y + (h == 2), 7 if h == 1 else 1, 1)
            if first <= hi and last > lo:
                out[f"{y}-H{h}"] = (f"The {'first' if h == 1 else 'second'} half of {y}: "
                                    f"{'January to June' if h == 1 else 'July to December'} {y}.")
    return out


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
    for p, text in _periods(lo, hi).items():
        key = f"period:{p}"
        back[key] = ("period", p)
        questions[key] = {
            "type": "noul", "instructions": f"Does the question ask about this period: {text}",
            "criteria": {"true": "The question names this exact period, alone or as one of several periods "
                                 "it compares.",
                         "false": "The question names a different period, a longer or shorter one that only "
                                  "overlaps this one, or no period at all."}}
    questions["outside"] = {
        "type": "noul", "instructions": f"Does the question name a period outside the data, which covers "
                                        f"{lo} to {hi}?",
        "criteria": {"true": "Yes, at least one period it names lies outside that range.",
                     "false": "No."}}
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
    crit["not_in_list"] = "The question asks to split by something that is not one of the listed options."
    questions["breakdown"] = {"type": "choice", "criteria": crit,
                              "instructions": "If the question asks for a breakdown, by what?"}
    questions["time_grain"] = {"type": "choice", "instructions": "Does the question state the size of time buckets?",
                               "criteria": {"day": "Daily.", "week": "Weekly.", "month": "Monthly.",
                                            "not_mentioned": "The question does not state a bucket size."}}
    return questions, back


# ── the request ───────────────────────────────────────────────────────────────────────────────

def _ask(questions: dict, state: str) -> tuple[dict, float, str]:
    """(answers, cost in USD, the model version that served the request)."""
    from ..runtime.providers import ProviderError, load_env
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
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403, 404):
            raise
        exc.status_code = exc.code
        raise ProviderError(exc) from exc
    return r["answers"], float((r.get("usage") or {}).get("cost") or 0.0), str(r.get("model") or MODEL)


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


def _settle(periods: list) -> list:
    """The periods the question names, once each. A reading may say yes to a period and to the
    periods inside it. When those inside periods fill it exactly (April, May and June for Q2), they
    are the same period said twice and the longer one is kept; when they do not ("June compared with
    May" read together with Q2), the longer one only overlaps them and is dropped."""
    spans = {p: _period_span(p) for p in periods}
    keep = set(periods)
    for p in sorted(periods, key=lambda p: spans[p][0] - spans[p][1]):     # longest first
        inside = [q for q in keep if q != p and spans[p][0] <= spans[q][0] and spans[q][1] <= spans[p][1]]
        if p not in keep or not inside:
            continue
        if _within(spans[p], [spans[q] for q in inside]):
            keep -= set(inside)
        else:
            keep.discard(p)
    return [p for p in periods if p in keep]


def read(answers: dict, surface: dict, principles: list, back: dict, lo: dt.date, hi: dt.date) -> dict:
    """PURE. What the question asks for, from the decision model's answers.

    Returns {filters: {dim: [values]}, periods: [...], group_by: [...], separate, grain, rule,
    builtin, decisions}. A value list holds every value the question names; `None` in it is the
    reading "no filter", which only a small choice set produces. `decisions` records the basis of
    each value and any refusal or open parameter; a reading with either lets no call run."""
    by_id = {p["id"]: p for p in principles}
    small = next((p for p in principles if p.get("max_options")), None)    # show_small_choice_sets
    builtin = surface.get("filter")
    decisions, filters = [], {}
    if builtin:
        decisions.append(_decision("metric_filter", builtin, "governed_declaration",
                                   disclose=f"{surface['metric']} applies {builtin} by definition.",
                                   why="declared by the metric; not selectable"))

    dims: dict = {}
    for key, (dim, value) in back.items():
        if dim == "period" or value in ("mode", "lacks"):
            continue
        entry = dims.setdefault(dim, {"members": [], "named": [], "maybe": []})
        entry["members"].append(value)
        p = _yes(answers, key)
        if p >= CONFIDENT:
            entry["named"].append(value)
        elif p >= PLAUSIBLE:
            entry["maybe"].append((value, p))
    for e in dims.values():
        e["unsure"] = [v for v, p in e["maybe"] if p >= (LEAN if e["named"] else PLAUSIBLE)]
    for dim, e in dims.items():
        name = dim.split("__")[-1]
        mode, p_mode = _pick(answers, f"mode:{dim}")
        mode = mode or "none"                    # no answer: the request did not ask about it
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
            filters[dim] = e["named"]
            decisions.append({**_decision("filter", _shown(dim, e["named"]), "question"), "confidence": p_mode})
        elif mode == "except":
            # One reading: everything but the named values, as ONE filter (an IN list), because "not
            # Android" asks for one number. Values named to include are each their own reading.
            filters[dim] = [[m for m in e["members"] if m not in e["named"]]]
            decisions.append({**_decision("filter", _shown(dim, filters[dim]), "question",
                                          why=f"the question asks for every {name} except "
                                              f"{', '.join(map(str, e['named']))}: this filter IS that, one figure"),
                              "confidence": p_mode})

    shape, p_shape = _pick(answers, "shape")
    group_by, separate = [], False
    if shape == "cause" and p_shape >= CONFIDENT:
        # A governed metric reports what happened, not why; the layer holds no causal evidence.
        decisions.append({**_refuse("group_by", "no_causal_evidence",
                                    "the question asks why something happened, and the governed layer "
                                    "holds no causal evidence"), "confidence": p_shape})
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
    elif shape == "trend":
        group_by = ["metric_time"]
        decisions.append({**_decision("group_by", group_by, "question"), "confidence": p_shape})

    said = {p: _yes(answers, f"period:{p}") for _, (k, p) in back.items() if k == "period"}
    periods = _settle([p for p, v in said.items() if v >= CONFIDENT])
    unsure = [p for p, v in said.items() if (LEAN if periods else PLAUSIBLE) <= v < CONFIDENT
              and not any(_within(_period_span(q), [_period_span(p)]) or _within(_period_span(p), [_period_span(q)])
                          for q in periods)]
    if not periods and _yes(answers, "outside") >= CONFIDENT:
        decisions.append(_refuse("period", "out_of_coverage", f"the period asked about is outside the data ({lo} to {hi})"))
    elif unsure:
        decisions.append(_ungrounded("period", f"unsure whether the question includes {', '.join(unsure)}"))
    elif not periods:
        decisions.append(_ungrounded("period", "the question states no period that can be placed on the "
                                     "calendar, and no rule supplies one"))
    else:
        decisions.append(_decision("period", " or ".join(periods), "question"))

    grain, p_grain = _pick(answers, "time_grain")
    return {"filters": filters, "periods": periods, "group_by": group_by, "separate": separate,
            "values": {dim: e["members"] for dim, e in dims.items()},
            "period_options": [p for _, (k, p) in back.items() if k == "period"],
            "grain": grain if grain not in (None, "not_mentioned") and p_grain >= CONFIDENT else None,
            "rule": next((r for r in principles if r.get("slot") == "time_grain"), None),
            "builtin": builtin, "decisions": decisions}


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
        if dim in filters or dim in group_by or dim in (requested.get("filters") or {}):
            continue
        if len(allowed) == 1 and allowed[0] is not None:
            filters[dim] = allowed[0]
        else:
            fan.append((dim, allowed))
    may_split = set(reading["group_by"]) | {d for d, a in reading["filters"].items() if len(a) > 1} | {"metric_time"}
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
    surface = surface_for(semantic, cursor, metric)
    lo, hi = (semantic.coverage_window(metric) if hasattr(semantic, "coverage_window") else (None, None))
    if surface is None or not lo or not hi:
        return None, 0.0
    principles = list((governance or {}).get("methodological_rules") or [])
    questions, back = _questions(surface, principles, lo, hi)
    answers, cost, model = _ask(questions, question)
    # The raw answers and the serving version are kept with the reading, so a stored row can be
    # replayed and the reading evaluated as a component without a new request.
    cache[metric] = {**read(answers, surface, principles, back, lo, hi), "answers": answers, "model": model}
    return cache[metric], cost


# ── the question as a whole: which fork word it uses, and whether it asks to bend the rules ───────

def question_questions(vocabulary: dict[str, tuple[str, ...]]) -> tuple[dict, dict]:
    """The question-level request. Two things are properties of the question, not of any metric:

      term          which declared fork word it uses ("users", "marketing spend"), or a metric named
                    directly, or none. A fork is a fact about a word, so routing applies only when
                    the question uses that word (guardrails/forks.py).
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
    from .forks import vocabulary
    questions, back = question_questions(vocabulary(semantic))
    answers, cost, model = _ask(questions, question)
    cache["_question"] = {**read_question(answers, back), "answers": answers, "model": model}
    return cache["_question"], cost


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
    lines += [f"  - not filtered: every other dimension. Filtering or splitting by one the question "
              f"does not name will not run."]
    lines += [f"  - {d['parameter']}: {d['disclose']}" for d in reading["decisions"]
              if d["state"] == "applied" and d.get("disclose")]
    if refusals:
        lines += [f"  - REFUSE ({d['reason']}): {d['why']}. No governed number answers the question; do "
                  f"not offer another value's figure or a mapping." for d in refusals]
    if open_:
        lines += [f"  - OPEN {d['parameter']}: {d['why']}. Ask the user with `clarify`, offering governed "
                  f"values." for d in open_]
    return "\n".join(lines)


def choose_metric(question: str, metrics: dict) -> dict:
    """Which governed metric the question asks for, read by the decision model from the catalogue:
    {choice, p, probabilities, cost, model}. `not_in_list` and `not_mentioned` are returned as such."""
    answers, cost, model = _ask(_metric_questions(metrics), question)
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

def _metric_questions(metrics: dict) -> dict:
    crit = {name: f"{name}: {' '.join((m.get('description') or '').split())[:260]}"
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
    answers, cost, _model = _ask(_metric_questions(metrics), question)
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
