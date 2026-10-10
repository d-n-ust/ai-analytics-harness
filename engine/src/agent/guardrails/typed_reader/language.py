"""The typed reader's requests to language models: the proposal, the suggestions, the confirmation.

The proposal model marks what each phrase of the question does. It is shown nothing about the layer
and is taught with examples from an unrelated domain (a bakery), so its output depends on the
question alone. The decision model (`decisions._ask`) answers yes/no and choice questions that code
builds from the resolved reading. The proposal wording was measured in experiment 07's spike
(03_typed_reader/spike.py, findings section 29); the round-trip confirmation replaced one question
per judgement after the replication sealed set (findings section 31).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

from ..decisions import ReadingUnavailable, _dimensions
from .resolve import readable

# The proposal model. Not the agent's model; chosen on the spike's 45 development wordings, where it
# matched `gemini-3.8-flash` on errors that pass both checks at a sixteenth of the cost.
PROPOSAL_MODEL = "gpt-5.4-mini"
# A second, independent proposal from another model family (the owner's decision, 2026-10-10). Where
# the two disagree, narrow questions settle each point (`reconcile_questions`), instead of rules written
# to repair one model's misfiled phrases.
SECOND_MODEL = "gemini-3.8-flash"

SYSTEM = """You read a business question and mark what each phrase of it does. You are not told what \
data exists, so do not judge whether a value exists; only say what the question asks.

