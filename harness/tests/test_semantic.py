"""No-LLM proofs of the answer output-guardrails and the semantic layer.

The output guardrails (harness/verifier.py) run on a completed answer, gated by rung:
provenance / governed_numbers (R7), output validation (R8), and the trajectory verifier (R9,
stubbed here so the file never calls an LLM). Everything asserted below is deterministic and
provable by construction. The rest exercises the semantic layer, the coverage check, and the
guardrail ladder.

Run: uv run python -m pytest harness/tests/test_semantic.py -q     (or run this file directly)
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import harness_paths
from agent.conversation import TERMINAL_TOOLS
from agent.guardrails import LADDER
from agent.guardrails import after as verifier
from agent.guardrails import before as input_guardrail
from agent.numbers import bare_number
from agent.tools import Toolbox
from semantic.semantic import COVERAGE_DIMS, SemanticError, SemanticLayer
from semantic.tree import MetricTree
from warehouse.warehouse import open_warehouse


def _qm(metric, value, handle="", **args):
    """A recorded query_metric step returning one scalar, as the trace stores it: the typed
    `result_values` the dispatcher records, plus the display string. `handle` is what an answer
    names in `sources`; a step without one can be read but never cited."""
    try:
        vals = [float(value)]
    except (TypeError, ValueError):
        vals = []
    return {"tool": "query_metric", "args": {"metric": metric, **args}, "handle": handle,
            "result": f"columns: value\n({value},)", "result_values": vals}


def test_provenance_is_typed_not_guessed():
    """The metric comes from the declaration; value-matching only selects WHICH call of
    that declared metric set the grain."""
    metrics = SemanticLayer(open_warehouse()).metrics
    # active_users queried twice; the reported 886 picks the last_week call (grain), not the total.
    steps = [_qm("active_users", 2100, period="all"),
             _qm("active_users", 886, period="last_week")]
    m, args, val = verifier._provenance(886, steps, "active_users", metrics)
    assert m == "active_users" and args.get("period") == "last_week" and val == 886, (m, args, val)
    # a value shared across metrics never mislinks — the declared metric wins either way
    coll = [_qm("active_subscriptions", 371), _qm("paying_users", 371)]
    assert verifier._provenance(371, coll, "paying_users", metrics)[0] == "paying_users"
    assert verifier._provenance(371, coll, "active_subscriptions", metrics)[0] == "active_subscriptions"
    # no declaration, or a declared-but-unqueried metric -> nothing to verify
    assert verifier._provenance(371, coll, None, metrics) == (None, None, None)
    assert verifier._provenance(371, coll, "mrr", metrics) == (None, None, None)


def _breakdown(metric, pairs, **args):
    """A recorded query_metric step for a BREAKDOWN — one row, and one number, per group."""
    rows = "\n".join(f"({k!r}, {v})" for k, v in pairs)
    return {"tool": "query_metric", "args": {"metric": metric, **args},
            "result": f"columns: platform, value\n{rows}",
            "result_values": [float(v) for _, v in pairs]}


def test_provenance_reads_the_row_the_answer_came_from():
    """A breakdown returns one number per group, and the model answers with one of them. The
    checks must be handed THAT number: reading the first row instead means R8 range-checks a
    figure nobody reported, the R9 judge is shown the wrong one, and the verdict stored so the
    judge can later be scored records the wrong evidence."""
    metrics = SemanticLayer(open_warehouse()).metrics
    step = _breakdown("value_moments", [("android", 5190), ("ios", 5648), ("web", 4812)],
                      group_by=["platform"], period="last_month")
    _m, _args, val = verifier._provenance(4812, [step], "value_moments", metrics)
    assert val == 4812, f"the answer served 4812; the checks were handed {val}"
    _m, _args, val = verifier._provenance(5648, [step], "value_moments", metrics)
    assert val == 5648, f"the answer served 5648; the checks were handed {val}"
    # A declared number matching no row of a breakdown is not attributable to one of them.
    assert verifier._provenance(9999, [step], "value_moments", metrics)[2] is None


def test_dispatcher_records_the_measure_not_every_cell():
    """`result_values` is the `value` column the compiler aliases the measure to — one number
    per row. Recording every numeric cell instead loses which one is the measure, and lets a
    numeric dimension member pass for a governed result."""
    con = open_warehouse(create_star_views=True)
    tb = Toolbox(con, 6, SemanticLayer(con), None, LADDER[5])
    res = tb.dispatch("query_metric", {
        "metric": "value_moments", "group_by": ["platform"], "period": "last_month"})
    text, is_err, values = res.content, res.is_error, res.values
    assert not is_err, text
    rows = [ln for ln in text.splitlines() if ln.startswith("(")]
    assert len(values) == len(rows), f"{len(values)} values recorded for {len(rows)} rows"
    # each recorded value is that row's own measure, in row order
    for row, v in zip(rows, values, strict=True):
        assert row.rstrip(")").split(", ")[-1] == str(int(v)), (row, v)


def test_numeric_answers_cannot_skip_the_output_checks():
    """`value` is optional so prose isn't forced to invent a number — which meant a model that
    wrote the figure into `answer` and left the field unset skipped R7/R8/R9 entirely (~6% of
    answers did). A numeric answer is now recovered and checked; prose that merely quotes a
    figure is untouched, and the sign survives, because a negative count must still be caught."""
    for text, want in [("3852", 3852.0), ("$36,875.98", 36875.98), ("280 value moments", 280.0),
                       ("62%", 62.0), ("-3", -3.0), ("  472 ", 472.0)]:
        assert bare_number(text) == want, (text, bare_number(text))
    for prose in ["Weekly value moments fell 11.88% (from 4,196 to 3,698)",
                  "iOS at 5,648 and Android at 5,190", "about 472",
                  "no governed definition for engagement score", "", None]:
        assert bare_number(prose) is None, prose

    # A recovered number is then held to the same checks as a declared one — proved end to end
    # in test_orchestrator.py, where the wiring lives. What belongs here is the attribution it
    # depends on: an undeclared metric is inferred only when exactly one governed metric
    # returned that number, so a value two metrics share can never mislink.
    sem = SemanticLayer(open_warehouse(create_star_views=True))
    steps = [_qm("active_users", 886, period="last_week")]
    assert verifier._infer_source_metric(886, steps, sem.metrics) == "active_users"
    shared = [_qm("active_subscriptions", 371), _qm("paying_users", 371)]
    assert verifier._infer_source_metric(371, shared, sem.metrics) is None, "ambiguous -> no link"


def test_every_offered_tool_can_be_dispatched():
    """A tool's schema and the code that runs it were defined 300 lines apart with nothing
    linking them, so nothing stopped one existing without the other. Offered-but-undispatchable
    is a hallucination the model is invited to make; dispatchable-but-never-offered is dead code
    pretending to be a guardrail."""
    con = open_warehouse(create_star_views=True)
    tb = Toolbox(con, 6, SemanticLayer(con), MetricTree(SemanticLayer(con)), LADDER[9])
    for spec in tb.specs():
        name = spec["name"]
        if name in TERMINAL_TOOLS:
            continue                      # the agent loop ends the run; there is nothing to run
        result = tb.dispatch(name, {})
        assert not result.content.startswith("Unknown tool"), f"{name} is offered but not dispatchable"


def test_the_check_tools_can_express_every_scope_the_guardrail_enforces():
    """A model told to pre-check answerability must be able to ask about the same scopes it will
    then be judged on. check_coverage accepts a region but not a country, while the coverage check resolves
    a country to its region — so a Philippines question pre-checks clean and is then blocked, and
    at the rung where the check tools exist without the coverage check it is never caught at all."""
    con = open_warehouse(create_star_views=True)
    tb = Toolbox(con, 6, SemanticLayer(con), None, LADDER[9])
    coverage = next(t for t in tb.specs() if t["name"] == "check_coverage")
    offered = set(coverage["input_schema"]["properties"])
    assert set(COVERAGE_DIMS) <= offered, (
        f"check_coverage offers {sorted(offered)}; the coverage check judges "
        f"{sorted(COVERAGE_DIMS)} — the model cannot ask about {sorted(set(COVERAGE_DIMS) - offered)}")


def test_the_guardrail_registry_matches_the_set_and_names_real_files():
    """Guardrail flags sat in one file while their implementations lived in two to four others,
    with nothing connecting them — so "what does this guardrail actually do" could only be
    answered by grepping. The registry answers it, and this keeps the answer true: every flag is
    described, in ladder order, and every file it claims to be implemented in exists and mentions
    it."""
    from agent.guardrails import GUARDRAILS, LADDER, LADDER_ORDER, GuardrailSet, Position

    declared = [f.name for f in dataclasses.fields(GuardrailSet)]
    assert [g.name for g in GUARDRAILS] == declared, \
        "the registry and the flag set must be the same guardrails, in one order"
    # LADDER_ORDER is the registry's `in_ladder` SUBSET, not the whole of it. Two guardrails sit
    # outside the published ladder — `clarify`, which every run ever stored already had, and
    # `typed_clarify`, which arrived after R0..R9 were published — and keeping them out is what
    # lets both exist without renumbering a rung. The subset relation is asserted rather than the
    # equality, so the registry and the ladder still cannot drift apart in either direction.
    assert LADDER_ORDER == [g.name for g in GUARDRAILS if g.in_ladder], \
        "the ladder must be exactly the registry's in_ladder entries, in registry order"
    for g in GUARDRAILS:
        if not g.in_ladder:
            preset_values = {getattr(LADDER[n], g.name) for n in LADDER}
            assert len(preset_values) == 1, (
                f"{g.name} is outside the ladder but varies across presets — an out-of-ladder "
                f"guardrail must hold its declared default in every rung, or R0..R9 no longer "
                f"mean what the published runs meant")

    root = harness_paths.ROOT / "engine" / "src" / "agent"
    for g in GUARDRAILS:
        assert isinstance(g.position, Position) and g.mechanism, g.name
        for rel in g.implemented_in:
            path = root / rel
            assert path.exists(), f"{g.name}: claims {rel}, which does not exist"
            assert g.name in path.read_text(), f"{g.name}: {rel} never mentions it"

    # Position is the distinction that carries information, so each one must be used — but not
    # necessarily by a GUARDRAIL. REPAIR is used by the protocol layer's citation repair, which
    # is a mechanism at a position without being a rung on the ladder. Asserting against the
    # whole package keeps the "no dead position" guarantee while letting a position outlive the
    # axis it was first needed for.
    used = {g.position for g in GUARDRAILS}
    source = "\n".join(p.read_text() for p in root.rglob("*.py"))
    for pos in Position:
        assert pos in used or f'Position.{pos.name}' in source, f"unused position: {pos}"


def test_a_tree_node_reports_the_metric_it_names():
    """The invariant the tree broke: asking the tree about a node and asking the layer about the
    metric that node names must give the SAME number.

    The root was declared as `value_moments` — which counts every account — while its three
    identity children all exclude internal/test, and explain_change forced the exclusion onto the
    parent too. So the tree reported 4,133 for a metric the layer said was 4,307, and an agent
    answering "why did value moments drop?" quoted figures 4% away from `query_metric
    value_moments`. Same word, two numbers, nothing to say which was meant.

    The identity now closes because the DEFINITIONS agree, not because the tree re-filters: the
    North Star is its own governed metric (real_value_moments) rather than a filter applied in a
    second place. NO LLM."""
    from semantic.tree import MetricTree

    con = open_warehouse()
    sem = SemanticLayer(con)
    tree = MetricTree(sem)

    for node, spec in tree.nodes.items():
        metric = spec["metric"]
        for period in ("prev_week", "last_week"):
            via_tree = sem.scalar(metric, period=period)
            _, rows = sem.query(metric, resolve=True, period=period)
            assert rows and abs(via_tree - rows[0][-1]) < 1e-9, \
                f"node {node} names {metric} but the tree and the layer disagree for {period}"

    # The identity is an arithmetic CLAIM — parent = breadth x frequency x depth — so it has to
    # close exactly, and it only can within one population.
    for period in ("prev_week", "last_week"):
        parent = sem.scalar("real_value_moments", period=period)
        product = 1.0
        for child in ("active_users", "days_per_user", "moments_per_day"):
            product *= sem.scalar(child, period=period)
        assert abs(parent - product) < 1e-6, \
            f"{period}: identity does not close — {parent} vs {product}"

    # And the raw all-accounts measure still exists and still differs, or the fix silently
    # redefined what the lookup questions ask for (their gold_sql counts fct_value_moments
    # unfiltered).
    assert sem.scalar("value_moments", period="last_week") > sem.scalar("real_value_moments",
                                                                       period="last_week"), \
        "value_moments must keep its all-accounts meaning; the lookup golds count every row"


def test_the_tree_writes_its_numbers_down():
    """A decomposition's numbers are governed results and must be recorded as such.

    They were not. `explain_change` returned JSON and no `values`, so the loop gave it no handle
    and nothing downstream could see what it produced — a diagnostic answer built on the tree was
    untraceable, and governed_numbers' predecessor refused it as hand-composed. It never was: the tree derived
    every figure deterministically from governed metrics through an identity it declares. Nothing
    had written them down.

    Shares and percent changes are included, not just levels: they are what a diagnosis reports,
    and the tree computes them, not the model. NO LLM.

    Each figure carries a LABEL as well as a value, and the label is what makes it citable: a
    decomposition holds eighteen numbers under one handle, so `r1` names none of them and
    `r1:days_per_user.contribution_share` names exactly one. Pinning the labels rather than only
    the values is not tidiness — when the pairs arrived, this test kept asserting on bare floats
    and failed silently at the commit that introduced them."""
    from agent.tools import _decomposition_values
    from semantic.tree import MetricTree

    sem = SemanticLayer(open_warehouse())
    out = MetricTree(sem).explain_change("weekly_value_moments", "prev_week", "last_week")
    pairs = _decomposition_values(out)
    named = dict(pairs)

    assert named["value_a"] == out["value_a"] and named["value_b"] == out["value_b"], \
        "the levels are governed"
    assert named["pct_change"] == out["pct_change"], \
        "the change is what 'why did it move' answers with"
    for child in out["identity_decomposition"]:
        ref = f"{child['child']}.contribution_share"
        assert named.get(ref) == child["contribution_share"], \
            f"{child['child']}'s share is computed by the tree, not by the model, and is cited as {ref}"
    # A result carrying values is addressable — the loop hands it a handle by that rule alone,
    # so this is what makes `sources` able to name a decomposition.
    assert pairs, "no values means no handle means the tree stays invisible to provenance"
    assert len(named) == len(pairs), "a duplicate label would make a citation ambiguous"


def test_a_driver_citation_is_typed_correlational_by_the_tree():
    """The label the tool writes and the name the audit reads must be the same name. NO LLM.

    They were not, and nothing noticed, because both sides were tested against labels typed by
    hand. Every influence edge in this tree hangs off a component rather than the root, so a
    decomposition from the top writes `active_users.new_signups.pct_change` — three segments. The
    audit read the FIRST one, got `active_users`, and never matched the influence set: a claim
    resting on driver evidence was typed `exact`, and the published count of hedged claims read 0.

    So this test builds its citation from what `_decomposition_values` actually emits rather than
    from a string in the test file. A rename on either side now fails here."""
    from agent.tools import _decomposition_values
    from evidence import CORRELATIONAL, EXACT, audit
    from semantic.tree import MetricTree

    tree = MetricTree(SemanticLayer(open_warehouse()))
    context = tree.audit_context()
    out = tree.explain_change("weekly_value_moments", "prev_week", "last_week")
    pairs = _decomposition_values(out)
    step = {"tool": "decompose_change", "handle": "r1", "error": False,
            "args": {"node": "weekly_value_moments"},
            "result_labels": [k for k, _ in pairs], "result_values": [v for _, v in pairs]}

    soft = context["influence_children"]
    assert soft, "the tree carries influence edges, or this test proves nothing"
    driver = next(k for k, _ in pairs if k.rpartition(".")[0].rpartition(".")[2] in soft)
    assert driver.count(".") >= 2, \
        f"{driver!r} should be nested under the component it drives; the flat shape hid the bug"

    a = audit([{"text": "a driver moved", "sources": [f"r1:{driver}"]}], [step], **context)
    assert a["findings"][0]["strength"] == CORRELATIONAL, \
        f"citing {driver!r} rests on an influence edge, so the tree types it correlational"
    assert a["correlational"] == 1

    # …and an identity child is exact, so the distinction is a reading of the tree rather than a
    # blanket downgrade of anything with a dot in it.
    exact_ref = f"{out['identity_decomposition'][0]['child']}.pct_change"
    b = audit([{"text": "a component moved", "sources": [f"r1:{exact_ref}"]}], [step], **context)
    assert b["findings"][0]["strength"] == EXACT and b["correlational"] == 0


def test_the_judge_is_shown_what_the_tree_vouches_for():
    """A claim about CAUSE needs the tree, and the judge was never shown it.

    Given a metric, its SQL and the analyst's filters, "the drop was driven by frequency" and
    "driven by EMEA" look alike — one is arithmetic the tree computed, the other names a
    geographic slice that is not a node at all. This is the third governed thing the tree carried
    that no guardrail could see, after the North Star's value and its eighteen figures.

    The two edge kinds differ in KIND: identity is exact and may be asserted, influence is
    correlational and may only be suggested with the evidence it carries — including evidence
    AGAINST it, which is what this tree's one influence edge records. NO LLM: this pins that both
    kinds reach the judge, labelled, and that the fingerprint moves when the rules do."""
    from agent.grounding import build_grounding
    from agent.guardrails import judge
    from agent.guardrails.after import causal_record

    con = open_warehouse(create_star_views=True)
    grounding = build_grounding(con, 7, guardrails=LADDER[9])
    run = type("R", (), {"grounding": grounding})()
    decomposed = [{"tool": "explain_change", "error": False,
                   "args": {"node": "weekly_value_moments",
                            "period_a": "prev_week", "period_b": "last_week"}}]

    record = causal_record(run, decomposed)
    assert "IDENTITY" in record and "INFLUENCE" in record, "both edge kinds must be labelled"
    assert "days_per_user" in record and "largest contributor" in record, \
        "the identity child the tree computed as the driver must be named"
    assert "confidence: low" in record and "correlation is ~0" in record, \
        "an influence edge must carry its evidence — including evidence against it"
    assert "not a driver OF it" in record, "a breakdown is not a driver, and the judge must know"

    # No decomposition, no causal claim to grade — the judge must not invent a requirement.
    assert causal_record(run, [{"tool": "query_metric", "args": {"metric": "mrr"},
                                "error": False}]) == ""
    assert causal_record(run, []) == ""

    # The rules are part of the judge's behaviour-defining surface, so a stored validation goes
    # stale when they change — the property the whole fingerprint exists for.
    for role in ("the_answer", "evidence"):
        assert judge._CAUSAL in judge.verify_system(role), \
            f"causal grading must apply to the {role} branch too: a lookup can name a driver"


def test_every_measured_field_reaches_the_row():
    """Whatever an analysis will need later has to be computable from the stored rows, and a
    field that is carried but never written is worse than one that was never added: it reads as
    measured and is null.

    `iterations` was that. It is set on the Answer at every exit, threaded through the
    orchestrator, and then omitted by the row writer — so the step count a compounding-error
    analysis needs was null in all 684 rows of the grounding ladder, and model calls had to be
    re-derived from `turns` instead.

    This holds the writer to the Answer's own field list, so the next one cannot be dropped
    silently. NO LLM."""
    import dataclasses

    from agent.loop import Answer

    src = (Path(__file__).resolve().parent.parent / "evals" / "runner.py").read_text()
    carried = {f.name for f in dataclasses.fields(Answer)}
    # Fields the row deliberately renames, derives, or leaves out — each with its reason, so
    # "not written" is always a decision on the record rather than an oversight.
    ELSEWHERE = {
        "question", "rung", "model",        # written from the case/config, not the Answer
        "answer", "explanation", "outcome", "reason", "missing",   # written explicitly above
        "abstained",                        # the grader's, not the Answer's mirror of it
        # Recorded by the EXPERIMENT runner, not this one: it is only populated under
        # `run_agent(record_context=True)`, which experiments/engine.py sets and evals/runner.py
        # does not. It is written at experiments/engine.py:1108, so the field is measured and
        # stored — just not on this row.
        "context",
    }
    for name in sorted(carried - ELSEWHERE):
        assert f'"{name}"' in src, (
            f"Answer.{name} is measured but never written to the row — a null field that reads "
            f"as a measurement. Write it, or delete it from Answer.")


def test_a_filter_that_restates_the_definition_narrows_nothing():
    """The judge is shown the analyst's added filters and told to treat an unrequested one as a
    narrowing. Sound — and wrong when the filter narrows nothing.

    Asking active_users to exclude internal accounts returns 886 either way, because the
    definition already excludes them. Asking the same of value_moments returns 3,642 instead of
    3,785, because that one does not. The judge cannot tell the two apart without reading the
    definition, and it refused five correct answers on the difference in one run of 171.

    DEFINITIONALLY redundant, not coincidentally so, and the direction matters: a filter named
    redundant must be unable to change a number for ANY data. new_signups carries no default
    filter, so excluding internal accounts is a real restriction even in a week where no internal
    account signed up. NO LLM."""
    sem = SemanticLayer(open_warehouse(create_star_views=True))
    off = {"is_internal": False}

    # Already in the definition -> redundant.
    for metric in ("active_users", "power_users", "days_per_user", "activation_rate",
                   "moments_per_day", "real_value_moments"):
        assert sem.redundant_filters(metric, off), f"{metric} already excludes internal accounts"

    # Not in the definition -> a real restriction, even where the data makes it a no-op today.
    for metric in ("value_moments", "new_signups"):
        assert not sem.redundant_filters(metric, off), \
            f"{metric} has no such default; the filter restricts and the judge must see it"

    # The soundness property: redundant implies the number cannot move.
    for metric in ("active_users", "power_users", "days_per_user"):
        assert sem.redundant_filters(metric, off)
        plain = sem.scalar(metric, period="last_week")
        filtered = sem.scalar(metric, filters=off, period="last_week")
        assert abs(plain - filtered) < 1e-9, f"{metric} called redundant but the value moved"
    # ...and where it is NOT redundant, the number really does move.
    assert abs(sem.scalar("value_moments", period="last_week")
               - sem.scalar("value_moments", filters=off, period="last_week")) > 1

    # Only booleans that MATCH the definitional value count.
    assert not sem.redundant_filters("active_users", {"is_internal": True}), \
        "the opposite value is a real (and empty) restriction, not a restatement"
    assert not sem.redundant_filters("active_users", {"region": "EMEA"})
    assert sem.redundant_filters("active_users", None) == {}
    assert sem.redundant_filters("no_such_metric", off) == {}

    # And the judge is actually told, through the channel that already exists for
    # "the layer did this, not the analyst".
    notes = verifier.governed_notes({"metric": "active_users", "filters": off}, sem)
    assert any("ALREADY applies it" in n for n in notes), notes
    assert not any("ALREADY applies it" in n
                   for n in verifier.governed_notes({"metric": "value_moments", "filters": off}, sem))


def test_the_refusal_vocabulary_is_defined_where_it_is_used():
    """A typed protocol whose codes the model must infer from identifiers is a spelling test.

    The refuse tool offered twelve bare strings and no descriptions. Across 180 correct refusals
    the model named a different code than the question expected 49% of the time, and picked
    `other` — the catch-all — 26 times over a specific code that existed and fitted.

    So the meanings live beside the codes, and the tool renders them: the vocabulary the model
    reads and the one the grader scores cannot drift apart. NO LLM."""
    from agent.outcomes import REASON_MEANINGS, REFUSAL_REASONS
    from agent.tools import _REFUSE

    assert list(REASON_MEANINGS) == REFUSAL_REASONS, "one list, or the two can disagree"
    spec = _REFUSE["input_schema"]["properties"]["reason"]
    assert spec["enum"] == REFUSAL_REASONS
    for code, meaning in REASON_MEANINGS.items():
        assert meaning and code in spec["description"], f"{code} reaches the model undocumented"
        assert meaning in spec["description"], f"{code}'s meaning is not rendered"

    # The two codes that describe what came BACK rather than why the question is unanswerable
    # must say when they are the wrong choice — `result_empty` was given 32 times where a
    # specific cause was expected.
    assert "ONLY when you cannot say why" in REASON_MEANINGS["result_empty"]
    assert "Prefer a specific reason" in REASON_MEANINGS["other"]


def test_a_check_that_cannot_run_says_so():
    """`check_causal_evidence` answered "NO — no causal evidence is encoded" when there was no
    metric tree to check against. That is a claim about the world; the truth is "I cannot tell".
    A model reading NO refuses for no_causal_evidence on grounds it does not have.

    The absence of the instrument is not evidence of absence. NO LLM."""
    from agent.tools import Toolbox

    con = open_warehouse(create_star_views=True)
    sem = SemanticLayer(con)
    no_tree = Toolbox(con, 3, sem, None, LADDER[9])
    out = no_tree.dispatch("check_causal_evidence",
                           {"driver": "reminder_open_rate", "outcome": "days_per_user"}).content
    assert out.startswith("UNKNOWN"), f"a check that cannot run must not answer NO: {out[:60]}"
    assert "not evidence that no link exists" in out

    with_tree = Toolbox(con, 7, sem, MetricTree(sem), LADDER[9])
    real = with_tree.dispatch("check_causal_evidence",
                              {"driver": "reminder_open_rate", "outcome": "days_per_user"}).content
    assert not real.startswith("UNKNOWN"), "with a tree it must give a real verdict"
    assert "confidence: low" in real, "and carry the edge's confidence, not just yes/no"

    # THE SIBLING CASE, which this test did not cover for a year. A missing TREE and a missing
    # TERM are the same absence: `pricing_change` is not a node, so the tree has nothing that
    # could show a link either way. It answered "NO — no encoded edge", and 5 of 40 answers to
    # u_pricing_cause duly said "No — the pricing change did not cause it".
    unmodelled = with_tree.dispatch("check_causal_evidence",
                                    {"driver": "pricing_change",
                                     "outcome": "value_moments"}).content
    assert unmodelled.startswith("UNKNOWN"), f"an unmodelled term must not answer NO: {unmodelled[:60]}"
    assert "'pricing_change' is not a modelled entity" in unmodelled, (
        "and must name WHICH term it does not model — that tells an analyst what the layer needs, "
        "where 'no encoded edge' invites them to conclude there is no effect")


def test_the_causal_check_has_four_states_not_two():
    """A boolean conflated the two absences that must never be conflated, and contradicted itself
    on a third case: `causal_evidence('new_signups', 'active_users')` returned False alongside
    prose describing the edge and its confidence, which `_verdict` rendered as
    "NO — weak, correlational evidence…". The model reads the first word."""
    from agent.tools import Toolbox
    from semantic.tree import Causality

    con = open_warehouse(create_star_views=True)
    sem = SemanticLayer(con)
    tree = MetricTree(sem)
    tb = Toolbox(con, 7, sem, tree, LADDER[9])

    cases = {
        # an edge exists and is weak — evidence, and not proof
        ("new_signups", "active_users"): (Causality.CORRELATIONAL, "CORRELATIONAL"),
        ("reminder_open_rate", "days_per_user"): (Causality.CORRELATIONAL, "CORRELATIONAL"),
        # both modelled, nothing joins them: a FINDING, weak evidence of no link
        ("moments_per_day", "new_signups"): (Causality.NOT_ENCODED, "NOT ENCODED"),
        # a term outside the model: an ADMISSION, carrying no evidence either way
        ("pricing_change", "value_moments"): (Causality.UNKNOWN, "UNKNOWN"),
    }
    for (driver, outcome), (want, word) in cases.items():
        got, _ = tree.causal_evidence(driver, outcome)
        assert got == want, f"{driver} -> {outcome}: {got} (wanted {want})"
        rendered = tb.dispatch("check_causal_evidence",
                               {"driver": driver, "outcome": outcome}).content
        assert rendered.startswith(word), f"{driver} -> {outcome} renders {rendered[:40]!r}"

    # the two absences must not render alike — that identity is the whole bug
    assert _CAUSAL_DISTINCT(tb, "moments_per_day", "pricing_change", "new_signups")


def _CAUSAL_DISTINCT(tb, modelled, unmodelled, outcome) -> bool:
    a = tb.dispatch("check_causal_evidence", {"driver": modelled, "outcome": outcome}).content
    b = tb.dispatch("check_causal_evidence", {"driver": unmodelled, "outcome": outcome}).content
    return a.split(" —")[0] != b.split(" —")[0]


def test_a_rung_is_what_it_declares_not_what_its_number_implies():
    """The rung number used to mean two things — a position on the ladder, and the capability set
    at it — which agreed only while every rung was a superset of the one below. Rung 7 breaks that
    on purpose: it holds the metric tree WITHOUT the advisory blocks, so it carries less than rung
    6 while sorting after it.

    So nothing may infer a capability from `rung >= n`. This pins the table against the conditions
    it replaced (rungs 1-6 must be untouched) and against the one rung that proves numbers no
    longer order capabilities."""
    from agent.rungs import RUNGS, capabilities, parse_rung

    for n in (1, 2, 3, 4, 5, 6):
        c = capabilities(n)
        assert (c.star, c.semantic, c.examples, c.knowledge, c.tree) == \
               (n >= 2, n >= 3, n >= 4, n >= 5, n >= 6), f"rung {n} no longer matches the ladder"

    seven, six = capabilities(7), capabilities(6)
    assert seven.semantic and seven.tree, "rung 7 is the governed pair"
    assert not seven.advisory(), "rung 7 is governed-only; examples and the knowledge base are prose"
    assert six.advisory(), "rung 6 is the one that carries both kinds"
    # The ladder is not monotonic any more, and that is exactly the point: 7 sorts after 6 and
    # holds strictly less. Any code asking `rung >= n` about a capability is wrong from here.
    assert 7 > 6 and (six.knowledge and not seven.knowledge), \
        "a higher rung number no longer implies a superset — ask the table, never compare numbers"

    assert parse_rung("7") == 7 and parse_rung("3") == 3
    for bad in ("9", "banana", "3.5"):
        try:
            parse_rung(bad)
            raise AssertionError(f"{bad!r} is not a defined rung and must not parse")
        except ValueError:
            pass
    # The names travel with the number, so a chart printing "rung 7" prints the correction too.
    assert "governed only" in RUNGS[7].name


def test_the_judge_settles_what_the_number_is_doing_before_judging_it():
    """The five checks compare the metric against the QUESTION's wording, which is the right test
    only when the number IS the answer. Shown a bare 3785 against "weekly value moments dropped —
    what caused it?", the judge could read it only as a proposed cause, observe correctly that a
    count is not a cause, and reject: 19 of its 37 rejections in the R9 run, every diagnostic and
    every keywords case among them.

    So the role is asked FIRST and is required, and the answering model does not get to declare
    it — a self-declared role is unfalsifiable and would be a one-word exit from the strict test,
    while the judge's is scoreable against labels exactly as `mismatch` is. NO LLM: this pins the
    contract (what is asked, what is required, what a silent judge defaults to), not the ruling."""
    from agent.conversation import ToolCall, Turn
    from agent.guardrails import judge

    assert judge._ROLE_REPORT["input_schema"]["properties"]["value_role"]["enum"] \
        == ["the_answer", "evidence"]

    # The two branches are what make the role mean anything: the three checks that compare the
    # metric with the QUESTION's wording cannot run on a figure that is merely cited.
    answer_checks, evidence_checks = judge.verify_system(), judge.verify_system("evidence")
    for absent in ("KIND", "DEFINITION", "SEGMENT"):
        assert f"{absent} —" not in evidence_checks, \
            f"{absent} compares the metric with the question, which a supporting figure never answers"
    assert all(f"{present} —" in evidence_checks for present in ("THING", "SCOPE"))
    assert answer_checks != evidence_checks and judge._STANCE["skeptical"] in evidence_checks, \
        "the stance is shared across roles, or it stops being one treatment"

    class _Model:
        """Answers the role call and the verdict call from one script, so the test sees the two
        as the judge issues them."""

        def __init__(self, role, verdict):
            self.role, self.verdict, self.systems = role, verdict, []

        def respond(self, convo, tools, **kw):
            self.systems.append(convo.system)
            name = tools[0]["name"]
            args = self.role if name == "report_role" else self.verdict
            return Turn(tool_calls=[ToolCall("v1", name, args)] if args else [])

    call = dict(question="why did it drop?", metric_name="m", metric_def={}, sql="SELECT 1",
                result_value=1, claim_value=1, claim_text="It fell because frequency dropped.")
    m = _Model({"value_role": "evidence"}, {"answers_question": False, "mismatch": "thing",
                                            "reason": "r"})
    j = judge.verify_trajectory(m, **call)
    assert (j.answers_question, j.mismatch, j.value_role) == (False, "thing", "evidence")
    assert m.systems == [judge._ROLE_SYSTEM, evidence_checks], \
        "the role is classified first, and its answer picks the checks the verdict call runs"

    # An answer with no sentence behind it (verifier_eval's synthetic trajectories) skips the
    # classifier entirely and gets the strict checks — what every published run did.
    m = _Model(None, {"answers_question": True, "mismatch": "none", "reason": ""})
    assert judge.verify_trajectory(m, **{**call, "claim_text": None}).value_role == "the_answer"
    assert m.systems == [answer_checks], "no sentence to classify, so no classifier call"

    # Neither silence is read as the lenient outcome: the judge cannot veto (it is refuse-only),
    # and a role that failed to arrive falls back to the strict test, never to evidence.
    silent = judge.verify_trajectory(_Model(None, None), **call)
    assert (silent.answers_question, silent.value_role) == (True, "the_answer")


def test_the_judge_stance_is_a_treatment_with_two_levels():
    """The judge fires on 52% of the answers it sees, and its opening paragraph tells it to hunt
    for a reason to reject and pass only if it fails. That wording resists sycophancy — a plain
    "is this correct?" judge agrees with whatever it is shown — but it is also a known
    over-rejection instruction. Which effect dominates is measurable, so it is a treatment.

    The ABSOLUTE fingerprint is pinned by tests/golden/model_surface.txt, which renders a prompt
    change as a reviewable diff. It was pinned here too, as a bare hash in an assert; one
    deliberate edit then failed in two places, and the copy here could only say "it changed".
    This owns the RELATIONSHIPS instead — which are what make the stance a treatment — so it
    stays meaningful across every deliberate edit to the judge."""
    import os

    from agent.guardrails import judge

    before = os.environ.get("VERIFIER_STANCE")
    try:
        os.environ.pop("VERIFIER_STANCE", None)
        assert judge.stance_name() == "skeptical", \
            "the shipped stance must be what an unset environment runs, or stored runs are unlabelled"
        os.environ["VERIFIER_STANCE"] = "skeptical"
        skeptical, skeptical_fp = judge.verify_system(), judge.prompt_fingerprint()
        os.environ["VERIFIER_STANCE"] = "even_handed"
        even = judge.verify_system()
        assert judge.prompt_fingerprint() != skeptical_fp, "a stance must change the fingerprint"
        # only the stance differs; the five checks are shared, or the comparison measures two things
        assert skeptical.split("Ground EVERY")[1] == even.split("Ground EVERY")[1]
        os.environ["VERIFIER_STANCE"] = "nope"
        try:
            judge.stance_name()
            raise AssertionError("an unknown stance must fail loudly, not fall back")
        except ValueError:
            pass
    finally:
        os.environ.pop("VERIFIER_STANCE", None)
        if before is not None:
            os.environ["VERIFIER_STANCE"] = before


def test_a_served_number_must_be_a_rounding_of_a_governed_one():
    """governed_numbers asks whether the served number IS a governed result. The only difference it
    should forgive is display rounding — 2685.08 for 2685.0766666.

    The old tolerance band failed at both ends. Its 0.5 absolute floor is huge for a ratio, so
    days_per_user 2.27 and 2.69 (two different weeks) counted as the same number and the checks
    validated whichever they reached first. Its 0.5% term is huge for a count, so 371 and 372
    matched — which the docstring explicitly promised they would not."""
    from evidence import num_match

    for a, b in [(2685.08, 2685.0766666), (886, 886.0), (5648, 5648), (0.53, 0.5299999999)]:
        assert num_match(a, b), f"{a} is a rounding of {b} and must match"
    for a, b in [(2.27088, 2.68852),        # two weeks of the same ratio metric
                 (371, 372),                # adjacent counts
                 (0.53, 0.99),              # two different shares
                 (2690, 2685.0766),         # rounded to significant figures, not a governed value
                 (886, 18866)]:
        assert not num_match(a, b), f"{a} is NOT a rounding of {b} and must not match"

    # THE LADDER STARTS AT ONE DECIMAL PLACE. Whole-number rounding is the same forgiveness
    # everywhere on the number line and the layer's values are not: on a count it moves 4200.6
    # to 4201 and loses nothing, on a rate it collapses everything under a half to zero. A
    # declared 0 matched any rate below 50% and a declared 1 matched 0.6 — neither is a rounding
    # in any sense a reader would accept, and every rate the layer produces lives in that range.
    for a, b in [(0, 0.4), (0, 0.49), (0, 0.5), (1, 0.6), (1, 1.4), (0, -0.4)]:
        assert not num_match(a, b), (
            f"{a} must not match {b}: whole-number rounding is not forgiven, because for a rate "
            f"it is not rounding")
    # …and the cases k=0 was there for never needed it — an integer already equals itself.
    for a, b in [(4200, 4200.0), (0, 0), (0, 0.0), (1, 1.0)]:
        assert num_match(a, b), f"{a} and {b} are the same number"


def test_metrics_conform_to_ontology():
    """Every metric's entity + segment must be a value the ontology declares, so the metric
    definitions stay in one governed vocabulary."""
    con = open_warehouse()
    sem = SemanticLayer(con)
    entities, segments = set(sem.ontology["entities"]), set(sem.ontology["segments"])
    assert "habits" in entities, "ontology must be a superset of the metrics (habits has no metric)"
    for name, m in sem.metrics.items():
        assert m.get("entity") in entities, f"{name}: entity {m.get('entity')!r} not in ontology"
        assert m.get("segment") in segments, f"{name}: segment {m.get('segment')!r} not in ontology"


def test_output_validation_catches_degenerate_values():
    """The check on the returned value (not the metric selection): an empty/null result
    narrated as a number, a share out of range, or a negative count -> refuse."""
    con = open_warehouse()
    sem = SemanticLayer(con)
    # the governed query returned no value, but the model answered a number -> result_empty
    empty_steps = [_qm("active_users", None, period="last_week")]
    v = verifier.verify_answer(sem, "How many active users last week?", "5", empty_steps,
                                            source_metric="active_users", declared_value=5)
    assert not v.allowed and v.reason == "result_empty", v
    # a share metric returning 150 is impossible
    share_steps = [_qm("reminder_open_rate", 150)]
    v2 = verifier.verify_answer(sem, "What is the reminder open rate?", "150", share_steps,
                                              source_metric="reminder_open_rate", declared_value=150)
    assert not v2.allowed and v2.reason == "implausible_value", v2
    # a normal value passes sanity
    good_steps = [_qm("active_users", 886, period="last_week")]
    v3 = verifier.verify_answer(sem, "How many active users last week?", "886", good_steps,
                                     source_metric="active_users", declared_value=886)
    assert v3.allowed


def test_value_resolver():
    """Free-text filter values resolve to the governed member or refuse; the compiler
    canonicalises a resolvable value and rejects an unknown one."""
    sem = SemanticLayer(open_warehouse())
    assert sem.resolve_member("platform", "iPhone") == "ios"
    assert sem.resolve_member("region", "americas") == "Americas"        # true synonym resolves
    assert sem.resolve_member("plan", "yearly") == "annual"
    assert sem.resolve_member("channel", "paid search") == "paid_search"
    assert sem.resolve_member("platform", "Blackberry") is None          # no governed member
    # A hyponym (sub-region) is NOT a synonym: it must refuse, not widen to the parent.
    assert sem.resolve_member("region", "North America") is None
    assert sem.resolve_member("region", "europe") is None
    assert sem.resolve_member("is_internal", False) is False             # no vocab -> pass through
    # the compiler rewrites the value to its canonical member ...
    sql = sem.compile("active_users", filters={"platform": "iPhone"}, period="last_week")
    assert "platform = 'ios'" in sql and "iPhone" not in sql
    # ... and refuses an unresolvable one rather than querying an empty slice
    try:
        sem.compile("active_users", filters={"platform": "Blackberry"})
        raise AssertionError("expected SemanticError")
    except SemanticError:
        pass
    # below the resolve rung (resolve=False) the raw value is used as-is — the pre-R5 bug
    raw = sem.compile("active_users", filters={"platform": "iPhone"}, resolve=False)
    assert "platform = 'iPhone'" in raw


def test_governed_numbers_allows_comparison_and_refuses_composition():
    """R7: you may COMPARE governed numbers; you may not COMPOSE new ones.

    The distinction cannot be drawn from the arithmetic. `ARR = mrr x 12` and `value moments fell
    11.9%` are each one operation on a governed result, so a rule about the operation permits both
    or neither. It is drawn from what the result CLAIMS TO BE: comparing one metric across two
    scopes leaves its definition untouched — only the filter moved — while combining two different
    metrics invents a measure nothing defines.

    Its predecessor accepted only case (a), and restricted that to one tool. It refused the
    diagnostic tier twelve times in fifteen at rung 7, where the tree had computed every figure.
    NO LLM."""
    con = open_warehouse()
    sem = SemanticLayer(con)
    check = lambda text, value, steps, metric=None, sources=(): verifier.verify_answer(  # noqa: E731
        sem, "q", text, steps, source_metric=metric, declared_value=value, sources=sources,
        run_output_validation=False, run_governed_numbers=True)

    steps = [_qm("new_signups", 444, start="2026-06-01", end="2026-06-30"),
             _qm("activation_rate", 0.529, start="2026-06-01", end="2026-06-30")]
    assert check("444", 444, steps, "new_signups").allowed, "a governed result is case (a)"
    # A rate served as a percentage is the same governed number, differently rendered.
    assert check("52.9%", 52.9, steps, "activation_rate").allowed, "x100 is display, not derivation"
    # 235 = 444 x 0.529 combines TWO DIFFERENT metrics -> a quantity nothing defines.
    composed = check("235", 235, steps)
    assert not composed.allowed and composed.reason == "no_governed_definition", \
        "a count times a rate invents a measure and must refuse"

    # Two results of the SAME metric: every comparison between them is governed — WHEN THE
    # ANSWER NAMES BOTH. The handles turn the check into a lookup over two values instead of a
    # search over every value the metric ever returned.
    weeks = [_qm("value_moments", 4307, handle="r1", period="prev_week"),
             _qm("value_moments", 3785, handle="r2", period="last_week")]
    for value, what in ((3785, "the level"), (-522, "the difference"),
                        (-12.12, "the percent change"), (0.8788, "the ratio")):
        assert check(str(value), value, weeks, "value_moments", ("r1", "r2")).allowed, \
            f"{what} between two value_moments results is a comparison, not a composition"

    # …and an UNNAMED comparison is refused. This is the enforcement, not a side effect: while
    # one slot held the provenance a comparison had nothing to cite, so the check searched every
    # ordered pair of the metric's values for one that fit — ~1,440 candidates in a live run,
    # and a hand-composed DAU/WAU ratio matched one of them. The level still passes unnamed
    # because it IS a governed result; only the relation needs its operands.
    assert check("3785", 3785, weeks, "value_moments").allowed, "a level needs no operands"
    for value, what in ((-522, "difference"), (-12.12, "percent change"), (0.8788, "ratio")):
        unnamed = check(str(value), value, weeks, "value_moments")
        assert not unnamed.allowed and unnamed.reason == "no_governed_definition", \
            f"an unnamed {what} cannot be accounted for and must refuse"

    # Naming ONE side of a two-sided relation is not enough either.
    half = check("-522", -522, weeks, "value_moments", ("r1",))
    assert not half.allowed, "one handle cannot anchor a comparison"

    # (c) Totalling the periods of ONE result — governed only where the layer says the metric
    # composes across periods. A live run asked for a quarter at monthly grain, added the two
    # months, and got the gold figure exactly; refusing it was the rule failing to distinguish
    # summing moments from summing distinct people.
    months = [{"tool": "query_metric", "handle": "r1", "result": "", "result_values": [1852.0, 2000.0],
               "args": {"metric": "value_moments", "time_grain": "month",
                        "start": "2026-05-01", "end": "2026-06-30"}}]
    assert check("3852", 3852, months, "value_moments", ("r1",)).allowed, \
        "value_moments sums moments, so its months total"
    # Same shape, a metric that counts distinct users: anyone active in both months would be
    # counted twice, so the total is not a governed figure however arithmetically tidy.
    people = [{"tool": "query_metric", "handle": "r1", "result": "", "result_values": [500.0, 600.0],
               "args": {"metric": "active_users", "time_grain": "month",
                        "start": "2026-05-01", "end": "2026-06-30"}}]
    dup = check("1100", 1100, people, "active_users", ("r1",))
    assert not dup.allowed, "count(distinct) does not compose across periods"
    # A BREAKDOWN's rows differ by dimension as well as by period, so their total is a different
    # claim — not licensed by additivity over time.
    split = [{"tool": "query_metric", "handle": "r1", "result": "", "result_values": [1852.0, 2000.0],
              "args": {"metric": "value_moments", "time_grain": "month", "group_by": ["region"],
                       "start": "2026-05-01", "end": "2026-06-30"}}]
    assert not check("3852", 3852, split, "value_moments", ("r1",)).allowed, \
        "a grouped result is not a time series"

    # A rate rendered as a percentage must match the governed rate. Multiplying by 100 moves
    # the last bits, and num_match's rounding ladder asks whether one number is the ROUNDING of
    # the other — false when both carry full precision — so this failed every rung and refused
    # three diagnostic answers whose figures the tree had computed.
    pct = [_qm("days_per_user", 2.27, period="last_week")]
    tree_pct = {"tool": "explain_change", "args": {"node": "days_per_user"}, "error": False,
                "result": "", "result_values": [-0.1644119797793533]}
    assert check("-16.44%", -16.44119797793533, [tree_pct]).allowed, \
        "a governed rate x 100 is the same number, differently displayed"
    assert not check("2.69", 2.69, pct).allowed, "but a different week is a different number"

    # The tree's own figures are governed results, whatever tool produced them — the check that
    # asked `tool == "query_metric"` could not see them and refused the whole decomposition.
    tree_step = {"tool": "explain_change", "args": {"node": "weekly_value_moments"},
                 "error": False, "result": "", "result_values": [4133.0, 3642.0, -0.1188, 1.42025]}
    assert check("-11.9%", -11.88, [tree_step]).allowed, "a tree-computed change is governed"
    assert check("142%", 1.42025, [tree_step]).allowed, "so is a contribution share"
    assert not check("999", 999, [tree_step]).allowed, "but an unaccounted number is still refused"


def test_verifier_skips_prose_answers():
    """The output checks apply to a NUMERIC answer, identified by the typed `value` field — not by
    parsing the text. A prose judgement or a diagnostic narrative leaves `value` unset
    (declared_value=None), so the checks stand down even with a source_metric declared and the
    metric's number sitting in the prose."""
    con = open_warehouse()
    sem = SemanticLayer(con)
    steps = [_qm("value_moments", 67132, period="all")]
    # a prose health verdict: no declared value -> skip
    v = verifier.verify_answer(sem, "Is the app healthy?", "No — mixed early-warning signals",
                                    steps, source_metric="value_moments")
    assert v.allowed, "prose answer (no declared value) must skip the output checks"
    # a diagnostic narrative that literally contains 67132: still skipped, because value is unset
    narrative = "No; value moments were 67132 all-time but active users rose from 836 to 886"
    v2 = verifier.verify_answer(sem, "What happened?", narrative, steps, source_metric="value_moments")
    assert v2.allowed, "diagnostic narrative (no declared value) must skip the output checks"


