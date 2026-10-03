"""Guardrail `parameter_grounding` (BEFORE): ground every parameter of a governed query.

A governed metric settles one decision, which measure to use. The query that produces the number
also decides its filters, group-by dimensions, time grain and period, and the layer governs few of
them. This guardrail runs when the agent calls `query_metric`. It keeps the agent's METRIC and
re-derives every other parameter from the question, so that each value has a basis:

  question              the question states it ("Android users" -> platform = android)
  governed_declaration  the metric applies it by definition (app_opens: is_internal = false)
  governed_principle    a declared rule fills a gap the question leaves open (trend_granularity)

The basis decides the action, and this is the policy the guardrail enforces:

  question              proceed; the reader already knows the value
  declaration, rule     proceed, and disclose the declaration or rule in the answer
  none                  do not run the query; ask the user (clarify `underspecified_request`)

A value the question did not ask for is not a decision the question needs, so it is dropped rather
than asked about. A value the question names but the layer does not have (TikTok as a channel) is
not ungrounded either: the query runs with it, matches nothing, and the agent refuses.

The division of labour follows `grounding_check.py`. The MODEL maps the question's words onto the
metric's parameter surface by meaning, reading the dimension descriptions; that is semantic work,
where a phrase table is brittle. The MECHANISM checks what can be checked without judgement: that
the dimension exists (an enum), that the quoted basis is in the question, that the layer's own text
licenses the member for that phrase (`core.members.licenses`: world knowledge may propose, only
documentation may license), and it applies a named principle's governed value itself, so the model
cannot reproduce it partially.

One model call per metric per run; the result is cached on the run, so repeated calls to the same
metric are grounded identically.

Two optional variants of the evidence check, each its own guardrail flag so each can be measured
alone:

  tolerant_quotes   the quoted phrase matches the question by word stem, allows up to two
                    intervening words, a shared prefix of three letters or more ("Jun" / "June") and
                    one typo in a word of five letters or more ("Andriod" / "Android").
  quote_retry       a quote that is not in the question is sent back to the model once, with the
                    error. If it is still not in the question, the parameter is treated as
                    ungrounded and the agent must ask, instead of the value being dropped silently.

Known limit: every call to a metric is grounded against the WHOLE question. A question that needs
the same metric twice with different parameters (this month against last month) is grounded to one
reading. None of the experiment 07 suite asks that; a run that needs it should not use this flag.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from ontology import parameters as _surface

from ..core.conversation import Conversation, Usage
from ..core.measure import _additivity
from ..core.members import licenses

__all__ = ["ground", "surface_for", "note_text"]

_SYSTEM = """You are an experienced analyst constructing ONE governed query. The metric is already
chosen. Map the question onto the metric's parameters using your own judgment, guided by these
principles, not by fixed word patterns:

1. Answer exactly what is asked, at the grain it asks for. Represent every part of the request, and
   add nothing it did not ask for. Do not add a filter the metric already applies.
2. Structure follows the OPERATION, not the phrasing: seeing something "by <dimension>" is a
   grouping; how something "changed over time" is a time series (group_by metric_time); a plain
   amount is a single value.
3. Use only dimensions that exist (the tool enforces this). Read the descriptions to map any
   phrasing ("by market", "by geography") onto the right dimension and member.
4. When the question leaves a choice open, NAME the governed principle that fills it (do not
   reproduce its values yourself). If the answer depends on the choice and no principle applies,
   list the parameter under `ungrounded` with the reason. Never fill it with a guess.
5. A value the question NAMES but no member matches (a channel, platform or country the layer does
   not have) is not ungrounded: the question is clear, the layer lacks it. Record it as a filter
   with the phrase as the member; the protocol checks it and the agent will decline.
6. Prefer the simplest query that answers the question.

