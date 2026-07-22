"""Spec decomposition: does the metric behind the answer match what was asked?

The valid-but-wrong floor is a real, governed metric answering a slightly different
question — active users reported as the user total, value moments as the habit count.
The structural rungs (gate, fence) check that a metric *exists* and is *accessible*;
they never check its *meaning*. This module does.

It compares two structured specs, slot by slot:

  - the ANSWER's spec, read deterministically from the metric that produced the number:
    its governed `entity` and `population` segment (declared in the semantic layer) plus
    the `measure` family (derived from the aggregate) and the `grain` of the call.
  - the QUESTION's spec, produced by an isolated decomposer (`decompose_question`): one
    model call, its own prompt, and NO access to the metric catalog — so it states what
    was *asked*, independent of what we happen to stock. A parser that can see the
    catalog anchors to it ("there's an active_users metric, so that must be the intent")
    and the check turns circular. Share the vocabulary; hide the inventory.

Everything after the decomposer is deterministic and provable without a model call
(see tests/test_semantic.py). The check is refuse-only: a mismatch turns an answer into
a refusal, it can never turn a refusal into an answer, so it can only add safety.

The four slots are the lowest common denominator of every semantic layer — MetricFlow
entities, Cube segments, measures, dimensions:
    entity      the thing one unit counts (users, subscriptions, value_moments, habits…)
    population  the governed segment / behavioural restriction (all, active, paying…)
    measure     the aggregate family (count, count_distinct, sum, avg, ratio)
    grain       the reporting scope of the answer (total, period, per_dimension)
"""

from __future__ import annotations

import logging
import re

from .numbers import parse_numbers

_log = logging.getLogger(__name__)

# --- vocabulary ---------------------------------------------------------------------
# The BUSINESS vocabulary (which entities and population segments exist) is governed in
# the semantic layer's `ontology` block and passed in at call time — the decomposer
# picks from those enums, the metric side reads the same words back, so comparison is
# exact equality. The ontology names entities with no metric (habits, sessions…) on
# purpose, so a question about one is expressible and provably unanswerable.
#
# MEASURES and GRAINS are universal query properties (every business has count/sum/ratio
# and total/period/breakdown), derived not authored, so they live here, not in the layer.
MEASURES = ["count", "count_distinct", "sum", "avg", "ratio", "other"]
GRAINS = ["total", "period", "per_dimension"]


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").lower())


def measure_of(agg: str) -> str:
    """The aggregate family of a metric's `agg` expression. Derived, not annotated —
    so it cannot drift from the SQL it describes. A ratio divides one aggregate by
    ANOTHER aggregate (guarded by nullif); a constant divisor inside an aggregate
    (mrr's annual `/ 12.0`) is a sum, not a ratio — so match division-by-an-aggregate,
    not any slash."""
    a = _norm(agg)
    if re.search(r"/(nullif\()?(count|sum|avg|min|max)\(", a):
        return "ratio"
    if a.startswith("avg("):
        return "avg"
    if "count(distinct" in a:
        return "count_distinct"
    if a.startswith("count("):
        return "count"
    if a.startswith("sum("):
        return "sum"
    return "other"


def additivity_of(measure: str) -> str:
    """Kimball additivity, derived from the measure family (a property of the aggregate,
    never a per-question judgement): additive sums over any dimension; semi-additive
    (distinct counts, stocks/snapshots) sums over everything except time; non-additive
    (averages, ratios) does not sum. Used for the coarse amount/rate split below; the
    finer semi-additive-over-time case is a grain/reconciliation concern, not this slot."""
    if measure in ("avg", "ratio"):
        return "non_additive"
    if measure == "count_distinct":
        return "semi_additive"
    if measure in ("sum", "count"):
        return "additive"
    return "unknown"


def metric_spec(m: dict) -> dict:
    """The governed spec of a metric, read straight from its definition. entity and
    population are first-class governed fields; measure derives from the aggregate."""
    return {"entity": m.get("entity", "other"),
            "population": m.get("population", "all"),
            "measure": measure_of(m.get("agg", ""))}


def grain_of_call(args: dict) -> str:
    """The reporting scope the answer was computed at, read from the query_metric
    arguments: a breakdown, a bounded window, or an all-time / as-of-now total. (This
    folds the time window into the scope; a WHERE-window is not a Kimball group-by grain,
    but for the purpose of 'did you answer the scope that was asked' it belongs here.)"""
    args = args or {}
    if args.get("group_by") or args.get("time_grain"):
        return "per_dimension"
    period = args.get("period")
    if (period and period != "all") or args.get("start") or args.get("end"):
        return "period"
    return "total"


# --- the comparison (deterministic) ------------------------------------------------
_SLOT_ORDER = ["entity", "population", "measure", "grain"]
_REASON = {"entity": "no_governed_definition", "population": "population_undefined",
           "measure": "wrong_measure", "grain": "wrong_grain"}