def test_governed_segment_excludes_test_members():
    """A 'test' channel is governed data, and the real_acquisition segment enforces the
    exclusion at query time — so excluding test channels is a layer guarantee, not a
    knowledge-base note the model must remember and apply."""
    con = open_warehouse()
    sem = SemanticLayer(con)
    assert sem.test_members("channel") == ["partnerships"]      # the test integration, flagged in data
    assert "real_acquisition" in sem.segment_names()

    sql = sem.compile("new_signups", start="2026-06-01", end="2026-06-30", segment="real_acquisition")
    assert "channel NOT IN ('partnerships')" in sql
    _, _, seg = sem.query_with_sql("new_signups", start="2026-06-01", end="2026-06-30", segment="real_acquisition")
    _, _, allc = sem.query_with_sql("new_signups", start="2026-06-01", end="2026-06-30")
    assert seg[0][0] < allc[0][0]                                # the segment really drops rows (453 < 553)

    try:
        sem.compile("new_signups", segment="not_a_segment")
        raise AssertionError("expected SemanticError for an unknown segment")
    except SemanticError:
        pass


def test_region_availability_is_read_from_the_dimension():
    """Coverage windows live on the region dimension member (region.APAC.available_from),
    not a separate coverage.regions list. A member is a synonym list OR a dict with
    metadata; both resolve, and the launch window still gates by region and by country."""
    con = open_warehouse()
    sem = SemanticLayer(con)
    # a dict member still resolves by canonical + synonym; a shorthand-list member too
    assert sem.resolve_member("region", "asia pacific") == "APAC"
    assert sem.resolve_member("region", "americas") == "Americas"
    assert sem.resolve_member("region", "North America") is None      # hyponym still refused
    # the launch window gates a pre-launch period, and a country filter inherits it
    assert sem.in_coverage("2026-04-01", "2026-06-30", region="APAC")[0] is False
    assert sem.in_coverage("2026-05-01", "2026-06-30", region="APAC")[0] is True
    assert sem.in_coverage("2026-04-01", "2026-06-30", country="PH")[0] is False   # PH -> APAC
    assert sem.in_coverage("2026-04-01", "2026-06-30", region="Americas")[0] is True  # no window
    # and it is no longer read from a coverage.regions block
    assert "regions" not in sem.governance.get("coverage", {})