For each choice, `basis` is the exact phrase from the question you mapped, copied verbatim, or
'none'. `disclose` is one plain sentence stating the choice."""


def surface_for(semantic, cursor, metric: str) -> dict | None:
    """The metric's parameter surface, read from the layer the agent is querying. None when the
    layer does not expose its source directory (only the MetricFlow adapter does), so the guardrail
    stands down rather than grounding against a different layer."""
    spec_dir = getattr(semantic, "spec_dir", None)
    if spec_dir is None:
        return None
    text = "\n---\n".join(p.read_text() for p in sorted(Path(spec_dir).glob("*.y*ml")))
    try:
        return _surface.build(cursor, text, metric)
    except (KeyError, ValueError):
        return None


def _tool(surface: dict, principles: list) -> dict:
    dims = [d["name"] for d in surface["parameters"]["filters"]["dimensions"]]
    basis = {"type": "string", "description": "the question phrase you mapped, verbatim, or 'none'"}
    disclose = {"type": "string", "description": "one plain sentence stating the choice"}

    def named(slot):
        return ["none"] + [p["id"] for p in principles if p.get("slot") == slot]
    return {
        "name": "select_parameters",
        "description": "Select the query parameters by mapping the question onto the metric's parameters.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filters": {"type": "array", "items": {"type": "object", "properties": {
                    "dimension": {"type": "string", "enum": dims},
                    "member": {"type": "string"}, "basis": basis, "disclose": disclose},
                    "required": ["dimension", "member", "basis"]}},
                "group_by": {"type": "object", "properties": {
                    "dimensions": {"type": "array", "items": {"type": "string",
                                                              "enum": dims + ["metric_time"]}},
                    "principle": {"type": "string", "enum": named("group_by"),
                                  "description": "name a principle if the breakdown is unspecified; else 'none'"},
                    "basis": basis, "disclose": disclose}},
                "time_grain": {"type": "object", "properties": {
                    "value": {"type": "string", "enum": [*_surface.TIME_GRAINS, "none"]},
                    "principle": {"type": "string", "enum": named("time_grain"),
                                  "description": "name a principle if a trend has no stated bucket; else 'none'"},
                    "basis": basis, "disclose": disclose}},
                "period": {"type": "object", "properties": {
                    "value": {"type": "string",
                              "description": "YYYY-MM, YYYY-Qn or YYYY-Hn; 'current' when the question "
                                             "asks for the value now; empty when nothing states it"},
                    "basis": basis, "disclose": disclose}},
                "ungrounded": {"type": "array", "description": (
                    "Parameters the answer depends on that neither the question states nor a "
                    "principle settles. Listing one stops the query and asks the user."),
                    "items": {"type": "object", "properties": {
                        "parameter": {"type": "string",
                                      "enum": ["filter", "group_by", "time_grain", "period"]},
                        "why": {"type": "string"}}, "required": ["parameter", "why"]}},
            },
            "required": ["filters", "period"],
        },
    }


def _surface_text(surface: dict, principles: list) -> str:
    lines = [f"METRIC: {surface['metric']}: {surface['description']} "
             f"(additivity: {_additivity(surface['agg'] or '')})"]
    if surface.get("filter"):
        lines.append(f"The metric already applies: {surface['filter']}")
    lines.append("Dimensions (filter or group_by), with descriptions and members:")
    for d in surface["parameters"]["filters"]["dimensions"]:
        members = ", ".join(map(str, d["members"])) if d["members"] else "(open)"
        lines.append(f"  {d['name']} [{members}]: {d['description']}")
    lines.append("Governed principles you may NAME when a choice is left open "
                 "(you name it; the protocol fills its value):")
    lines += [f"  - {p['id']} ({p['slot']}): {p.get('when', '')}" for p in principles]
    return "\n".join(lines)


def _select(model, question: str, surface: dict, principles: list,
            feedback: str = "") -> tuple[dict, Usage]:
    tool = _tool(surface, principles)
    user = f"{_surface_text(surface, principles)}\n\nQUESTION: {question}\n\nCall select_parameters."
    if feedback:
        user += ("\n\nYOUR PREVIOUS SELECTION QUOTED EVIDENCE THAT IS NOT IN THE QUESTION:\n" + feedback
                 + "\nFor each, quote the exact words of the question that support the value, or "
                   "use 'none' if the question does not ask for it.")
    turn = model.respond(Conversation.opening(_SYSTEM, user), [tool],
                         force_tool=tool["name"], temperature=0)
    args = next((c.args for c in turn.tool_calls if c.name == tool["name"]), {})
    return args, turn.usage


# ── the mechanism: checks and principle application, no model ─────────────────────────────────

def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", str(text or "").lower())


def _in_question(basis: str, question: str, tolerant: bool = False) -> bool:
    """Is the quoted basis actually in the question? Word-level, so punctuation and case never
    matter. Exact by default: the quote's words, consecutively. With `tolerant` (the
    `tolerant_quotes` variant) each word may match by stem, prefix or one typo, and up to two
    question words may sit between consecutive quote words."""
    quoted = _words(basis)
    if not quoted or quoted == ["none"]:
        return False
    asked = _words(question)
    if not tolerant:
        n = len(quoted)
        return any(asked[i:i + n] == quoted for i in range(len(asked) - n + 1))
    return any(_follows(quoted, asked, i) for i in range(len(asked)))


_MAX_GAP = 2      # question words allowed between two consecutive quote words


def _follows(quoted: list, asked: list, start: int) -> bool:
    """`quoted` matches `asked` beginning exactly at `start`, each later word within the gap."""
    if not _word_match(quoted[0], asked[start]):
        return False
    if len(quoted) == 1:
        return True
    return any(_follows(quoted[1:], asked, j)
               for j in range(start + 1, min(start + 2 + _MAX_GAP, len(asked))))


def _stem(w: str) -> str:
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if w.endswith(("sses", "xes", "ches", "shes")):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _one_edit(a: str, b: str) -> bool:
    """At most one substitution, insertion, deletion or swap of adjacent letters."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        return len(diff) <= 1 or (len(diff) == 2 and diff[1] == diff[0] + 1
                                  and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]])
    short, long_ = sorted((a, b), key=len)
    return any(long_[:i] + long_[i + 1:] == short for i in range(len(long_)))


