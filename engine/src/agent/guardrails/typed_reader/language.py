"""The typed reader's requests to language models: the proposal, the suggestions, the confirmation.

The proposal model marks what each phrase of the question does. It is shown nothing about the layer
and is taught with examples from an unrelated domain (a bakery), so its output depends on the
question alone. The decision model (`decisions._ask`) answers yes/no and choice questions that code
builds from the resolved reading. Wording measured in experiment 07's spike
(03_typed_reader/spike.py, findings section 29): 44 of 45 proposals correct with `gpt-5.4-mini`, no
error passing both checks, no false asks.
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
    ("How did non-organic cake sales change in 2025?",
     {"figures": [{"terms": [{"quote": "organic", "keep": False}]}], "time": [{"quote": "2025", "value": "2025"}],
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
    return {"model": MODEL_SPECS[model].openrouter_id, "temperature": 0, "messages": messages, "tools": [TOOL],
            "tool_choice": {"type": "function", "function": {"name": "mark_question"}}}


def propose(request: dict) -> tuple[dict, float]:
    """(proposal, cost in USD). Raises ReadingUnavailable after three failed attempts; a missing key is
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
            return json.loads(call), cost
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403, 404):
                raise
            err: Exception = exc
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, IndexError) as exc:
            err = exc
        time.sleep(3 * (attempt + 1))
    raise ReadingUnavailable(f"proposal model unavailable: {type(err).__name__}")


def _yn(text: str) -> dict:
    return {"type": "noul", "instructions": text, "criteria": {"true": "Yes.", "false": "No."}}


def suggestion_questions(unresolved: list, surface: dict) -> dict:
    """One choice per phrase no list holds: which listed value it is the same thing as, a value of a
    dimension the layer does not have, or something else (design section 6)."""
    out = {}
    for i, quote in enumerate(unresolved):
        criteria = {}
        for d in _dimensions(surface):
            label = d["column"].replace("_", " ")
            for m in d["members"]:
                if str(m).lower() not in ("true", "false"):
                    criteria[f"value:{d['name']}={m}"] = f"\"{quote}\" is the same thing as the {label} {m}."
            criteria[f"absent:{d['name']}"] = (f"\"{quote}\" is a {label}, but none of these: "
                                               f"{', '.join(map(str, d['members']))}.")
        criteria["other"] = f"\"{quote}\" is something else, or it is not clear what it is."
        out[f"sug{i}"] = {"type": "choice", "criteria": criteria,
                          "instructions": f"In the question, what is \"{quote}\"?"}
    return out


def confirmation_questions(proposal: dict, terms: list, periods: list) -> tuple[dict, dict]:
    """(questions, flag rule per key): 'low' flags below 0.7, 'high' flags at 0.7 or above. One
    question per judgement the proposal made, plus one per phrase whose resolved value leaves words
    over ("Google Android phones") or was corrected from a misspelling."""
    qs, rule, parts = {}, {}, []
    figures = proposal.get("figures") or []
    for i, f in enumerate(figures):
        fterms = f.get("terms") or []
        # One question per figure, not per term: "restricted to Android?" scored 0.09 for "Android and
        # iOS together", because the question means both (spike, 2026-10-09).
        keep = [t["quote"] for t in fterms if t["keep"]]
        drop = [t["quote"] for t in fterms if not t["keep"]]
        text = ("restrict what is counted to " + " and ".join(keep) if keep else "count everything") + \
               (" except " + " and ".join(drop) if drop else "")
        qs[f"fig{i}"], rule[f"fig{i}"] = _yn(f"Does the question {text}?"), "low"
        if len(fterms) > 1:
            qs[f"group{i}"] = _yn("Does the question ask for " + " and ".join(t["quote"] for t in fterms)
                                  + " combined into one number?")
            rule[f"group{i}"] = "low"
        parts.append(" and ".join(("not " if not t["keep"] else "") + t["quote"] for t in fterms))
    if len(figures) > 1:
        qs["separate"], rule["separate"] = _yn("Does the question ask for separate numbers for "
                                               + " and for ".join(parts) + "?"), "low"
    for i, t in enumerate(x for f in terms for x in f):
        if t.get("values") and (t.get("rest") or t.get("why")):
            named = " and ".join(f"{d.split('__')[-1].replace('_', ' ')} {v}" for d, v in t["values"])
            qs[f"term{i}"], rule[f"term{i}"] = _yn(f"In the question, does \"{t['quote']}\" mean {named}, and "
                                                   f"nothing narrower?"), "low"
    s = proposal.get("series")
    if s:
        qs["shape"] = _yn(f"Does the question ask for one number per {s['unit']}?" if s.get("unit")
                          else "Does the question ask how the number changes over time?")
        rule["shape"] = "low"
    else:
        # Asked about what was NOT marked, flagged only on yes. "...or for one number per day, week,
        # month or other period?" read "in May 2026" as one number for the month and flagged nearly
        # every question (spike run 2); "several numbers" is the distinction that matters.
        qs["shape"] = _yn("Does the question ask for several numbers over time, one for each of several days, "
                          "weeks or months, rather than one number for the whole period?")
        rule["shape"] = "high"
    for i, p in enumerate(periods):
        qs[f"time{i}"], rule[f"time{i}"] = _yn(f"Does the question ask about {readable(p)}?"), "low"
    if not proposal.get("time"):
        qs["anytime"], rule["anytime"] = _yn("Does the question name a period of time?"), "high"
    for i, b in enumerate(proposal.get("breakdown") or []):
        by = b["quote"] if b["quote"].lower().startswith(("by", "per")) else "by " + b["quote"]
        qs[f"by{i}"], rule[f"by{i}"] = _yn(f"Does the question ask to split the number {by}?"), "low"
    reading = "; ".join(filter(None, [
        ("restricted to " + "; separately ".join(parts)) if parts else "no restriction",
        ", ".join(readable(p) for p in periods) or "no period",
        (f"one number per {s['unit']}" if s and s.get("unit") else "a trend over time") if s else "a single total",
        ("split " + ", ".join(b["quote"] for b in proposal.get("breakdown") or [])) if proposal.get("breakdown") else ""]))
    qs["beyond"] = _yn(f"The question has been read as asking for: {reading}. Leaving aside what is being counted "
                       "(the measure itself), does the question also restrict or split it by something this "
                       "reading leaves out?")
    rule["beyond"] = "high"
    return qs, rule