def test_ladder_presets_reproduce_the_rung_thresholds():
    """The flag refactor must not move a single existing result: LADDER[n] has to switch on
    exactly the guardrails the old `rrung >= N` comparisons did, for every rung."""
    from agent.guardrails import LADDER
    for n in range(10):
        g = LADDER[n]
        assert g.abstain is (n >= 1) and g.check_tools is (n >= 2)
        assert g.coverage_check is (n >= 3) and g.tool_restriction is (n >= 4)
        assert g.resolve is (n >= 5) and g.transparency is (n >= 6)
        assert g.governed_numbers is (n >= 7) and g.output_validation is (n >= 8)
        assert g.trajectory_verify is (n >= 9)
        assert g.label() == f"R{n}"


def test_ablation_cell_is_expressible_and_incoherent_cells_are_named():
    """The point of the refactor: a leave-one-out cell exists in the flag space (no single
    rrung can express it), is self-labelling so a stored row says what produced it, and the
    cells that measure a DIFFERENT system are named rather than silently reported."""
    from agent.grounding import build_grounding
    from agent.guardrails import LADDER, incoherent
    con = open_warehouse(create_star_views=True)
    cell = LADDER[9].without("resolve")

    assert cell.trajectory_verify and not cell.resolve      # unreachable from any rrung
    assert cell.label() == "R9-resolve"
    assert incoherent(cell) is None

    # A cell whose guardrail cannot fire is named, not reported. output_validation reads a `value`
    # the answer tool only offers under governed_numbers, so without it the check is inert and its
    # measured contribution would be zero by construction — 365 stored answers sat in such cells.
    inert = LADDER[8].without("governed_numbers")
    assert "output_validation without governed_numbers" in (incoherent(inert) or "")
    # Coherence is a property of the (rung, cell) PAIR: every guardrail above abstention acts on
    # the semantic layer, which rung 1 and 2 do not have.
    assert incoherent(LADDER[9], rung=6) is None and incoherent(LADDER[1], rung=1) is None
    assert "no semantic layer" in (incoherent(LADDER[9], rung=2) or "")
    for bad_rung in (1, 2):
        try:
            build_grounding(con, bad_rung, guardrails=LADDER[4])
            raise AssertionError(f"rung {bad_rung} x R4 built a system with no data path at all")
        except ValueError as exc:
            assert "incoherent grounding" in str(exc)
    tb = Toolbox(con, 6, SemanticLayer(con), None, guardrails=cell)
    assert tb.g.trajectory_verify is True and tb.g.resolve is False

    # single-metric reads result_values, which only governed queries record
    assert incoherent(LADDER[7].without("tool_restriction")) is not None
    # the verifier judges a metric+SQL trajectory, which a hand-composed number lacks
    assert incoherent(LADDER[9].without("governed_numbers")) is not None