figures: each separate number the question asks for. A figure lists its terms: phrases that restrict \
what is counted (a product, a place, a channel, a kind of customer), each with keep=true (only these) \
or keep=false (everything except these). Several values asked for as ONE combined number are terms of \
one figure ("croissants and baguettes together"). Values compared against each other are separate \
figures ("croissants vs baguettes"). Copy each quote exactly from the question, without the negation \
word ("non-organic" -> quote "organic", keep false). The thing being counted (the measure itself) and \
time words are not terms. No restriction: an empty list.
time: every period named, with the exact quote and a value: YYYY-MM, YYYY-Qn, YYYY-Hn (half year), \
YYYY, YYYY-SP / YYYY-SU / YYYY-FA / YYYY-WI for seasons, START/END for a range of two such values, \
last_week / last_month / last_quarter / last_year / this_month / this_quarter / this_year / \
year_to_date, or "unplaceable". No period: an empty list.
series: when the question asks for the number over time (a trend, a change, "week by week"), the \
quote and the unit (day, week, month, quarter, year) or null when no unit is stated. Otherwise null.
breakdown: phrases asking to split the number by a category ("by store size").
premise: something the question states as already true ("now that X stopped"), or null."""

EXAMPLES = [
    ("How many croissants did stores outside Paris sell in spring 2025, week by week?",
     {"figures": [{"terms": [{"quote": "Paris", "keep": False}]}], "time": [{"quote": "spring 2025", "value": "2025-SP"}],
      "series": {"quote": "week by week", "unit": "week"}, "breakdown": [], "premise": None}),
    ("Sourdough vs rye sales in Lyon and Nice combined, Q3 2024?",
     {"figures": [{"terms": [{"quote": "Sourdough", "keep": True}, {"quote": "Lyon", "keep": True}, {"quote": "Nice", "keep": True}]},
                  {"terms": [{"quote": "rye", "keep": True}, {"quote": "Lyon", "keep": True}, {"quote": "Nice", "keep": True}]}],
      "time": [{"quote": "Q3 2024", "value": "2024-Q3"}], "series": None, "breakdown": [], "premise": None}),
    ("Compare croissant and baguette sales in Lyon for June 2025.",
     {"figures": [{"terms": [{"quote": "croissant", "keep": True}, {"quote": "Lyon", "keep": True}]},
                  {"terms": [{"quote": "baguette", "keep": True}, {"quote": "Lyon", "keep": True}]}],
      "time": [{"quote": "June 2025", "value": "2025-06"}], "series": None, "breakdown": [], "premise": None}),
    ("Break down bread sales by store size for last month.",
     {"figures": [], "time": [{"quote": "last month", "value": "last_month"}], "series": None,
      "breakdown": [{"quote": "by store size"}], "premise": None}),
    ("Monthly baguette sales in Lyon from March through June 2024",
     {"figures": [{"terms": [{"quote": "baguette", "keep": True}, {"quote": "Lyon", "keep": True}]}],
      "time": [{"quote": "from March through June 2024", "value": "2024-03/2024-06"}],
      "series": {"quote": "Monthly", "unit": "month"}, "breakdown": [], "premise": None}),
    # "cake" is a term: an unmarked product here taught the model to leave "Android" unmarked in
    # "How did Android app opens change" (development run, 2026-10-10).
    ("How did non-organic cake sales change in 2025?",
     {"figures": [{"terms": [{"quote": "cake", "keep": True}, {"quote": "organic", "keep": False}]}],
      "time": [{"quote": "2025", "value": "2025"}],
      "series": {"quote": "change", "unit": None}, "breakdown": [], "premise": None}),
]

_TERM = {"type": "object", "required": ["quote", "keep"],
         "properties": {"quote": {"type": "string"}, "keep": {"type": "boolean"}}}
TOOL = {"type": "function", "function": {
    "name": "mark_question", "description": "The marked question.",
    "parameters": {"type": "object", "required": ["figures", "time", "series", "breakdown", "premise"], "properties": {
        "figures": {"type": "array", "items": {"type": "object", "required": ["terms"], "properties": {
            "terms": {"type": "array", "items": _TERM}}}},
        "time": {"type": "array", "items": {"type": "object", "required": ["quote", "value"], "properties": {
            "quote": {"type": "string"}, "value": {"type": "string"}}}},
        "series": {"type": ["object", "null"], "properties": {"quote": {"type": "string"}, "unit": {"type": ["string", "null"]}}},
        "breakdown": {"type": "array", "items": {"type": "object", "required": ["quote"], "properties": {"quote": {"type": "string"}}}},
        "premise": {"type": ["object", "null"], "properties": {"quote": {"type": "string"}}}}}}}


def proposal_request(question: str, missed: list | None = None, model: str = PROPOSAL_MODEL) -> dict:
    """The chat request that marks the question; with `missed`, the one retry that names the words
    accounting found unmarked."""
    from ...core.models import MODEL_SPECS
    messages = [{"role": "system", "content": SYSTEM}]
    for q, a in EXAMPLES:
        messages += [{"role": "user", "content": q},
                     {"role": "assistant", "content": None, "tool_calls": [{"id": "ex", "type": "function",
                      "function": {"name": "mark_question", "arguments": json.dumps(a)}}]},
                     {"role": "tool", "tool_call_id": "ex", "content": "ok"}]
    messages.append({"role": "user", "content": question})
    if missed:
        messages.append({"role": "user", "content": "These words of the question are not marked: " + ", ".join(missed)
                         + ". If any of them restricts what is counted, names a period, or asks for a split or a "
                           "series, mark it. Then call mark_question again for the same question."})
    # max_tokens bounds the cost of one request; a marked question is a few hundred tokens. Without it
    # the provider reserves its default (65,536) against the account's balance (HTTP 402, 2026-10-10).
    return {"model": MODEL_SPECS[model].openrouter_id, "temperature": 0, "max_tokens": 1500, "messages": messages, "tools": [TOOL],
            "tool_choice": {"type": "function", "function": {"name": "mark_question"}}}


def propose(request: dict) -> tuple[dict, float, str]:
    """(proposal, cost in USD, the model version that served it). Raises ReadingUnavailable after three failed attempts; a missing key is
    a configuration fault and propagates, as in `decisions._ask`."""
    from ...core.models import MODEL_SPECS
    from ...runtime.providers import load_env
    load_env()
    base, key = (os.environ.get("OPEN_ROUTER_BASE_URL") or "").rstrip("/"), os.environ.get("OPEN_ROUTER_API_KEY")
    if not base or not key:
        raise RuntimeError("typed_reader needs OPEN_ROUTER_BASE_URL and OPEN_ROUTER_API_KEY")
    spec = next(s for s in MODEL_SPECS.values() if s.openrouter_id == request["model"])
    req = urllib.request.Request(base + "/chat/completions", data=json.dumps(request).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            r = json.load(urllib.request.urlopen(req, timeout=90))
            call = r["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
            u = r.get("usage") or {}
            cost = (u.get("prompt_tokens", 0) * spec.input_price + u.get("completion_tokens", 0) * spec.output_price) / 1e6
            return json.loads(call), cost, str(r.get("model") or request["model"])
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 402, 403, 404):         # credentials, credit, model: not transient
                raise
            err: Exception = exc
            detail = f"HTTP {exc.code}: {exc.read()[:200].decode(errors='replace')}"
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, IndexError) as exc:
            err, detail = exc, type(exc).__name__
        time.sleep(3 * (attempt + 1))
    raise ReadingUnavailable(f"proposal model unavailable: {detail}")


def _yn(text: str) -> dict:
    return {"type": "noul", "instructions": text, "criteria": {"true": "Yes.", "false": "No."}}


def _twins(surface: dict) -> set:
    """Dimensions that are another dimension under a second name: each value maps to exactly one of
    the other's and back (country and country_name). Their values are offered, but "a value the layer
    does not have" is offered once, for the first: split over two options, neither reached the bar
    and "Japan" was asked about instead of refused."""
    sizes = {d["name"]: len(d["members"]) for d in _dimensions(surface)}
    linked = surface["parameters"]["filters"].get("determines") or {}
    return {b for a, bs in linked.items() for b in (bs or {}) if sizes.get(a) == sizes.get(b)}


def suggestion_questions(unresolved: list, surface: dict) -> dict:
    """One choice per phrase the lists do not settle alone: which listed value it is the same thing as,
    or one narrower kind of; a value of a dimension the layer does not have; or something else (design
    sections 6 and 13)."""
    out, twins = {}, _twins(surface)
    for i, quote in enumerate(unresolved):
        criteria = {}
        for d in _dimensions(surface):
            label = d["column"].replace("_", " ")
            for m in d["members"]:
                if str(m).lower() not in ("true", "false"):
                    # The declared meaning is shown here, where the model compares the phrase with the
                    # value: "the Linux desktop app" against desktop, "the web client".
                    meant = (d.get("meanings") or {}).get(str(m))
                    named = f"the {label} {m}" + (f" ({meant})" if meant else "")
                    criteria[f"value:{d['name']}={m}"] = f"\"{quote}\" is the same thing as {named}."
                    criteria[f"part:{d['name']}={m}"] = (f"\"{quote}\" is narrower than {named}, and {m} is the "
                                                         f"closest {label} that contains it.")
            if d["name"] not in twins:
                # The layer's own first sentence says what the dimension is: "TikTok" was "something
                # else" against "a channel", and is an acquisition channel the layer lacks.
                what = (d.get("description") or "").split(". ")[0].rstrip(".")
                criteria[f"absent:{d['name']}"] = (f"\"{quote}\" is a {label}" + (f" ({what})" if what else "")
                                                   + f", but none of these: {', '.join(map(str, d['members']))}.")
        criteria["other"] = f"\"{quote}\" is something else, or it is not clear what it is."
        out[f"sug{i}"] = {"type": "choice", "criteria": criteria,
                          "instructions": f"In the question, what is \"{quote}\"?"}
    return out


def structure_questions(proposal: dict, reading: dict, terms: list) -> dict:
    """One yes/no per structural judgement the proposal made, each about one item, in the user's words:
    a series, several values of one dimension added together, values compared as separate numbers,
    something left out, several periods. They replace one whole-reading question ("is this an accurate
    description?"), which vetoed 83 right readings for 13 wrong ones across the development runs of
    2026-10-10. On 15 calibration readings each answered on the right side: wrong readings 0.26 or less,
    right ones 0.73 or more (findings section 36). `terms` are the resolved terms per figure, so values
    of different dimensions ("mobile" and "Brazil") are never asked about as one combined number."""
    out = {}
    if "metric_time" in reading["group_by"]:
        out["series"] = _yn("Does the question ask for several numbers over time (a trend, or one number per day, "
                            "week or month), rather than one number for the whole period?")
    for i, figure in enumerate(terms):
        by_dim: dict = {}
        for t in figure:
            if t["keep"]:
                for dim, _v in t["values"][:1]:
                    by_dim.setdefault(dim, []).append(t["quote"])
        for dim, quotes in by_dim.items():
            if len(quotes) > 1 and len(terms) == 1:
                out[f"combined{i}:{dim}"] = _yn(f"Does the question ask for {' and '.join(quotes)} added together as "
                                                "one combined number?")
        for j, t in enumerate(t for t in figure if not t["keep"]):
            out[f"except{i}_{j}"] = _yn(f"Does the question ask for everything except {t['quote']}?")
        # The other direction: a value marked as kept may be one the question leaves out ("all countries
        # with the exception of IN" was marked as IN). Without this, nothing asks.
        for j, t in enumerate(t for t in figure if t["keep"]):
            out[f"include{i}_{j}"] = _yn(f"Does the question ask to include {t['quote']}, rather than to leave "
                                         f"{t['quote']} out?")
    if len(terms) > 1:
        # Only what differs between the figures is named: "Android and iOS", not "Germany and Android ...".
        shared = set.intersection(*({t["quote"].lower() for t in f} for f in terms))
        names = [" and ".join(t["quote"] for t in f if t["keep"] and t["quote"].lower() not in shared) or "the rest"
                 for f in terms]
        out["separate"] = _yn(f"Does the question ask for a separate number for each of {' and '.join(names)}?")
    times = [t["quote"] for t in proposal.get("time") or []]
    if len(times) > 1:
        out["periods"] = _yn(f"Does the question ask about {' and '.join(times)} as separate periods, rather than "
                             "one continuous range?")
    return out


def inner_questions(quote: str, inner: list) -> dict:
    """One yes/no per narrower value the model also found plausible: is the phrase wholly inside it?"""
    return {f"in{i}": _yn(f"Does everything \"{quote}\" refers to fall within the "
                          f"{dim.split('__')[-1].replace('_', ' ')} {value}?") for i, (dim, value) in enumerate(inner)}


def leftover_questions(words: list) -> dict:
    """One yes/no per word of the question that no part of the reading uses: does the word name the
    kind of thing a filter is on? Asked per word, about its category, because asked about the list as a
    whole ("does any of them narrow what is counted?") the model said yes to ordinary words ("Compare",
    "show", "number") at 0.73 to 0.85. Per word, on 14 development readings: unmarked restrictions
    ("Germani", "Samsung", "phone", "smartwatch", "German") 0.82 to 0.93; other words 0.53 or less, most
    0.10 or less."""
    return {f"lw{i}": _yn(f"In this question, does the word \"{w}\" name a place, a device or platform, a product, "
                          "a kind of customer, or an acquisition channel?") for i, w in enumerate(words)}


def kind_questions(quotes: list, surface: dict) -> dict:
    """What kind of thing each phrase is, one narrow yes/no per dimension, in a request of its own. Used
    only to refuse ("Japan" is a country the layer does not have): asked in the same request as the
    value choice, the answers carried noise from it and Japan stayed below the bar."""
    twins = _twins(surface)
    out = {}
    for i, quote in enumerate(quotes):
        for d in _dimensions(surface):
            if d["name"] not in twins and any(str(m).lower() not in ("true", "false") for m in d["members"]):
                what = (d.get("description") or "").split(". ")[0].rstrip(".")
                out[f"kind{i}:{d['name']}"] = _yn(f"In this question, is \"{quote}\" a {d['column'].replace('_', ' ')}"
                                                  + (f" ({what})" if what else "") + "?")
    return out


def reconcile_questions(a: dict, b: dict, surface: dict | None = None) -> dict:
    """One narrow yes/no per point on which two independent proposals disagree (design: self-consistency;
    findings section 37). Each is decided by majority: the two proposals already disagree, so the
    question settles which of two readings the question supports."""
    from .resolve import _tokens, canonical, period_of, term_key
    ca, cb = canonical(a, surface), canonical(b, surface)
    out = {}
    if ca["series"][0] != cb["series"][0]:
        out["series"] = _yn("Does the question ask for several numbers over time (a trend, or one number per day, "
                            "week or month), rather than one number for the whole period?")
    for v in sorted(set(ca["time"]) ^ set(cb["time"])):
        period = period_of(v, {})[0]
        out[f"time:{v}"] = _yn(f"Does the question ask about {readable(period) if period else v}?")
    quotes = {" ".join(_tokens(x["quote"])): x["quote"] for p in (a, b) for x in p.get("breakdown") or []}
    for key in sorted(set(ca["breakdown"]) ^ set(cb["breakdown"])):
        quote = next((q for k, q in quotes.items() if key in k or k in key), key)
        out[f"split:{key}"] = _yn(f"Does the question ask to split the number {quote}?")
    if ca["premise"] != cb["premise"]:
        stated = (a.get("premise") or b.get("premise") or {}).get("quote", "")
        out["premise"] = _yn(f"Does the question state as already true that \"{stated}\"?")
    keep, said = {}, {}
    for p in (a, b):
        for f in p.get("figures") or []:
            for t in f.get("terms") or []:
                k = "|".join(term_key(t, surface))
                keep.setdefault(k, set()).add(t["keep"])
                said.setdefault(k, t["quote"])
    for k, ways in keep.items():
        if len(ways) > 1:
            out[f"include:{k}"] = _yn(f"Does the question ask to include {said[k]}, rather than to leave {said[k]} out?")
    if len(ca["figures"]) != len(cb["figures"]):
        kept = sorted({q for p in (a, b) for f in p.get("figures") or [] for t in f.get("terms") or [] if t["keep"]
                       for q in [t["quote"]]}, key=str.lower)
        out["separate"] = _yn(f"Does the question ask for a separate number for each of {' and '.join(kept)}?")
    return out
