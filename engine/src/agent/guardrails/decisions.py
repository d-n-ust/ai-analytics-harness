"""Guardrail `decision_grounding` (BEFORE): ground every parameter with one decision-model request.

The same job as `parameter_grounding` (guardrails/parameters.py), with the proposal step replaced.
There, an LLM proposes each value and quotes the phrase behind it, and code checks the quote and maps
the phrase to a member. Here, both happen in one step: a decision model (Jev, on OpenRouter's
Decisions API) is given the question and, for each parameter, the closed list of values the layer
allows, and returns a choice with a probability. Every option list is generated from the layer by
code, so the model can only pick a value that exists:

  each categorical filter   the dimension's members, each with its layer description,
                            plus `not_mentioned` and `not_in_list`
  shape                     total / breakdown / trend
  breakdown dimension       the dimensions, the governed `canonical_segments` rule, `not_in_list`
  time grain                day / week / month / `not_mentioned`
  period                    every month, quarter and half-year inside the metric's coverage,
                            plus `not_mentioned` and `outside_coverage`

The policy is unchanged and is applied by code: a confident member proceeds; `not_in_list` and
`outside_coverage` refuse; a needed value that is `not_mentioned`, or any choice below the confidence
threshold, asks. Rules (canonical_segments, trend_granularity) are applied by code, as before.

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
from .parameters import _decision, _trend_grain, _ungrounded, surface_for

__all__ = ["ground", "CONFIDENT", "MODEL"]

MODEL = "~typesafe/jev-latest"
# Act on a choice only at or above this probability; below it, ask. 0.7 is where the 120-decision
# fair test (2026-10-03) had no wrong decision left; it is a starting point, not a tuned value.
CONFIDENT = 0.7
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
    """The Decisions request, and for each filter question the map from option key to member."""
    questions, members = {}, {}
    for d in _dimensions(surface):
        label = d["column"].replace("_", " ")
        crit, back = {}, {}
        for m in d["members"]:
            key = str(m).lower()
            back[key] = m
            clause = _clause(m, d["description"])
            crit[key] = f"The question restricts the result to {label} = {m}." + (f" ({clause})" if clause else "")
        crit["not_mentioned"] = f"The question does not restrict the {label} at all."
        crit["not_in_list"] = f"The question restricts the {label} to a value that is not one of the listed options."
        questions[f"filter:{d['name']}"] = {
            "type": "choice", "criteria": crit,
            "instructions": f"Which {label} value does the question restrict the result to? "
                            f"Layer description of {label}: {d['description']}"}
        members[f"filter:{d['name']}"] = back
    questions["shape"] = {"type": "choice", "instructions": "What shape of answer does the question ask for?",
                          "criteria": {"total": "A single number.",
                                       "breakdown": "The number split by a category.",
                                       "trend": "How the number changes over time."}}
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
    crit = dict(_periods(lo, hi))
    crit["not_mentioned"] = ("The question states no time period, or one too vague to place on the "
                             "calendar (for example a season without a year).")
    crit["outside_coverage"] = f"The question names a period outside the data, which covers {lo} to {hi}."
    questions["period"] = {"type": "choice", "criteria": crit,
                           "instructions": "Which calendar period does the question ask about?"}
    return questions, members


# ── the request ───────────────────────────────────────────────────────────────────────────────

def _ask(questions: dict, state: str) -> tuple[dict, float]:
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
    return r["answers"], float((r.get("usage") or {}).get("cost") or 0.0)


# ── the policy, applied by code ───────────────────────────────────────────────────────────────

def _refuse(parameter: str, reason: str, why: str) -> dict:
    return {**_decision(parameter, "?", "none", state="refuse", why=why), "reason": reason}


def resolve(answers: dict, surface: dict, principles: list, members: dict, requested: dict,
            lo: dt.date, hi: dt.date) -> tuple[list, list]:
    """PURE. The queries to run and the decision record, from the decision model's answers."""
    by_id = {p["id"]: p for p in principles}
    decisions, filters = [], {}
    if surface.get("filter"):
        decisions.append(_decision("metric_filter", surface["filter"], "governed_declaration",
                                   disclose=f"{surface['metric']} applies {surface['filter']} by definition.",
                                   why="declared by the metric; not selectable"))

    def pick(name):
        a = answers.get(name) or {}
        choice = a.get("choice")
        return choice, (a.get("probabilities") or {}).get(choice, 0.0)

    for name, back in members.items():
        dim = name.split(":", 1)[1]
        choice, p = pick(name)
        if choice in (None, "not_mentioned"):
            continue
        if p < CONFIDENT:
            decisions.append({**_ungrounded("filter", f"{dim}: unsure ({choice}, p {p:.2f})"), "confidence": p})
        elif choice == "not_in_list":
            decisions.append({**_refuse("filter", "ungoverned_dimension_value",
                                        f"the question names a {dim} value the layer does not have"),
                              "confidence": p})
        else:
            member = back[choice]
            value = f"{dim} = {member}"
            if surface.get("filter") and value.lower() == surface["filter"].lower():
                decisions.append({**_decision("filter", value, "none", state="dropped",
                                              why="the metric already applies this filter"), "confidence": p})
                continue
            filters[dim] = member
            decisions.append({**_decision("filter", value, "question"), "confidence": p})

    shape, p_shape = pick("shape")
    group_by, separate, time_grain = [], False, None
    if p_shape < CONFIDENT:
        decisions.append({**_ungrounded("group_by", f"shape: unsure ({shape}, p {p_shape:.2f})"),
                          "confidence": p_shape})
    elif shape == "breakdown":
        dim, p = pick("breakdown")
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

    period, p_period = pick("period")
    if p_period < CONFIDENT:
        decisions.append({**_ungrounded("period", f"unsure ({period}, p {p_period:.2f})"), "confidence": p_period})
        period = None
    elif period == "outside_coverage":
        decisions.append({**_refuse("period", "out_of_coverage",
                                    f"the period asked about is outside the data ({lo} to {hi})"),
                          "confidence": p_period})
        period = None
    elif period == "not_mentioned":
        decisions.append({**_ungrounded("period", "the question states no period that can be placed on "
                                        "the calendar, and no rule supplies one"), "confidence": p_period})
        period = None
    else:
        decisions.append({**_decision("period", period, "question"), "confidence": p_period})

    if "metric_time" in group_by:
        grain, p = pick("time_grain")
        rule = next((r for r in principles if r.get("slot") == "time_grain"), None)
        if grain not in (None, "not_mentioned") and p >= CONFIDENT:
            time_grain = grain
            decisions.append({**_decision("time_grain", grain, "question"), "confidence": p})
        elif rule and period and _trend_grain(rule, period):
            time_grain, _points, _days, disclose = _trend_grain(rule, period)
            decisions.append(_decision("time_grain", time_grain, "governed_principle",
                                       disclose=disclose, why=f"principle {rule['id']}"))
        else:
            decisions.append(_ungrounded("time_grain", "a time series is asked for, but neither the question "
                                         "nor a rule gives its granularity"))

    if any(d["state"] in ("refuse", "ungrounded") for d in decisions):
        return [], decisions
    args = {"metric": requested["metric"], **({"filters": filters} if filters else {}),
            **({"group_by": group_by} if group_by else {}), **({"time_grain": time_grain} if time_grain else {}),
            **({"period": period} if period else {})}
    if separate and len(group_by) > 1:
        return [{**args, "group_by": [d]} for d in group_by], decisions
    return [args], decisions


def ground(question: str, requested: dict, semantic, cursor, governance: dict | None,
           cache: dict) -> tuple[list, list, float]:
    """The grounded queries, the decision record, and the decision request's cost in USD (0.0 from
    the cache). When no surface or coverage can be read, the agent's own call stands."""
    metric = requested.get("metric", "")
    if metric in cache:
        return (*cache[metric], 0.0)
    surface = surface_for(semantic, cursor, metric)
    lo, hi = (semantic.coverage_window(metric) if hasattr(semantic, "coverage_window") else (None, None))
    if surface is None or not lo or not hi:
        return [requested], [], 0.0
    principles = list((governance or {}).get("methodological_rules") or [])
    questions, members = _questions(surface, principles, lo, hi)
    answers, cost = _ask(questions, question)
    queries, decisions = resolve(answers, surface, principles, members, requested, lo, hi)
    cache[metric] = (queries, decisions)
    return queries, decisions, cost