def _word_match(q: str, a: str) -> bool:
    if q == a or _stem(q) == _stem(a):
        return True
    if not (q.isalpha() and a.isalpha()):
        return False                      # numbers match exactly or not at all: 2026 is not 2025
    short = min(len(q), len(a))
    if short >= 3 and (a.startswith(q) or q.startswith(a)):
        return True
    return short >= 5 and _one_edit(q, a)


def _period_span(value: str):
    m = re.match(r"(\d{4})-(H[12]|Q[1-4]|\d{2})$", value or "", re.I)
    if not m:
        return None
    year, tag = int(m.group(1)), m.group(2).upper()
    if tag.startswith("H"):
        return (dt.date(year, 1, 1), dt.date(year, 6, 30)) if tag == "H1" else \
               (dt.date(year, 7, 1), dt.date(year, 12, 31))
    if tag.startswith("Q"):
        first = (int(tag[1]) - 1) * 3 + 1
        end = dt.date(year, 12, 31) if first == 10 else dt.date(year, first + 3, 1) - dt.timedelta(days=1)
        return dt.date(year, first, 1), end
    month = int(tag)
    return dt.date(year, month, 1), dt.date(year + month // 12, month % 12 + 1, 1) - dt.timedelta(days=1)


def _lines_up(grain: str, start: dt.date, end: dt.date) -> bool:
    """Does every bucket of `grain` lie wholly inside [start, end]? Weeks start on Monday, as the
    engine buckets them (date_trunc('week'))."""
    after = end + dt.timedelta(days=1)
    if grain == "week":
        return start.weekday() == 0 and after.weekday() == 0
    if grain == "month":
        return start.day == 1 and after.day == 1
    return True


def _trend_grain(rule: dict, period: str):
    """`trend_granularity`: (grain, points, days, disclosure), or None for an unreadable period.

    The coarsest grain whose number of points falls in the target range. With
    `buckets_within_period`, only grains whose buckets line up with the period are considered, so no
    point reports data from outside the period; among those, the one nearest the range is taken when
    none falls inside it. The disclosure sentence is built here, once, for every caller."""
    span = _period_span(period)
    if not span:
        return None
    days = (span[1] - span[0]).days + 1
    points = {"day": days, "week": round(days / 7), "month": round(days / 30)}
    allowed = [g for g in ("day", "week", "month")
               if not rule.get("buckets_within_period") or _lines_up(g, *span)]
    lo, hi = rule.get("target_points", [15, 40])
    fits = [g for g in allowed if lo <= points[g] <= hi]
    grain = (min(fits, key=lambda g: points[g]) if fits else
             min(allowed, key=lambda g: min(abs(points[g] - lo), abs(points[g] - hi))))
    excluded = [g for g in ("day", "week", "month") if g not in allowed]
    disclose = f"Shown by {grain}: {points[grain]} points over the {days}-day period, the governed trend granularity."
    if excluded:
        disclose += (f" {' and '.join(excluded).capitalize()} buckets were not used because they would "
                     f"cross the period's edges.")
    return grain, points[grain], days, disclose


def _ungrounded(parameter: str, why: str) -> dict:
    return _decision(parameter, "?", "none", state="ungrounded", why=why)


def _decision(parameter, value, basis, quote="", disclose="", state="applied", why=""):
    return {"parameter": parameter, "value": value, "basis": basis, "quote": quote,
            "disclose": disclose, "state": state, "why": why}


def resolve(question: str, surface: dict, principles: list, selected: dict,
            requested: dict, tolerant: bool = False) -> tuple[list, list]:
    """PURE. The queries to run and the decision record, from the model's selection. Usually one
    query; a group_by principle declared `combine: separate` gives one query per dimension. No
    query at all when a parameter the answer needs is ungrounded: the record then says which, and
    the agent must ask. `requested` is the agent's own call; only its metric is kept.

    A value dropped because its quoted evidence is not in the question carries `mismatch: True`
    when the quote is a real phrase (not 'none'): that is the case `quote_retry` sends back."""
    by_id = {p["id"]: p for p in principles}

    def found(basis: str) -> bool:
        return _in_question(basis, question, tolerant)

    def mismatch(basis: str) -> bool:
        return bool(_words(basis)) and _words(basis) != ["none"] and not found(basis)
    dims = {d["name"]: d for d in surface["parameters"]["filters"]["dimensions"]}
    decisions, filters = [], {}

    if surface.get("filter"):
        decisions.append(_decision(
            "metric_filter", surface["filter"], "governed_declaration",
            disclose=f"{surface['metric']} applies {surface['filter']} by definition.",
            why="declared by the metric; not selectable"))
    declared = _words(surface.get("filter") or "")

    for f in selected.get("filters") or []:
        dim, member = f.get("dimension", ""), str(f.get("member", ""))
        value = f"{dim} = {member}"
        if declared and set(_words(value)) <= set(declared):
            decisions.append(_decision("filter", value, "none", f.get("basis", ""), state="dropped",
                                       why="the metric already applies this filter"))
            continue
        if not found(f.get("basis", "")):
            decisions.append({**_decision("filter", value, "none", f.get("basis", ""), state="dropped",
                                          why="the stated basis is not in the question: an unrequested filter"),
                              "mismatch": mismatch(f.get("basis", ""))})
            continue
        state, why = "applied", ""
        members = dims.get(dim, {}).get("members")
        if members:
            # The model's mapping is a proposal. It stands only if the layer licenses the quoted
            # phrase for that member; the model once mapped "TikTok" to `organic`, and the agent
            # served organic's figure as TikTok's. No license at all means the phrase has no
            # referent: the query runs with the phrase itself, so the empty-result warning fires.
            licensed = licenses(f.get("basis", ""), members, dims[dim].get("description", ""), dim)
            if len(licensed) > 1:
                # Several members fit the phrase. The model's pick being one of them does not make
                # it the one the question meant.
                decisions.append(_ungrounded("filter", f"{f['basis']!r} could mean any of "
                                             f"{licensed} in {dim}; the question does not say which"))
                continue
            if member.lower() not in {str(m).lower() for m in licensed}:
                if len(licensed) == 1:
                    why = f"the layer licenses {f['basis']!r} as {licensed[0]!r}, not {member!r}"
                    member = str(licensed[0])
                else:
                    member = f.get("basis", "")
                    state, why = "invalid", (f"no member of {dim} is documented as {member!r}; "
                                             f"its members are {', '.join(map(str, members))}")
                value = f"{dim} = {member}"
        filters[dim] = member
        decisions.append(_decision("filter", value, "question", f.get("basis", ""), f.get("disclose", ""),
                                   state=state, why=why))

    group_by, separate = [], False
    gb = selected.get("group_by") or {}
    rule = by_id.get(gb.get("principle", "none"), {})
    if rule.get("slot") == "group_by":
        # A dimension the question already fixes to one member would group into a single row.
        group_by = [d for d in rule.get("default", []) if d not in filters]
        separate = rule.get("combine") == "separate"
        decisions.append(_decision("group_by", group_by, "governed_principle", gb.get("basis", ""),
                                   rule.get("disclose", ""), why=f"principle {rule['id']}"))
    elif gb.get("dimensions"):
        if found(gb.get("basis", "")):
            group_by = list(gb["dimensions"])
            decisions.append(_decision("group_by", group_by, "question", gb.get("basis", ""),
                                       gb.get("disclose", "")))
        else:
            decisions.append({**_decision("group_by", gb["dimensions"], "none", gb.get("basis", ""),
                                          state="dropped", why="the stated basis is not in the question"),
                              "mismatch": mismatch(gb.get("basis", ""))})

    period_sel = selected.get("period") or {}
    period = period_sel.get("value") or ""
    grounded_period = found(period_sel.get("basis", ""))
    if (_period_span(period) or period == "current") and grounded_period:
        decisions.append(_decision("period", period, "question", period_sel.get("basis", ""),
                                   period_sel.get("disclose", "")))
        period = "" if period == "current" else period       # omitted period = the current value
    else:
        stated = (_period_span(period) or period == "current") and mismatch(period_sel.get("basis", ""))
        period = ""
        decisions.append({**_ungrounded("period", "the question states no period that can be read "
                                        "as a calendar range, and no rule supplies one"),
                          "mismatch": stated, "value_proposed": period_sel.get("value"),
                          "quote": period_sel.get("basis", "")})

    time_grain = None
    tg = selected.get("time_grain") or {}
    trule = by_id.get(tg.get("principle", "none"), {})
    if "metric_time" in group_by:
        if trule.get("slot") == "time_grain" and period and _trend_grain(trule, period):
            time_grain, _points, _days, disclose = _trend_grain(trule, period)
            decisions.append(_decision("time_grain", time_grain, "governed_principle", tg.get("basis", ""),
                                       disclose, why=f"principle {trule['id']}"))
        elif tg.get("value") in _surface.TIME_GRAINS and found(tg.get("basis", "")):
            time_grain = tg["value"]
            decisions.append(_decision("time_grain", time_grain, "question", tg.get("basis", ""),
                                       tg.get("disclose", "")))
        else:
            decisions.append(_ungrounded("time_grain", "a time series is asked for, but neither the "
                                         "question nor a rule gives its granularity"))

    declared = {d["parameter"] for d in decisions if d["state"] == "ungrounded"}
    for u in selected.get("ungrounded") or ():
        if u.get("parameter") not in declared:
            decisions.append(_ungrounded(u.get("parameter", "?"), u.get("why", "")))
            declared.add(u.get("parameter"))
    if declared:
        return [], decisions

    args = {"metric": requested["metric"]}
    if filters:
        args["filters"] = filters
    if group_by:
        args["group_by"] = group_by
    if time_grain:
        args["time_grain"] = time_grain
    if period:
        args["period"] = period
    if separate and len(group_by) > 1:
        return [{**args, "group_by": [d]} for d in group_by], decisions
    return [args], decisions


def note_text(decisions: list) -> str:
    """What the agent reads. When a needed parameter is ungrounded, the block says the query did
    not run and asks for a clarification. Otherwise it lists the parameters the query ran with and
    marks for disclosure the ones a reader would not otherwise know were chosen: those grounded in a
    declaration or a rule."""
    refused = [d for d in decisions if d["state"] == "refuse"]
    if refused:
        lines = ["[parameter grounding] The query did NOT run. The question names something the layer "
                 "does not have, so no governed number exists. Decline with `refuse`, using the reason "
                 "below; do not answer from a neighbouring value."]
        lines += [f"  - REFUSE ({d['reason']}): {d['why']}" for d in refused]
        return "\n".join(lines)
    missing = [d for d in decisions if d["state"] == "ungrounded"]
    if missing:
        lines = ["[parameter grounding] The query did NOT run. The answer depends on a parameter "
                 "that neither the question nor a governed rule settles. Do not assume a value: "
                 "ask the user with `clarify`, naming what is missing."]
        lines += [f"  - UNGROUNDED {d['parameter']}: {d['why']}" for d in missing]
        return "\n".join(lines)
    lines = ["[parameter grounding] This query ran with the parameters below. State each line "
             "marked DISCLOSE in your answer, in plain words."]
    for d in decisions:
        if d["state"] == "dropped":
            lines.append(f"  - not applied: {d['parameter']} {d['value']} ({d['why']})")
            continue
        mark = "DISCLOSE: " if d["basis"] != "question" or d["state"] == "invalid" else ""
        source = (f"\"{d['quote']}\"" if d.get("quote") else
                  f"decision model, p {d['confidence']:.2f}" if d.get("confidence") is not None else "")
        where = {"question": f"from the question ({source})",
                 "governed_declaration": "declared by the metric",
                 "governed_principle": f"governed principle ({d['why']})",
                 "none": "no basis in the question"}[d["basis"]]
        text = f"  - {mark}{d['parameter']} = {d['value']}: {where}"
        if mark and d["disclose"]:
            text += f". {d['disclose']}"
        if d["state"] == "invalid":
            text += f". {d['why']}"
        lines.append(text)
    return "\n".join(lines)


def ground(model, question: str, requested: dict, semantic, cursor, governance: dict | None,
           cache: dict, tolerant: bool = False, retry: bool = False) -> tuple[list, list, Usage | None]:
    """The grounded queries, the decision record, and the grounding calls' token usage (None when
    the result came from the cache or the guardrail stood down). When no surface can be built, the
    agent's own call stands and the record is empty. `tolerant` is `tolerant_quotes`; `retry` is
    `quote_retry`."""
    metric = requested.get("metric", "")
    if metric in cache:
        return (*cache[metric], None)
    surface = surface_for(semantic, cursor, metric)
    if surface is None:
        return [requested], [], None
    principles = list((governance or {}).get("methodological_rules") or [])
    selected, usage = _select(model, question, surface, principles)
    queries, decisions = resolve(question, surface, principles, selected, requested, tolerant)
    bad = [d for d in decisions if d.get("mismatch")]
    if retry and bad:
        feedback = "\n".join(f"  - {d['parameter']} {d.get('value_proposed', d['value'])}: you quoted "
                              f"{d['quote']!r}" for d in bad)
        selected, again = _select(model, question, surface, principles, feedback)
        usage = usage + again
        queries, decisions = resolve(question, surface, principles, selected, requested, tolerant)
        still = [d for d in decisions if d.get("mismatch")]
        for d in still:
            # A value the model still claims the question asks for, with evidence that is not
            # there. Dropping it would change the number silently, so the agent asks instead.
            d.update(state="ungrounded", basis="none",
                     why=f"the quoted evidence {d['quote']!r} is not in the question, even after one retry")
        if still:
            queries = []
        for d in decisions:
            d["retried"] = True
    cache[metric] = (queries, decisions)
    return queries, decisions, usage