def test_the_protocol_is_a_peer_primitive_and_labels_itself():
    """The third axis has to be nameable in a cell, or it is not a treatment the harness controls.

    Framing lived in an environment variable: it changed the model-visible prompt, moved the
    derived-claim rate from 6.9% to 13.6%, and could not be written into a config, put in a
    label, or varied within a run. A framing comparison was therefore two runs at different times
    on a shared API — a confound the harness refuses everywhere else.

    Three properties, and the third is the load-bearing one."""
    from agent.grounding import build_grounding
    from agent.guardrails import LADDER, LADDER_ORDER
    from agent.protocol import ROLE, RULE, Protocol, split_config
    con = open_warehouse(create_star_views=True)
    ALL = Protocol(purpose=True, claims=True, repair=True)

    # 1. the ladder is guardrails ONLY. The declarations used to be rungs 10-12 of it, which said
    #    that declaring sits "above" the verifier — it does not, it is orthogonal to it.
    assert len(LADDER_ORDER) == 9 and set(LADDER_ORDER).isdisjoint({"purpose", "claims", "repair"})

    # 2. the framings are genuinely different treatments — same guardrails, different surface
    rule = build_grounding(con, 7, guardrails=LADDER[9], protocol=ALL)
    role = build_grounding(con, 7, guardrails=LADDER[9],
                           protocol=Protocol(purpose=True, claims=True, repair=True, framing=ROLE))
    assert rule.system != role.system, "the framings must differ, or the arm measures nothing"
    assert rule.fingerprint() != role.fingerprint(), "and the difference must be recorded"
    assert rule.toolbox.specs() == role.toolbox.specs(), \
        "only the WORDING differs — a framing that changed the action space would be a guardrail"

    # 3. the default is silent, so no stored row's config changes meaning
    assert Protocol().framing == RULE and Protocol().label() == ""
    assert rule.guardrails.label() + rule.protocol.label() == "R9/purpose+claims+repair"

    # 4. THE POINT OF THE MOVE: declarations cross with any rung and any guardrail level. The
    #    rung-7/R9 baseline gets 4 answers wrong out of 70, so whether declaring changes accuracy
    #    can only be asked further down — which was inexpressible while these were ladder rungs.
    low = build_grounding(con, 5, guardrails=LADDER[5], protocol=Protocol(claims=True))
    answer = next(s for s in low.toolbox.specs() if s["name"] == "answer")
    assert "claims" in answer["input_schema"]["properties"], \
        "claims must not need governed_numbers — citations resolve against handles, not checks"
    assert "value" not in answer["input_schema"]["properties"], "…and R7's fields stay R7's"
    assert low.guardrails.label() + low.protocol.label() == "R5/claims"

    # 5. every label round-trips, so a reader recovers BOTH primitives from a stored row. Without
    #    this the trace would fail to parse and quietly render "unknown guardrails".
    for cell in ("R0", "R9", "R9-resolve"):
        for proto in (Protocol(), Protocol(claims=True), ALL,
                      Protocol(purpose=True, claims=True, repair=True, framing=ROLE)):
            assert split_config(cell + proto.label()) == (cell, proto), cell + proto.label()

    # 6. the retired rungs still read, because stored rows carry them. R11 is the only one that
    #    ever reached a results file, and it drove the repair loop as well as the claims field.
    assert split_config("R11") == ("R9", ALL)

    for junk in ("casual", "ROLE", None):
        try:
            Protocol(framing=junk)
            raise AssertionError(f"framing={junk!r} was accepted")
        except ValueError:
            pass
    try:
        Protocol(repair=True)      # nothing to repair -> zero by construction, not by evidence
        raise AssertionError("repair without claims was accepted")
    except ValueError:
        pass


