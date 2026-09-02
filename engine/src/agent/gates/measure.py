"""The measure family: substitution judgement routing and the answerability gate.

Extracted from loop.py (refactor phase 3). Every gate keeps its exact behaviour and signature —
`self` became the explicit `run` parameter, and cross-references go through the run's delegator
methods, so in-family and cross-family calls read identically. Gates return a ToolResult to hand
the answer back, or None (standing down, or after constructing into the exit call in place).
"""
from __future__ import annotations

import re                                                                   # noqa: F401

import evidence as claim_audit                                              # noqa: F401

from ..core import trace
from ..conversation import Conversation, ToolCall, ToolResult, Turn, Usage  # noqa: F401
from ..guardrails import Act, Position, after, before                       # noqa: F401
from ..guardrails import classify as _classify                              # noqa: F401
from ..guardrails import grounding_check as _grounding                      # noqa: F401
from ..numbers import bare_number, parse_numbers                            # noqa: F401
from ..outcomes import TERMINAL_TOOLS, Answer, declared_handles             # noqa: F401
from ..tool_args import AnswerArgs, ClarifyArgs, RefuseArgs                 # noqa: F401
from ._common import GRACE, MAX_CORRECTIONS                                 # noqa: F401

_COMPOSE = trace.COMPOSE
_leaf = trace.leaf
_as_number = trace.as_number
_reported = trace.reported
_scalar = trace.scalar


def substituted_measure(run, exit_call):
    """Hand back an answer whose number measures a DIFFERENT quantity than the question asked
    for — the substitution the grounding protocol cannot see, because it lives in the measure
    rather than the concept ("time spent per category" answered with a COUNT of completions).

    The judgement is the model's, on its own served answer, and its citation is verified
    (`classify.answer_measures_asked`); this method only routes the verdict. `unmeasured` — the
    asked quantity is not in the data at all — pushes to refuse. `proxy` — a related quantity
    stood in — leans by `MEASURE_PROXY_LEAN`: disclose the gap and serve, or refuse. `measures`
    serves untouched, which is the default on any doubt, so a clean answer is never delayed.

    Not a rigid equality gate: nothing here compares measure NAMES, and the model keeps the
    call. What changes is that the substitution must be made explicit — the same lever that
    turned the CSAT menu into a refusal, applied one level down.
    """
    g = run.grounding.guardrails
    if exit_call.name != "answer" or not getattr(g, "grounded_measure", False):
        return None
    parsed = AnswerArgs.of(exit_call.args)
    text = " ".join(x for x in (parsed.answer, parsed.explanation) if x).strip()
    if not text:
        return None
    # ONE SEMANTIC JUDGEMENT PER FACT. When the run's own check_answerability already resolved
    # this question's measure to metric M (a typed `resolution` record on the trace) and the
    # served figure IS a value M returned, the question->metric fit has been judged once —
    # graph-grounded and recorded. Running this judge again asks the same question in
    # different words, at a model call per answer; the audit found it costing 1-2 calls on
    # zero-risk serves. Risk-tiered verification: the judge runs only where no resolution
    # covered the serve.
    resolved = {e.get("metric") for s in run.steps if not s.get("blocked_by")
                for e in (s.get("evidence") or ())
                if e.get("kind") == "resolution" and e.get("verdict") == "governed"}
    if resolved:
        served_nums = parse_numbers(after.served_text(exit_call.args))
        for step in run.steps:
            if step.get("blocked_by") or step.get("tool") != "query_metric":
                continue
            if (step.get("args") or {}).get("metric") in resolved and any(
                    isinstance(v, (int, float)) and not isinstance(v, bool)
                    and _reported(served_nums, v)
                    for v in step.get("result_values") or ()):
                run.acts.append(Act("grounded_measure", str(Position.REPAIR), "allowed",
                                     "resolution dedupe: the measure was graph-resolved to "
                                     f"{(step.get('args') or {}).get('metric')!r} and its "
                                     "value is what the answer serves").as_dict())
                return None
    # NARROWED: a served figure that IS a queried contested-cluster reading is never a measure
    # substitution — which VARIANT it should be is the binding check's question, answered
    # deterministically. This judge kept "seeing" the variant mismatch, having no verdict for
    # it, and passing it as `measures`; wrong-variant is out of its jurisdiction now.
    sem = run.grounding.semantic
    if getattr(sem, "clusters", None) is not None:
        served_nums = parse_numbers(after.served_text(exit_call.args))
        for metric, args in run._governed_calls():
            try:
                rivals = sem.clusters.competitors(metric)
            except Exception:                                           # noqa: BLE001
                continue
            if not rivals:
                continue
            v = _scalar(before.value_of(sem, args, metric))
            if v is not None and _reported(served_nums, v):
                return None
    verdict, asked, served = _classify.answer_measures_asked(run.model, run.question, text)
    run.acts.append(Act("grounded_measure", str(Position.REPAIR),
                         "stood down" if verdict == "measures" else "handed back",
                         f"served {served or '?'} for asked {asked or '(same)'} [{verdict}]; "
                         f"correction {run.claim_retries} of 2").as_dict())
    if verdict == "measures":
        return None
    run.repairs.append({"substituted_measure":
                         {"asked": asked, "served": served, "verdict": verdict}})
    if verdict == "unmeasured" or run.MEASURE_PROXY_LEAN == "refuse":
        tail = (f"The quantity the question asks for — {asked!r} — is not measured in this "
                f"data; your number reports {served or 'something else'} instead. `refuse` "
                f"with reason `uninstrumented`, unless that number genuinely answers the "
                f"question — in which case say plainly why.")
    else:
        tail = (f"Your number reports {served or 'a related quantity'}, a stand-in for the "
                f"{asked!r} the question asks for, and the reader cannot tell one from the "
                f"other. Answer again stating plainly that {asked!r} is not directly measured "
                f"and that {served or 'this'} is a proxy — or `refuse` if the proxy is too "
                f"weak to stand for it.")
    return ToolResult("Your answer was not accepted: it does not measure what was asked.\n"
                      + tail, is_error=True)


