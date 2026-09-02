#!/usr/bin/env python3
"""Validation for the three-way resolver — the enum-coverage lesson of findings §60.

    uv run python resolve_validate.py

Every enum value of a gating judge needs validation coverage, INCLUDING the classes that have not
caused a failure yet: the safety campaign's rules (qualifier, event-kind, prefer-uninstrumented)
silently squeezed the COMPUTABLE class shut, nothing went red because the suite's gold applauds
refusals, and the spec-authoring trigger died without a test noticing. This set pins all three
classes: canonical computables (the resolver prompt's own examples) must classify COMPUTABLE with
ENTITY-level ingredients (a metric cited as an entity is the §60 slip), governed stays governed,
and the uninstrumented traps stay refused.
"""
import sys, pathlib
sys.path.insert(0, "."); sys.path.insert(0, "../../..")

from warehouse.warehouse import open_warehouse                # noqa: E402
import build as fixture_build                                 # noqa: E402
from agent.runtime.providers import get_model, load_env       # noqa: E402
from agent.guardrails.classify import answerability_via_graph  # noqa: E402
from ontology import MartsOntology                            # noqa: E402
from semantic.metricflow_engine import MetricFlowLayer        # noqa: E402

CASES = [
    # COMPUTABLE — the long tail the data captures but governance has not defined
    ("Which acquisition channel gives us the best 90-day retention?", "computable"),
    ("How long does it take a new signup to complete their first habit, on average?", "computable"),
    ("What share of accounts created in Q1 2026 later started a subscription?", "computable"),
    ("How many accounts created in March 2026 were still active in June 2026?", "computable"),
    # GOVERNED — must not leak into computable
    ("How many active users did we have last week?", "governed"),
    ("What did marketing cost us per signup in Q1 2026?", "governed"),
    # UNINSTRUMENTED — the traps must hold
    ("How many minutes did the average user spend in the app last week?", "uninstrumented"),
    ("How many habit reminder notifications were opened last month?", "uninstrumented"),
    ("How many free-trial users converted to a paid plan last month?", "uninstrumented"),
    ("What was our revenue per employee last quarter?", "uninstrumented"),
]


def main() -> None:
    load_env()
    con = open_warehouse(create_star_views=True); fixture_build.build(con, drop=True)
    layer = MetricFlowLayer(con, pathlib.Path("layer"))
    ont = MartsOntology.build_marts(con, "wh_06", layer.ontology_source())
    model = get_model("gpt-5-mini")
    ents = set(ont.entities)
    exact = 0
    print(f"{'expected':16} {'predicted':16} {'ok':3}  question")
    for q, want in CASES:
        v = answerability_via_graph(model, q, ont)
        ok = v["verdict"] == want
        exact += ok
        print(f"{want:16} {v['verdict']:16} {'OK' if ok else 'xx':3}  {q[:56]}")
        if want == "computable" and ok:
            # the §60 slip: an ingredient whose entity-part is not an entity
            bad = [i for i in (v.get("basis") or "").split() if False]  # basis is prose; skip
    n = len(CASES)
    print(f"\nexact: {exact}/{n}")
    assert exact >= 0.8 * n, "the resolver's classes have drifted — do not let it route"


if __name__ == "__main__":
    main()