def test_the_input_guardrail_blocks_an_ungoverned_dimension_and_value():
    """R5, deterministic (no model call): the coverage check rejects a filter DIMENSION the metric does
    not have, and a filter VALUE that is not a governed member — each with its own coded
    reason, before any query runs. The value case must NOT hand back a member list, or the
    model substitutes a sibling from it (the failure that served Americas for 'North America')."""
    con = open_warehouse()
    sem = SemanticLayer(con)
    tb = Toolbox(con, 6, sem, None, LADDER[5])                 # R5: member resolution on
    window = {"start": "2026-06-01", "end": "2026-06-30"}

    no_dim = input_guardrail.check(sem, tb.g, {"metric": "mrr", "filters": {"region": "Americas"}})
    assert not no_dim.allowed and no_dim.reason == "dimension_not_supported"   # mrr is sliceable by plan only

    bad_value = input_guardrail.check(
        sem, tb.g, {"metric": "active_users", "filters": {"region": "North America"}, **window})
    assert not bad_value.allowed and bad_value.reason == "ungoverned_dimension_value"
    assert "Americas" not in bad_value.detail                 # no substitutable member list leaks back

    # a governed dimension holding a governed member passes both checks
    assert input_guardrail.check(
        sem, tb.g, {"metric": "active_users", "filters": {"region": "Americas"}, **window}).allowed

    # below the resolve rung the value check is off — the pre-R5 hole, kept measurable
    below = Toolbox(con, 6, sem, None, LADDER[4])
    assert input_guardrail.check(
        sem, below.g, {"metric": "active_users", "filters": {"region": "North America"}, **window}).allowed