def answerability_gate(run, exit_call):
    """Governance policy on the MEASURE: route a served answer by whether its measure is a
    governed metric, computable from the data, or uninstrumented (classify.classify_answerability
    over the governed ontology AND the data schema).

    - `governed`  -> serve (the semantic layer answered it).
    - `uninstrumented` -> refuse: the data does not capture it, under either policy.
    - `computable` -> STRICT refuses `no_governed_definition` (a figure with no governed
      definition is not authoritative); TRANSPARENT lets it stand IF the answer states the
      definition it computed by (else hands back to disclose or clarify). The transparent policy
      is the useful one — the agent may compute the long tail — made safe by the disclosure the
      number's trust rests on.

    This is where the raw-SQL escape is closed: retention has no governed metric, so a served
    retention figure is `computable` (or `uninstrumented`), and the gate refuses or requires
    disclosure rather than let an invented definition ship as fact.

    SCOPED TO RAW-SQL PROVENANCE. The gate guards ONE boundary — a number computed via run_sql
    for a measure with no governed home. A number composed from governed metric calls (a ratio
    of governed metrics like spend_per_signup = marketing_spend / new_signups) is already
    grounded in governance and is left alone; a governed-call substitution is grounded_measure's
    to catch, not this. So the answerability judgement runs only when the answer used run_sql —
    which is a FACT in the trace, not a model judgement, and which is why it does not flicker on
    a contested ratio the way a semantic classification did."""
    g = run.grounding.guardrails
    if not getattr(g, "answerability_gate", False):
        return None
    # Two boundaries, one gate. A SERVED number that bypassed governance is the raw-SQL escape
    # (below). A REFUSAL that claims the data is not captured is the other half: when the graph
    # can prove the measure computable, `uninstrumented` is the wrong reason. The refusal path
    # needs no run_sql scope — retention refuses without ever computing.
    if exit_call.name == "refuse":
        return run._answerability_refusal(exit_call, g)
    if exit_call.name != "answer":
        return None
    # Provenance scope: only a number that came from raw SQL bypassed governance. If the run made
    # no run_sql call, the figure was composed from governed metrics — nothing for this gate.
    if not any(step.get("tool") == "run_sql" and not step.get("blocked_by") for step in run.steps):
        return None
    semantic = run.grounding.semantic
    if semantic is None or not hasattr(semantic, "ontology_text"):
        return None
    parsed = AnswerArgs.of(exit_call.args)
    served = " ".join(x for x in (parsed.answer, parsed.explanation) if x).strip()
    if not served:
        return None
    # Where the verdict comes from. With graph_answerability, the model decomposes the measure
    # against the complete marts graph and MartsOntology.verify() decides existence and
    # joinability deterministically; otherwise the schema-text classifier judges it. The graph
    # path needs an ontology on the grounding — absent (build failed, or a non-MetricFlow layer),
    # it falls back, so the flag never breaks a run.
    if getattr(g, "graph_answerability", False) and run.grounding.ontology is not None:
        v = _classify.answerability_via_graph(run.model, run.question, run.grounding.ontology)
    else:
        from warehouse import schema_text
        from .rungs import capabilities
        con = getattr(run.grounding.toolbox, "con", None)
        sch = (schema_text(con, capabilities(run.grounding.rung).star,
                           getattr(run.grounding.toolbox, "schema", None)) if con is not None else "")
        v = _classify.classify_answerability(run.model, run.question, semantic.ontology_text(), sch)
    verdict, measure = v["verdict"], (v.get("measure") or "this quantity")
    if verdict == "governed":
        return None
    transparent = getattr(g, "transparent_compute", False)

    def act(outcome, detail):
        run.acts.append(Act("answerability_gate", str(Position.REPAIR), outcome,
                             f"measure {measure!r} is {verdict}, policy="
                             f"{'transparent' if transparent else 'strict'}: {detail}").as_dict())

    if verdict == "uninstrumented":
        act("handed back", "refuse uninstrumented")
        run.repairs.append({"answerability": {"verdict": verdict, "measure": measure}})
        miss = v.get("missing") or "data the warehouse does not have"
        return ToolResult(
            "Your answer was not accepted: the measure it reports is not captured in this data.\n"
            f"{measure} needs {miss}, which the warehouse does not have. `refuse` with reason "
            f"`uninstrumented`.", is_error=True)
    # verdict == computable
    if not transparent:
        act("handed back", "refuse no_governed_definition")
        run.repairs.append({"answerability": {"verdict": verdict, "measure": measure}})
        return ToolResult(
            "Your answer was not accepted: it reports a measure with no governed definition.\n"
            f"{measure} can be computed from the data, but no GOVERNED metric defines it, so a "
            f"single figure is not authoritative. `refuse` with reason `no_governed_definition`.",
            is_error=True)
    if _classify.answer_discloses_definition(run.model, run.question, served):
        act("stood down", "computed and disclosed")
        return None
    act("handed back", "computed but did not disclose the definition")
    run.repairs.append({"answerability": {"verdict": verdict, "measure": measure}})
    return ToolResult(
        "Your answer was not accepted: it computed a measure with no governed definition "
        f"({measure}) but did not state the definition it used.\n"
        "Answer again STATING the definition and how you computed it — and note the margin if a "
        "leading value is close to the next — or `clarify` which definition is wanted.",
        is_error=True)


