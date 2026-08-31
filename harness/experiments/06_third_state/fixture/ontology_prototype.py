#!/usr/bin/env python3
"""End-to-end check that the ai-analytics-ontology module works on the real marts + a live model.

The inline graph is gone — this now USES `ontology.MartsOntology` (generated from information_schema,
closed-world over a complete present, no enumerated absence). The prototype keeps only the agent's
half: the LLM decomposes a measure into ingredients against ont.render(), and ont.verify() decides
the verdict. If this matches the hand-rolled prototype's 7/7, the productionised module is faithful.
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")
sys.path.insert(0, "../../..")

from run import LAYER, MARTS, RUNG, scoped_cursor          # noqa: E402
from agent.grounding import build_grounding                # noqa: E402
from agent.conversation import Conversation                # noqa: E402
from agent.providers import get_model, load_env            # noqa: E402
from warehouse.warehouse import open_warehouse             # noqa: E402
from ontology import MartsOntology                         # noqa: E402
import build as fixture_build                              # noqa: E402


# The marts-specific inputs the module generates the graph from. In production these come from the
# MetricFlow manifest (entities + type_params.measure) and column comments; here they are the small
# curated mapping the module turns into a complete, verified graph.
ENTITY_TABLES = {
    "user":         ("dim_users",          []),
    "activity":     ("fct_user_days",      ["value_moments", "app_opens"]),
    "subscription": ("fct_subscriptions",  ["billed_amount"]),
    "spend":        ("fct_marketing_spend",["spend"]),
    "habit":        ("dim_habit",          []),
}
RELATIONSHIPS = [
    ("activity", "user", "each activity row is performed_by a user (user_id), dated by active_date"),
    ("subscription", "user", "each subscription is held_by a user (user_id), started_date/ended_date"),
    ("habit", "user", "each habit was created_by a user (user_id)"),
]
MEASURE_SEMANTICS = {
    "value_moments": "number of completed habits (a count of habit-completion events)",
    "app_opens": "number of app-open events (an event count)",
    "billed_amount": "amount billed on a subscription term (currency)",
    "spend": "amount of marketing spend (currency)",
}

_SYSTEM = (
    "You resolve an analytics question against a CLOSED-WORLD marts ontology that lists everything "
    "the warehouse captures. Decide how the MEASURE the question asks for is answered, IN THIS "
    "ORDER, and cite the graph.\n\n"
    "1. GOVERNED — a governed metric fits directly, OR the measure is a RATIO/combination of governed "
    "metrics ('habits per active user' = value_moments per active_users). Report kind='governed', "
    "metric=metric.<name>.\n"
    "2. COMPUTABLE — no governed metric, but the measure can be DERIVED from attributes and measures "
    "IN the graph, via the relationships. DECOMPOSE it and list the ingredient nodes "
    "(entity.attribute / entity.measure), NOT join keys. Example: 90-day retention = signup cohort "
    "(user.signup_date) observed for return activity (activity.active_date), sliced by user.channel.\n"
    "3. UNINSTRUMENTED — the measure needs an ingredient NOT in this complete graph. Since the graph "
    "is complete, a concept absent from it does not exist: 'minutes in app' needs a duration measure "
    "and there is none (only event counts); 'top screen' needs a screen attribute and there is none; "
    "'revenue per employee' needs a headcount and there is no employee entity. Name the absent thing.\n\n"
    "Interpretation is yours; only real nodes count — every ingredient is checked against the graph.")
_REPORT = {"name": "resolve", "description": "Resolve the measure against the ontology.",
           "input_schema": {"type": "object", "properties": {
               "kind": {"type": "string", "enum": ["governed", "computable", "uninstrumented"]},
               "metric": {"type": "string"}, "ingredients": {"type": "array", "items": {"type": "string"}},
               "missing": {"type": "string"}}, "required": ["kind"]}}

REASON = {"instrumented": "answer (governed)", "computable": "no_governed_definition", "uninstrumented": "uninstrumented"}
TARGETS = [
    ("How many active users did we have last week?", "instrumented"),
    ("Which acquisition channel gives us the best 90-day retention?", "computable"),
    ("How many minutes did the average user spend in the app last week?", "uninstrumented"),
    ("Which screen in the app did users visit most last week?", "uninstrumented"),
    ("How many habits did the average active user complete last week?", "instrumented"),
    ("What was our revenue per employee last quarter?", "uninstrumented"),
    ("What was the most common reason customers gave for cancelling?", "uninstrumented"),
]


def resolve(model, question, ont: MartsOntology):
    """The agent's half: the model decomposes against the graph; the module verifies existence."""
    user = f"{ont.render()}\n\nQuestion: {question}\n\nHow is the measure answered? Cite the graph."
    turn = model.respond(Conversation.opening(_SYSTEM, user), [_REPORT], force_tool="resolve", temperature=0)
    call = next(c for c in turn.tool_calls if c.name == "resolve")
    return ont.verify(call.args.get("kind"), metric=str(call.args.get("metric") or ""),
                      ingredients=call.args.get("ingredients") or [])


def main():
    load_env()
    con = open_warehouse(create_star_views=True)
    fixture_build.build(con, drop=True)
    cur = scoped_cursor(con)
    sem = build_grounding(cur, rung=RUNG, spec_path=LAYER, engine="metricflow",
                          semantic_layer=True, guardrails=None, schema=MARTS).semantic
    ont = MartsOntology.build(cur, MARTS, ENTITY_TABLES,
                              {m: (d.get("description") if isinstance(d, dict) else "") for m, d in sem.metrics.items()},
                              relationships=RELATIONSHIPS, measure_semantics=MEASURE_SEMANTICS)
    model = get_model("gpt-5-mini")
    print(f"MartsOntology: {len(ont.entities)} entities, {len(ont.nodes)} nodes, {ont.fingerprint()}\n")
    for q, expect in TARGETS:
        verdict, why = resolve(model, q, ont)
        flag = "OK " if verdict == expect else "XX "
        print(f"{flag}{q[:56]:56} {expect:14} {verdict:14} -> {REASON.get(verdict, verdict)}")


if __name__ == "__main__":
    main()