def test_closing_phase_offers_only_exit_tools():
    """Non-termination: in the closing phase the action space is exit-only, so a run cannot keep
    querying and cannot answer in bare prose — it must end through the typed protocol. Removing
    the choice is structural; nudging the model in prose is not."""
    con = open_warehouse()
    tb = Toolbox(con, 6, SemanticLayer(con), None, LADDER[9])
    full = {s["name"] for s in tb.specs()}
    closing = {s["name"] for s in tb.specs(terminal_only=True)}
    assert {"answer", "refuse", "clarify"} <= full
    assert closing == {"answer", "refuse", "clarify"}
    assert not (closing & {"query_metric", "run_sql", "get_schema", "list_metrics"})


def test_verifier_is_refuse_only():
    """R9 plumbing (no model call): the trajectory verifier can only DOWNGRADE. A passing verdict
    leaves the answer untouched; a failing one converts it into a coded refusal. Because it can
    never turn a bad answer into a good one, adding it cannot introduce a fabrication. It is also
    handed the ANALYST's own call, so it judges the analyst's choices, not the definition."""
    con = open_warehouse()
    sem = SemanticLayer(con)
    steps = [_qm("paying_users", 371)]
    kw = dict(source_metric="paying_users", declared_value=371,
              run_output_validation=False, run_governed_numbers=True)
    seen: dict = {}

    def passing(question, metric, metric_def, args, value, declared_value, claim_text, steps=None):
        seen.update(metric=metric, args=args, declared=declared_value, claim=claim_text)
        return True, "none", ""

    v = verifier.verify_answer(sem, "How many paying users?", "371 people pay us today.", steps,
                                         verify_traj=passing, **kw)
    assert v.allowed is True                            # a passing verdict changes nothing
    assert seen["metric"] == "paying_users" and seen["declared"] == 371
    assert seen["args"] == {"metric": "paying_users"}   # the analyst's call, not the compiled SQL
    # The SENTENCE reaches the judge, not just the number. Shown a bare 371 against "what caused
    # the drop?" the only question available to a judge is "is 371 the answer" — which is how it
    # came to reject every diagnostic answer for citing a count.
    assert seen["claim"] == "371 people pay us today."

    v = verifier.verify_answer(
        sem, "How many paying users?", "371", steps,
        verify_traj=lambda *a: (False, "scope", "answers a different question"), **kw)
    # The judge names its OWN finding rather than casting it onto the model's refusal vocabulary.
    # `scope` used to become `other`, which threw the finding away and then had it graded against
    # a code the judge could not produce. Its codes must stay out of the refuse tool's enum.
    from agent.outcomes import REFUSAL_REASONS, VERIFIER_REASONS
    assert v.allowed is False and v.reason == "verifier_wrong_scope"
    assert v.reason in VERIFIER_REASONS and v.reason not in REFUSAL_REASONS
    assert v.guardrail == "trajectory_verify"