def _answerability_refusal(run, exit_call, g):
    """The refusal-reason boundary. A refusal with reason `uninstrumented` asserts the warehouse
    does NOT capture the measure — a CLOSURE claim. When graph_answerability is on and the graph
    can PROVE the measure computable (real nodes that join), that claim is wrong: the data is
    captured, there is simply no governed metric, so the correct reason is `no_governed_definition`.
    The graph's closed-world fact overrides the model's open-world guess ('found no metric, so
    assume no data'); the collapse of computable into uninstrumented is the retention bug this
    closes.

    Fires ONLY on reason `uninstrumented`, ONLY under graph_answerability with an ontology, and
    ONLY when the graph returns `computable` — a positive proof. A graph `uninstrumented`
    (genuinely absent, or an island whose join is not curated) leaves the refusal untouched, so a
    genuinely uncaptured measure (csat, dark mode, minutes) is not disturbed. The verdict is
    verify()'s, not a second model judgement; the POLICY (strict reason-fix vs transparent
    compute) is read separately."""
    if not (getattr(g, "graph_answerability", False) and run.grounding.ontology is not None):
        return None
    if str(RefuseArgs.of(exit_call.args).reason or "").strip() != "uninstrumented":
        return None
    v = _classify.answerability_via_graph(run.model, run.question, run.grounding.ontology)
    if v["verdict"] != "computable":
        return None                       # the graph agrees it is not captured — refusal stands
    measure = v.get("measure") or "this measure"
    basis = v.get("basis") or "attributes the warehouse captures"
    transparent = getattr(g, "transparent_compute", False)
    run.repairs.append({"answerability_refusal": {"measure": measure, "verdict": "computable"}})
    run.acts.append(Act("answerability_gate", str(Position.REPAIR), "handed back",
                         f"refusal reason `uninstrumented` is wrong: {measure!r} is computable "
                         f"({basis}); policy={'transparent' if transparent else 'strict'}; "
                         f"correction {run.claim_retries} of 2").as_dict())
    if transparent:
        return ToolResult(
            "Your refusal used the wrong reason: this measure IS captured by the data.\n"
            f"{measure} can be COMPUTED from {basis} — it has no governed metric, but the data is "
            f"there. Do not refuse `uninstrumented`. Either compute it and STATE the definition "
            f"you used, or `refuse` with reason `no_governed_definition`.", is_error=True)
    return ToolResult(
        "Your refusal used the wrong reason: this measure IS captured by the data.\n"
        f"{measure} can be computed from {basis}; it has no GOVERNED metric, but the warehouse "
        f"does capture it. `refuse` with reason `no_governed_definition`, not `uninstrumented`.",
        is_error=True)