def _amount_or_rate(measure: str) -> str:
    """Collapse the measure family to the one distinction this slot refuses across: a
    'how many / how much' (additive or semi-additive) vs a 'what rate / share / average'
    (non-additive). A count implemented as a sum over a pre-aggregated fact is not a
    wrong answer, so those never refuse each other."""
    return "rate" if additivity_of(measure) == "non_additive" else "amount"


def first_mismatch(required: dict, answer: dict):
    """The first slot on which the question's spec and the answer's spec disagree, or
    (None, None, None). Slots the question left unspecified ('other'/'unknown') never
    trigger a refusal — the check only fires on a positive, named disagreement."""
    for slot in _SLOT_ORDER:
        want, got = required.get(slot), answer.get(slot)
        if not want or want in ("other", "unknown"):
            continue
        if got in (None, "other", "unknown"):
            continue
        if slot == "measure" and _amount_or_rate(want) == _amount_or_rate(got):
            continue
        if slot == "population" and required.get("measure") not in ("count", "count_distinct"):
            # A population is *which entities you count*, so it only bites a COUNTING
            # question. "How much revenue / what rate" does not choose an entity
            # population — its scope lives in the metric's own definition (MRR = active
            # subscriptions), so a named-metric question needn't restate a segment. We
            # key this off the QUESTION's measure, not the metric's, so a counting
            # question answered by a filtered SUM metric is still caught.
            continue
        if want != got:
            return slot, want, got
    return None, None, None


def _num_match(a: float, b: float) -> bool:
    """Two reported numbers are the same value, tolerant of rounding but not of distinct
    integers (886 != 18866, and adjacent counts 371 != 372 stay distinct)."""
    return abs(a - b) <= max(0.5, 0.005 * abs(b))


def _provenance(answer_text: str, steps: list, source_metric, metrics):
    """Which governed metric produced the answer, its call args, and the value it returned
    — taken ONLY from the model's typed `source_metric` declaration, never inferred from the
    answer text. When that metric was queried more than once (say a breakdown and a total),
    value-matching selects WHICH of ITS OWN calls produced the reported number, so the grain
    and the governed value are read from the right call. That is picking a call of an
    already-known metric, not guessing the metric — a value shared by two different metrics
    can never mislink, because the metric is declared. Returns (metric, args, value), or
    (None, None, None) when nothing verifiable was declared."""
    if source_metric not in metrics:
        return None, None, None
    calls = [s for s in (steps or []) if s.get("tool") == "query_metric"
             and (s.get("args") or {}).get("metric") == source_metric]
    if not calls:
        return None, None, None
    wanted = parse_numbers(answer_text)
    best = next((s for s in reversed(calls)
                 if any(_num_match(a, b) for a in wanted
                        for b in parse_numbers(s.get("result")))), calls[-1])
    governed = parse_numbers(best.get("result"))
    return source_metric, (best.get("args") or {}), (governed[0] if governed else None)


def result_sanity(metric_def: dict, value) -> tuple[bool, str, str, str]:
    """Deterministic checks on the RETURNED value, not the metric selection: a governed
    query that came back empty/null, or a value impossible for its `unit`, must not be
    served as an answer. Refuse-only. This is where the spec check (which validates *which*
    metric) can't see — it never looks at *what came back*."""
    if value is None:
        return (False, "result_empty", "the governed query returned no value (empty/null result)",
                "the metric produced no number for this request, so there is nothing to report; refuse.")
    unit = (metric_def or {}).get("unit")
    if value < 0 and unit in ("count", "currency", "share"):
        return (False, "implausible_value", f"a {unit} value cannot be negative (got {value})",
                f"the governed result {value} is impossible for a {unit} metric; refuse.")
    if unit == "share" and value > 100:
        return (False, "implausible_value", f"a share above 100 (got {value})",
                f"the governed result {value} is out of range for a share; refuse.")
    return True, "", "", ""


def verify_answer(semantic, question: str, answer_text: str | None, steps: list,
                  decompose, source_metric: str | None = None) -> tuple[bool, str, str, str]:
    """Return (ok, reason, missing, explanation). ok=False means convert the answer into
    a refuse; `missing` is the short slot fact, `explanation` the sentence.

    `decompose` is a callable(question) -> required_spec dict. It is injected so the
    deterministic half (metric_spec + comparison) is provable without a model call: the
    real caller passes an isolated LLM decomposer, the tests pass a stub. `source_metric`
    is the model's typed provenance declaration (preferred over value-linking)."""
    if semantic is None or not answer_text:
        return True, "", "", ""
    metric, args, value = _provenance(answer_text, steps, source_metric, semantic.metrics)
    if metric is None:
        if parse_numbers(answer_text):     # a numeric answer we can't attribute -> measure it
            _log.info("spec check: numeric answer with no usable source_metric; not verified")
        return True, "", "", ""                    # no governed metric to check against
    ok_r, reason_r, missing_r, expl_r = result_sanity(semantic.metrics[metric], value)
    if not ok_r:                                   # the returned value is empty or impossible
        return False, reason_r, missing_r, expl_r
    required = decompose(question) or {}
    if not required:
        _log.warning("spec decomposer returned no spec for question: %r", question)
        return True, "", "", ""                    # forced tool failed — don't guess
    answer = {**metric_spec(semantic.metrics[metric]), "grain": grain_of_call(args)}
    slot, want, got = first_mismatch(required, answer)
    if slot is None:
        return True, "", "", ""
    missing = f"{slot} '{want}' (the answer's metric {metric} is '{got}')"
    explanation = (f"the question asks for a '{want}' {slot}, but the number came from "
                   f"{metric}, whose {slot} is '{got}' — a governed metric for a different "
                   "question. No governed metric matches what was asked, so refuse rather "
                   "than report a near-miss as the answer.")
    return False, _REASON[slot], missing, explanation