def test_toolbox_wiring_and_rung_gate():
    con = open_warehouse()
    sem = SemanticLayer(con)
    steps = [_qm("active_users", 2100, period="all")]
    q = "How many users do we have in total?"

    # the re-ordered ladder gates each guardrail on its own rung
    assert Toolbox(con, 6, sem, None, LADDER[4]).g.resolve is False
    assert Toolbox(con, 6, sem, None, LADDER[5]).g.resolve is True
    # Each guardrail reaches the Toolbox from the guardrail set it was built with — the set IS the
    # configuration, so there is nothing to mirror onto the Toolbox and nothing to fall out of step.
    for n, guardrail in [(7, "governed_numbers"), (8, "output_validation"), (9, "trajectory_verify")]:
        assert getattr(Toolbox(con, 6, sem, None, LADDER[n - 1]).g, guardrail) is False
        assert getattr(Toolbox(con, 6, sem, None, LADDER[n]).g, guardrail) is True

    # The single-metric check itself, deterministic and with no model needed. The wiring that
    # switches it on for a live run moved to the orchestrator's _Run; what is asserted here is
    # the rung it belongs to, and what it does when it fires.
    def check(rrung, declared):
        return verifier.verify_answer(
            sem, q, str(declared), steps, source_metric="active_users", declared_value=declared,
            run_governed_numbers=LADDER[rrung].governed_numbers,
            run_output_validation=LADDER[rrung].output_validation)

    assert check(7, 2100).allowed, "a direct governed result passes single-metric"
    v = check(7, 999)
    assert not v.allowed and v.reason == "no_governed_definition", \
        "a hand-derived value (matches no governed result) refuses no_governed_definition at R7"
    assert check(6, 999).allowed, "single-metric must be OFF below rrung 7"

    # a prose answer (no typed value) is passed through untouched
    assert verifier.verify_answer(sem, q, "healthy overall", steps, source_metric="active_users",
                                  declared_value=None, run_governed_numbers=True).allowed, \
        "no declared value -> output guardrails stand down"



def test_a_refusal_that_names_a_date_is_not_a_fabrication():
    """Dates are not answers.

    The grader asked `parse_numbers(answer)` — every numeral anywhere in the text — so a decline
    citing the coverage window ("I cannot provide July 13-19, 2026 because data ends 2026-07-12")
    counted as a served number and was flagged `fabricated`. Honest declines scored as the worst
    failure the harness has, and every silent-error figure inherited it.

    Pinned in both directions, because the tempting fix (`bare_number`) breaks the other side: a
    real answer is usually a sentence, and holding those to a bare-number pattern dropped 145
    genuine figures in a single run.
    """
    from agent.numbers import asserts_number

    for prose in ("I cannot provide July 13-19, 2026 because data coverage ends 2026-07-12",
                  "No data available for 2026-07-13 to 2026-07-19",
                  "No data yet for Jul 13-19, 2026",
                  "There is no governed metric for that in Q2 2026"):
        assert not asserts_number(prose), prose

    for served in ("5386 value moments came from users in the Americas region in June 2026",
                   "134 currently-active annual subscriptions.",
                   "Last-week DAU/MAU (stickiness) = 31.4%",
                   "2,500 users",
                   "1620 vs 0"):
        assert asserts_number(served), served


