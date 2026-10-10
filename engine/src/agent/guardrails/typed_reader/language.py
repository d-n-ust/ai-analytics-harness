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
                    criteria[f"part:{d['name']}={m}"] = (f"\"{quote}\" is one kind of {named}, narrower than it: "
                                                         f"{m} also holds other things.")
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


def described(reading: dict, metric: str) -> str:
    """The resolved reading as one plain sentence, built by code from the values that would run."""
    figures = reading.get("figures") or []
    what = ("separately for " + ", and for ".join(figures) if len(figures) > 1
            else f"for {figures[0]}" if figures else "with no restriction")
    # The period as asked: the covered part of a partly covered one is stated to the user separately,
    # and "1 June to 12 July 2026" read against "summer 2026" was not confirmed (development, 2026-10-10).
    when = " and ".join(readable(p) for p in reading.get("asked_periods") or reading["periods"]) or "no period"
    shape = []
    if "metric_time" in reading["group_by"]:
        shape.append(f"one number per {reading['grain']}" if reading.get("grain") else "as a trend over time")
    if reading.get("splits"):
        shape.append("split by " + " and by ".join(reading["splits"]))
    return (f"the number of {metric.replace('_', ' ')} {what}, in {when}, "
            + (" and ".join(shape) if shape else "as one number for the whole period") + ".")


def roundtrip_question(reading: dict, metric: str) -> dict:
    """One yes/no question: does the reading, written back as a sentence, ask for exactly what the
    question asks? It replaces one question per judgement (spike and first sealed run), where every
    extra part was one more chance of a false "no": 53 of 216 readings asked without need."""
    # Wording chosen on 14 development readings (8 correct, 6 wrong): this one passed 7 and flagged all
    # 6, the wrong ones at 0.32 or less; "Does this ask for exactly what the question asks..." flagged
    # a correct exclusion at 0.66 and passed nothing wrong below 0.54 (findings section 32).
    return {"roundtrip": _yn(
        f"Is this an accurate description of what the question asks for: {described(reading, metric)} Answer "
        "no if it leaves out, adds or changes a restriction, a period, a comparison or a split. Staff and test "
        "accounts are always excluded; ignore that.")}