# --- the isolated decomposer: question -> required spec (one model call, no catalog) -
def _declare_spec(entities, populations) -> dict:
    return {
        "name": "declare_spec",
        "description": "Declare the structured request spec for the question.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "enum": entities},
                "population": {"type": "string", "enum": populations},
                "measure": {"type": "string", "enum": MEASURES},
                "grain": {"type": "string", "enum": GRAINS},
            },
            "required": ["entity", "population", "measure", "grain"],
        },
    }

# The entity and population vocabularies are filled in from the layer's ontology; the
# rules stay abstract and the worked examples are all unrelated domains, so nothing here
# is tuned to the questions this check is measured on.
_DECOMPOSE_SYSTEM = (
    "You turn ONE business question into a structured request spec, so a separate system "
    "can check whether a given metric actually answers it. Describe only what the question "
    "ASKS FOR. You do not know which metrics exist and must not assume the question is "
    "answerable. Fill four slots, each from its fixed vocabulary.\n\n"
    "entity — the thing one unit counts or measures:\n{entities}\n\n"
    "population — the segment the question restricts to. Default to 'all' (the entire set "
    "of the entity). Choose a narrower segment ONLY when the question explicitly restricts "
    "the set it is counting:\n"
    "{populations}\n\n"
    "measure — count or count_distinct for 'how many'; sum for a total amount of money or "
    "units; avg or ratio for a rate, share, percentage, or average-per.\n\n"
    "grain — total for an all-time or current total with no time window; period when the "
    "question names a window (last week, in June, this quarter, year to date); per_dimension "
    "when it asks for a breakdown (by region, per week, split by plan).\n\n"
    "Worked examples (unrelated domains, to show the mapping):\n"
    "Q: How many employees do we have?\n"
    "   entity=other, population=all, measure=count, grain=total\n"
    "Q: How many employees logged in last week?\n"
    "   entity=other, population=active, measure=count_distinct, grain=period\n"
    "Q: How many paying customers do we have right now?\n"
    "   entity=other, population=paying, measure=count_distinct, grain=total\n"
    "Q: What was the average order value in June?\n"
    "   entity=revenue, population=all, measure=ratio, grain=period\n"
    "Q: How much did we spend on ads, by channel?\n"
    "   entity=spend, population=all, measure=sum, grain=per_dimension\n"
)


def _bullets(vocab: dict) -> str:
    return "\n".join(f"  {name} — {gloss}" for name, gloss in vocab.items())


def _coerce(spec: dict, entities, populations) -> dict:
    """JSON-schema enums are not always hard-enforced by the provider; map any out-of-
    vocabulary slot value to 'other' so a hallucinated value is ignored by the comparison,
    never refused on. (Defines the bad-enum error out of existence.)"""
    allowed = {"entity": set(entities), "population": set(populations),
               "measure": set(MEASURES), "grain": set(GRAINS)}
    out = dict(spec)
    for slot, ok in allowed.items():
        if slot in out and out[slot] not in ok:
            out[slot] = "other"
    return out


def decompose_question(model, question: str, ontology: dict) -> dict:
    """Isolated question -> spec. Fresh model call whose prompt carries only the layer's
    ontology (entities + population segments), never the metric catalog, and which is
    FORCED to call declare_spec at temperature 0. Returns the declared spec (out-of-vocab
    values coerced to 'other'), or {} if the forced call still produced nothing."""
    entities = ontology.get("entities", {})
    populations = ontology.get("populations", {})
    system = _DECOMPOSE_SYSTEM.format(entities=_bullets(entities),
                                      populations=_bullets(populations))
    resp = model.create(system, [{"role": "user", "content": question}],
                        [_declare_spec(list(entities), list(populations))],
                        force_tool="declare_spec", temperature=0)
    for b in getattr(resp, "content", []):
        if getattr(b, "type", None) == "tool_use" and b.name == "declare_spec":
            return _coerce(b.input or {}, entities, populations)
    return {}