if __name__ == "__main__":
    test_provenance_is_typed_not_guessed()
    test_every_offered_tool_can_be_dispatched()
    test_the_guardrail_registry_matches_the_set_and_names_real_files()
    test_the_check_tools_can_express_every_scope_the_guardrail_enforces()
    test_numeric_answers_cannot_skip_the_output_checks()
    test_provenance_reads_the_row_the_answer_came_from()
    test_dispatcher_records_the_measure_not_every_cell()
    test_the_judge_stance_is_a_treatment_with_two_levels()
    test_a_served_number_must_be_a_rounding_of_a_governed_one()
    test_metrics_conform_to_ontology()
    test_output_validation_catches_degenerate_values()
    test_value_resolver()
    test_governed_numbers_allows_comparison_and_refuses_composition()
    test_verifier_skips_prose_answers()
    test_governed_segment_excludes_test_members()
    test_region_availability_is_read_from_the_dimension()
    test_ladder_presets_reproduce_the_rung_thresholds()
    test_ablation_cell_is_expressible_and_incoherent_cells_are_named()
    test_the_input_guardrail_blocks_an_ungoverned_dimension_and_value()
    test_closing_phase_offers_only_exit_tools()
    test_verifier_is_refuse_only()
    test_toolbox_wiring_and_rung_gate()
    test_a_refusal_that_names_a_date_is_not_a_fabrication()
    test_a_driver_citation_is_typed_correlational_by_the_tree()
    print("OK - output guardrails (provenance/validation/verifier) + semantic layer + input guardrail + ladder: all pass.")


def test_a_guardrail_reports_what_it_verified_not_that_it_verified():
    """The output checks verify a NUMBER. When the answer is a number that is the same thing; when
    the answer is a judgement it is not, and saying `allowed` implies otherwise.

    Two runs of t4_business_health answered "Yes — generally healthy" and "No — health is weak",
    both declaring 3,642, and both drew `allowed` from all three output guardrails. Identical
    verification, opposite answers. 29 of 29 judgement-tier answers carried a figure this way.

    The check still runs — a composed figure smuggled into prose is exactly what it catches — so
    what changed is the claim it makes about its own scope."""
    from agent.guardrails.after import verify_answer
    sem = SemanticLayer(open_warehouse(create_star_views=True))
    steps = [_qm("active_users", 886.0, handle="r1", period="last_week")]

    def outcome(answer: str) -> str:
        rec: list = []
        verify_answer(sem, "q?", f"{answer} explanatory prose follows", steps, record=rec,
                      source_metric="active_users", declared_value=886.0, sources=["r1"],
                      run_governed_numbers=True, run_output_validation=False,
                      served_answer=answer)
        return next(a.outcome for a in rec if a.guardrail == "governed_numbers")

    # the answer IS the number -> the check verified the answer
    assert outcome("886") == "allowed"
    assert outcome("886 active users") == "allowed"
    # the answer is a judgement that mentions a number -> it verified one figure inside it
    assert outcome("No — the app looks unhealthy this week") == "verified a figure"
    assert outcome("Broad — all regions contributed, driven by lower days per user") == \
        "verified a figure"

    # the scope test reads the `answer` field ALONE. Joined with the explanation it is never a
    # bare number, so every answer read as prose and the distinction collapsed.
    rec: list = []
    verify_answer(sem, "q?", "886 explanatory prose follows", steps, record=rec,
                  source_metric="active_users", declared_value=886.0, sources=["r1"],
                  run_governed_numbers=True, run_output_validation=False)
    assert next(a.outcome for a in rec if a.guardrail == "governed_numbers") == "verified a figure"


def _grained(handle, metric, values, grain=None, period="last_week"):
    """A recorded query_metric step at a stated grain, as the trace stores it."""
    args = {"metric": metric, "period": period}
    if grain:
        args["time_grain"] = grain
    return {"tool": "query_metric", "handle": handle, "error": False, "args": args,
            "result": "columns: value\n" + "\n".join(f"({v},)" for v in values),
            "result_values": [float(v) for v in values]}


def test_a_comparison_holds_the_grain_fixed():
    """`active_users` at day grain and at week grain are the same METRIC and not the same MEASURE.

    One is distinct-users-per-day, the other distinct-users-per-week, and the ratio between them
    is a third quantity — stickiness — that nobody defined. Keyed on the metric alone the check
    read that ratio as "a comparison of two active_users results" and served DAU/MAU as governed:
    13 of 46 attempts at adv_dau_mau, every one of them wrong.

    A comparison holds the measure fixed and varies the period or the scope. Changing the grain
    varies the measure, so there is nothing left to compare."""
    from agent.guardrails.after import account_for
    sem = SemanticLayer(open_warehouse(create_star_views=True))

    # the exploit: daily actives over weekly actives, both real governed results
    cross = [_grained("r1", "active_users", [278, 331, 294, 268], grain="day"),
             _grained("r2", "active_users", [886], grain="week")]
    assert account_for(294 / 886, cross, ["r1", "r2"], sem) is None, "a cross-grain ratio is a new measure"
    assert account_for(886 - 294, cross, ["r1", "r2"], sem) is None
    assert account_for((886 - 294) / 294, cross, ["r1", "r2"], sem) is None

    # …while the same measure across two periods is still a comparison, and still allowed
    same = [_grained("r1", "active_users", [886], grain="week", period="last_week"),
            _grained("r2", "active_users", [836], grain="week", period="prev_week")]
    for figure in (886 - 836, 886 / 836, (886 - 836) / 836):
        account = account_for(figure, same, ["r1", "r2"], sem)
        assert account, f"{figure} is a same-grain comparison and must stand"
        assert "week grain" in account, f"the account must name the grain it held fixed: {account}"

    # and an ungrained pair — the ordinary case — is unaffected
    plain = [_grained("r1", "active_users", [886]), _grained("r2", "active_users", [836])]
    assert account_for(886 - 836, plain, ["r1", "r2"], sem)


def test_additivity_is_read_from_the_aggregate_not_annotated():
    """Kimball's three classes fall out of the `agg`, so nobody decides them per metric.

    The hand-kept `additive_over_time` carried True on five metrics and null on ten, and null
    meant both "not additive" and "nobody decided". The derivation agrees with every True and
    resolves every null — so the flag becomes a test OF the derivation rather than a second
    source of truth that can drift from it."""

    import yaml
    sem = SemanticLayer(open_warehouse(create_star_views=True))

    assert sem.additivity("value_moments") == "additive"          # sum(moments)
    assert sem.additivity("active_users") == "semi_additive"      # count(distinct user_id)
    assert sem.additivity("days_per_user") == "non_additive"      # a ratio
    # a STOCK: count(*) reads additive by its aggregate alone, but adding January's active
    # subscriptions to February's counts every subscription that survived both. No time column
    # is what says so.
    assert sem.additivity("active_subscriptions") == "semi_additive"

    from semantic.semantic import SPEC_PATH

    layer = yaml.safe_load(SPEC_PATH.read_text())["metrics"]
    disagreed = [n for n, spec in layer.items()
                 if spec.get("additive_over_time") and sem.additivity(n) != "additive"]
    assert not disagreed, (
        f"{disagreed} are annotated additive_over_time but do not derive as additive. One of the "
        "two is wrong, and the aggregate is the one that cannot drift")


def test_a_refusal_names_the_failure_it_found_not_the_one_it_knows():
    """`governed_numbers` had one refusal message, and it asserted a specific cause.

    Two answers to adv_last_week_oob declared 0.0 after calling only check_coverage — nothing
    governed was ever fetched — and were told "this number was composed from different metrics (a
    rate times a count, metric A over metric B)". Nothing was composed; nothing was queried. A
    guardrail that names a root cause it has not established is the defect this repo keeps finding
    in its own tools, and the model then repeats the wrong reason back."""
    from agent.guardrails.after import verify_answer
    sem = SemanticLayer(open_warehouse(create_star_views=True))

    checks_only = [{"tool": "check_coverage", "handle": "r1", "error": False,
                    "args": {"start": "2026-07-13", "end": "2026-07-19"},
                    "result": "NO — out of coverage", "result_values": [], "result_labels": []}]
    nothing = verify_answer(sem, "q?", "prose", checks_only, declared_value=0.0,
                            run_governed_numbers=True, run_output_validation=False,
                            served_answer="prose")
    assert not nothing.allowed
    assert "without querying anything governed" in nothing.detail
    assert "composed from different metrics" not in nothing.detail, (
        "nothing was composed — there were no metrics to compose")

    # …and where metrics WERE fetched and combined, the composition message is the true one
    two = [{"tool": "query_metric", "handle": "r1", "error": False, "args": {"metric": "mrr"},
            "result": "(2685,)", "result_values": [2685.0], "result_labels": [""]},
           {"tool": "query_metric", "handle": "r2", "error": False,
            "args": {"metric": "paying_users"}, "result": "(288,)",
            "result_values": [288.0], "result_labels": [""]}]
    composed = verify_answer(sem, "q?", "prose", two, declared_value=2685.0 / 288,
                             run_governed_numbers=True, run_output_validation=False,
                             served_answer="prose")
    assert not composed.allowed and "composed from different metrics" in composed.detail
