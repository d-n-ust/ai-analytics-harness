"""define_measure — author a measure DEFINITION, verify it deterministically, compute, disclose.

The orchestration that ties the pure core (measure.py) and the executor (measure_exec.py) into one
capability. The LLM does its one job — author a `{scope, spec}` from the question as STRUCTURED output
(not prose to parse). The deterministic pipeline then decides everything the model does not:

    author {scope, spec}        LLM (language)          the ONLY model call
      -> coherent(spec)         deterministic           invalid definition -> re-author
      -> ground(spec, graph)    deterministic           uninstrumented -> refuse (not captured)
      -> bind_scope(scope,spec) deterministic           a dropped component -> re-author (bind it)
      -> run_ephemeral(spec)    imperative shell         did not execute -> re-author
      -> disclose               the spec IS the account

The author->check->re-author loop is bounded (like a coding agent iterating on a failing test): the
model is handed the specific deterministic failure and tries again, at most `max_tries` times, then
gives up rather than looping. Aptness — whether a bound, grounded, executing spec is the RIGHT
definition — is NOT decided here; that is the adversarial challenger, a later phase. This phase
guarantees completeness (bind_scope), existence (ground), validity (coherent) and honest disclosure.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..core.conversation import Conversation
from ..guardrails import classify as _classify
from ..core.measure import Scope, Spec, bind_scope, coherent, ground
from .measure_exec import run_ephemeral

_SYSTEM = (
    "You answer an analytics question by AUTHORING A DEFINITION, not by computing a number in your "
    "head. Emit two things against the closed-world marts graph you are shown:\n\n"
    "SCOPE — what the question asks for, decomposed so nothing is silently dropped:\n"
    "  measure: the quantity, in a few words.\n"
    "  segments: every governed restriction to a SINGLE VALUE the question names, each as "
    "[entity__dimension, value] (e.g. ['activity__platform','web']). A BREAKDOWN or comparison ('by "
    "channel', 'which channel', 'per region') is NOT a segment — it is a grouping the spec produces; "
    "leave it out of segments. 'all channels' is not a segment either. Empty if none.\n"
    "  period: the time window the question names, in the layer's grammar (e.g. '2026-Q2', "
    "'last_week', '2026'). Empty if none.\n"
    "  qualifiers: any definitional constraint stated ('started in', 'including refunds', 'at day "
    "90'). Empty if none.\n\n"
    "SPEC — how the measure is DEFINED and computed. Choose the simplest kind that fits, IN ORDER:\n"
    "  kind='metric': a governed metric fits directly. Set metric=<name>.\n"
    "  kind='derived': combine governed metrics with an op (ratio/difference/sum/product). Set op and "
    "inputs=[{kind:'metric',metric:...}, ...]. Use for a ratio or a change of governed metrics.\n"
    "  kind='query': no governed metric, but the graph has the columns to compute it. Set source "
    "(entity), measure (column), agg (sum/count_distinct/average/min/max), and any grain.\n"
    "  kind='raw': genuinely bespoke (a cohort/retention curve, custom windowing). Set sql and a "
    "one-line definition of what it computes. If the question asks ONE number, the SQL must RETURN "
    "one row — aggregate inside the definition, never hand back per-account rows for a prose "
    "average. Sanity-check a share: exactly 0.0 or 1.0 usually means a join bug (numerator equals "
    "denominator); re-derive the two counts separately in CTEs. Follow dbt modelling practice: build it in CTEs "
    "(cohort -> observation -> rate), STATE THE GRAIN in the definition ('one row is one channel'), "
    "return EXACTLY the grouping the question asks for, and guard division with nullif. Use ONLY the "
    "tables and columns listed under AVAILABLE TABLES, in the stated SQL dialect. A retention or "
    "cohort measure is the canonical kind='raw' case.\n\n"
    "PREFER GOVERNED METRICS, but do not force them. If a governed metric names the quantity — or a "
    "ratio 'X per Y' of two governed metrics does (acquisition_spend per new_signups) — use "
    "kind='metric' or kind='derived' with those metrics as inputs, and do NOT reconstruct a governed "
    "metric from raw columns with a query. But a genuinely bespoke measure a governed metric does NOT "
    "name — a cohort or retention calculation, custom windowing — is exactly what kind='raw' is for; "
    "author the SQL rather than contorting governed metrics into something they do not compute.\n\n"
    "A governed metric ALREADY EMBEDS ITS OWN SCOPE (acquisition_spend already excludes partnerships; "
    "active_users already excludes internal accounts). Never add a filter that restates a metric's "
    "own definition — a filter is ONLY for a segment the QUESTION restricts to. If the question's "
    "constraint is exactly what a governed metric already means, pick that metric and add no filter.\n\n"
    "DEFINITIONAL CHOICES ARE PART OF THE DEFINITION. A tail measure usually has latitude the "
    "question does not settle — a DENOMINATOR (the whole cohort, or only accounts with the "
    "event?), a WINDOW convention (within N days of signup; an offset month), a day-difference "
    "basis. Your definition text MUST state each such choice in plain words ('averaged over "
    "accounts that completed at least one habit', 'counting accounts with none as zero'). When "
    "the question is SILENT on a choice that changes the number, use the canonical reading — an "
    "interval 'time to first X' averages over accounts that HAVE X; a per-account count over a "
    "cohort includes accounts with zero; a window runs from each account's own signup — AND name "
    "the choice, so the reader can tell which question was answered.\n\n"
    "BIND EVERY SCOPE COMPONENT INTO THE SPEC. A segment the question named must appear as a filter "
    "([entity__dimension, value]) on the spec (or on a derived input); the period must be set; each "
    "qualifier must be listed in `addressed` (or reflected in the SQL). A component you leave unbound "
    "will be rejected. Only real nodes of the graph exist; if the measure needs something the graph "
    "does not have, author it anyway and it will be refused as uninstrumented.")


def _spec_props(with_op: bool) -> dict:
    p = {
        "kind": {"type": "string", "enum": ["metric", "query", "derived", "raw"]},
        "metric": {"type": "string", "description": "kind=metric: the governed metric name"},
        "source": {"type": "string", "description": "kind=query: the entity the measure is on"},
        "measure": {"type": "string", "description": "kind=query: the measure column"},
        "agg": {"type": "string", "description": "kind=query: sum|count_distinct|average|min|max"},
        "grain": {"type": "string", "description": "kind=query: the group-by level, if any"},
        "sql": {"type": "string", "description": "kind=raw: the SQL over the marts tables"},
        "definition": {"type": "string", "description": "kind=raw: one line, what the SQL computes"},
        "filters": {"type": "array", "items": {"type": "array", "items": {"type": "string"}},
                    "description": "segment filters applied, as [entity__dimension, value] pairs"},
        "period": {"type": "string", "description": "the period this spec computes over"},
        "addressed": {"type": "array", "items": {"type": "string"},
                      "description": "qualifiers from the question this spec accounts for"},
    }
    if with_op:
        p["op"] = {"type": "string", "enum": ["ratio", "difference", "sum", "product"],
                   "description": "kind=derived: how the inputs combine"}
        p["inputs"] = {"type": "array", "items": {"type": "object", "properties": _spec_props(False)},
                       "description": "kind=derived: the input specs to combine (leaf specs)"}
    return p


_DEFINE_TOOL = {
    "name": "define_measure",
    "description": "Author the scope of the question and a spec (definition) for its measure.",
    "input_schema": {"type": "object", "properties": {
        "scope": {"type": "object", "properties": {
            "measure": {"type": "string"},
            "segments": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
            "period": {"type": "string"},
            "qualifiers": {"type": "array", "items": {"type": "string"}}},
            "required": ["measure"]},
        "spec": {"type": "object", "properties": _spec_props(True)}},
        "required": ["scope", "spec"]},
}


@dataclass
class Defined:
    """The outcome of authoring + verifying + computing a definition. `outcome` is answer / refuse /
    gave_up. On answer, `value` (scalar) or `rows` carries the result, `verdict` the grounding
    (instrumented/computable/raw), `tier` the trust level, `disclosure` the reader-facing account.
    On refuse, `reason` is the code (uninstrumented). `tries` is how many re-authorings it took."""

    outcome: str
    scope: Scope
    spec: Spec
    verdict: str = ""
    tier: str = ""
    value: float | None = None
    rows: tuple = ()
    disclosure: str = ""
    reason: str = ""
    tries: int = 0
    error: str = ""
    aptness: str = ""              # the adversary's verdict on an ad-hoc spec: apt | contested | wrong
    aptness_note: str = ""         # the alternative reading or defect it named, when not apt


# A "segment" whose value is one of these is a breakdown or a non-restriction, not a real filter —
# dropped so bind_scope does not demand binding a filter that isn't one (the model sometimes emits
# `[channel, ALL]` for "all channels" or "by channel").
_PSEUDO_SEGMENT = {"all", "any", "*", "none", "", "every", "each", "total"}


def warehouse_context(ontology) -> str:
    """The table catalogue and SQL dialect a `raw` spec must be written against — rendered from the
    ontology (real table names + their columns), so the model authoring bespoke SQL is not blind to
    what exists or to the dialect. Context engineering: give the agent the schema, like a coding
    agent gets the codebase. Cheap and always included — it also helps a query spec name real
    columns."""
    lines = ["AVAILABLE TABLES (refer to them by these exact names; columns in parentheses):"]
    for _ent, d in ontology.entities.items():
        cols = ", ".join(list(d["attributes"]) + list(d["measures"]))
        lines.append(f"  {d['table']}({cols})")
    lines += [
        "",
        "SQL DIALECT — DuckDB (NOT BigQuery or Snowflake):",
        "  - date arithmetic: signup_date + INTERVAL 90 DAY   (no DATE_ADD, no DATEADD)",
        "  - safe division: numerator / nullif(denominator, 0)   (no SAFE_DIVIDE)",
        "  - the marts schema is already on the search path — use the bare table names above.",
    ]
    return "\n".join(lines)


def _parse_scope(d: dict) -> Scope:
    d = d or {}
    segs = tuple((str(s[0]), str(s[1])) for s in (d.get("segments") or [])
                 if isinstance(s, (list, tuple)) and len(s) >= 2
                 and str(s[1]).strip().lower() not in _PSEUDO_SEGMENT)
    return Scope(measure=str(d.get("measure") or ""), segments=segs,
                 period=str(d.get("period") or ""),
                 qualifiers=tuple(str(q) for q in (d.get("qualifiers") or [])))


def _parse_spec(d: dict) -> Spec:
    d = d or {}
    kind = str(d.get("kind") or "").strip()
    filters = tuple((str(f[0]), str(f[1])) for f in (d.get("filters") or [])
                    if isinstance(f, (list, tuple)) and len(f) >= 2)
    period = str(d.get("period") or "")
    addressed = tuple(str(q) for q in (d.get("addressed") or []))
    if kind == "metric":
        # The graph renders metrics as `metric.<name>`; the model echoes that form, but the engine
        # queries by the bare name. Strip the prefix so an authored `metric.active_users` executes.
        name = str(d.get("metric") or "").strip()
        name = name[len("metric."):] if name.startswith("metric.") else name
        return Spec.metric(name, filters=filters, period=period, addressed=addressed)
    if kind == "query":
        return Spec.query(str(d.get("source") or ""), str(d.get("measure") or ""),
                          str(d.get("agg") or ""), str(d.get("grain") or ""),
                          filters=filters, period=period, addressed=addressed)
    if kind == "derived":
        return Spec.derived(str(d.get("op") or ""), inputs=[_parse_spec(i) for i in (d.get("inputs") or [])],
                            filters=filters, period=period, addressed=addressed)
    if kind == "raw":
        return Spec.raw(str(d.get("sql") or ""), str(d.get("definition") or ""),
                        filters=filters, period=period, addressed=addressed)
    return Spec(kind=kind or "unknown")


def _disclose(scope: Scope, spec: Spec, res, tier: str) -> str:
    asked = scope.measure
    if scope.segments:
        asked += " [" + ", ".join(f"{d}={v}" for d, v in scope.segments) + "]"
    if scope.period:
        asked += f" for {scope.period}"
    val = res.value if res.value is not None else f"{len(res.rows)} rows"
    note = {"governed": "a governed definition", "computed": "computed (no governed metric); "
            "definition disclosed", "raw": "computed by bespoke SQL; definition disclosed"}.get(tier, "")
    return f"You asked for {asked}. Computed via {res.definition} = {val}. [{note}]"


def _author(model, question: str, ontology_render: str, wh_context: str, feedback: str) -> dict:
    user = f"{ontology_render}\n\n{wh_context}\n\nQuestion: {question}"
    if feedback:
        user += f"\n\nYour previous definition was REJECTED — {feedback}\nAuthor a corrected definition."
    turn = model.respond(Conversation.opening(_SYSTEM, user), [_DEFINE_TOOL],
                         force_tool="define_measure", temperature=0)
    call = next((c for c in turn.tool_calls if c.name == "define_measure"), None)
    return call.args if call else {}


def define_measure(model, question: str, ontology, engine, max_tries: int = 2,
                   challenge: bool = True) -> Defined:
    """Author a definition for the question's measure, verify it deterministically, compute, disclose.
    The one model call authors {scope, spec}; the deterministic pipeline decides the rest, handing back
    a specific failure for the model to fix, bounded by max_tries."""
    feedback, scope, spec = "", Scope(), Spec(kind="unknown")
    wh_context = warehouse_context(ontology)
    for attempt in range(max_tries + 1):
        args = _author(model, question, ontology.render(), wh_context, feedback)
        scope, spec = _parse_scope(args.get("scope")), _parse_spec(args.get("spec"))

        viol = coherent(spec)
        if viol:
            feedback = "the definition is invalid: " + "; ".join(f"{k} — {d}" for k, d in viol)
            continue

        verdict, detail = ground(spec, ontology)
        if verdict == "uninstrumented":
            return Defined("refuse", scope, spec, verdict=verdict, reason="uninstrumented",
                           tries=attempt, disclosure=f"{scope.measure} is not captured by the data: {detail}")

        unbound = bind_scope(scope, spec)
        if unbound:
            feedback = ("the spec drops components the question named: "
                        + "; ".join(f"{k} {d}" for k, d in unbound)
                        + " — bind each (add the filter / set the period / list the qualifier in "
                          "`addressed`), or drop it from the scope if the question did not name it")
            continue

        res = run_ephemeral(spec, engine)
        if not res.ok:
            feedback = f"the spec did not execute: {res.error} — fix the definition"
            continue
        # THE GRAIN BOUNCE. A raw spec that returns many rows for a question with no stated
        # breakdown hands the model a table to aggregate in prose — which is how "7.9" got
        # eyeballed from 100 account-grain rows for a true 9.69. A single-number question must be
        # aggregated INSIDE the definition; deterministic, bounded like every other repair here.
        breakdown = " by " in question.lower() or " per " in question.lower() \
            or "which " in question.lower() or "each " in question.lower()
        if spec.kind == "raw" and res.value is None and len(res.rows) > 3 and not breakdown:
            feedback = (f"the definition returns {len(res.rows)} rows at row grain, but the "
                        f"question asks for ONE number — aggregate inside the SQL (AVG/COUNT/"
                        f"ratio in a final SELECT) and return a single row")
            continue

        tier = {"instrumented": "governed", "computable": "computed", "raw": "raw"}.get(verdict, "computed")
        d = Defined("answer", scope, spec, verdict=verdict, tier=tier, value=res.value,
                    rows=res.rows, tries=attempt, disclosure=_disclose(scope, spec, res, tier))

        # APTNESS (the adversary). A governed metric is authoritative for its concept — skip it; an
        # AD-HOC spec (derived/query/raw) is where the definition could be the wrong one, so an
        # independent reviewer challenges it. Validated as a discriminator, not yet a hard gate: a
        # not-apt verdict is DISCLOSED (the reader sees the alternative), not silently served and not
        # refused, which is the safe use of a judge validated on a small set.
        if challenge and spec.kind != "metric":
            defn = res.definition + (f"\nSQL:\n{spec.sql}" if spec.kind == "raw" else "")
            apt = _classify.challenge_aptness(model, question, defn)
            d.aptness, d.aptness_note = apt["verdict"], (apt.get("alternative") or apt.get("why") or "")
            if apt["verdict"] != "apt":
                d.disclosure += (f"  NOTE ({apt['verdict']}): a competent analyst might read this "
                                 f"differently — {d.aptness_note}")
        return d

    return Defined("gave_up", scope, spec, tries=max_tries, error=feedback,
                   disclosure=f"could not author a valid definition for {scope.measure!r}: {feedback}")
