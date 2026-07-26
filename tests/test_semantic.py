"""No-LLM proofs of the answer output-guardrails and the semantic layer.

The output guardrails (harness/verifier.py) run on a completed answer, gated by rung:
provenance / single-metric (R7), output validation (R8), and the trajectory verifier (R9,
stubbed here so the file never calls an LLM). Everything asserted below is deterministic and
provable by construction. The rest exercises the semantic layer, the coverage check, and the
guardrail ladder.

Run: uv run python -m pytest tests/test_semantic.py -q     (or run this file directly)
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from agent import input_guardrail, verifier
from agent.guardrails import LADDER
from agent.numbers import bare_number
from agent.protocol import TERMINAL_TOOLS
from agent.tools import Toolbox
from semantic.semantic import COVERAGE_DIMS, SemanticError, SemanticLayer
from semantic.tree import MetricTree
from warehouse.warehouse import open_warehouse


def _qm(metric, value, **args):
    """A recorded query_metric step returning one scalar, as the trace stores it: the typed
    `result_values` the dispatcher records, plus the display string."""
    try:
        vals = [float(value)]
    except (TypeError, ValueError):
        vals = []
    return {"tool": "query_metric", "args": {"metric": metric, **args},
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
    """Nine guardrail flags sat in one file while their implementations lived in two to four
    others, with nothing connecting them — so "what does this guardrail actually do" could only
    be answered by grepping. The registry answers it, and this keeps the answer true: every flag
    is described, in ladder order, and every file it claims to be implemented in exists and
    mentions it."""
    from agent.guardrails import GUARDRAILS, LADDER_ORDER, GuardrailSet, Position

    declared = [f.name for f in dataclasses.fields(GuardrailSet)]
    assert [g.name for g in GUARDRAILS] == declared == LADDER_ORDER, \
        "the registry, the flag set and the ladder order must be the same nine, in one order"

    root = Path(__file__).resolve().parent.parent
    for g in GUARDRAILS:
        assert isinstance(g.position, Position) and g.mechanism, g.name
        for rel in g.implemented_in:
            path = root / rel
            assert path.exists(), f"{g.name}: claims {rel}, which does not exist"
            assert g.name in path.read_text(), f"{g.name}: {rel} never mentions it"

    # Position is the distinction that carries information, so each one must be used.
    used = {g.position for g in GUARDRAILS}
    assert used == set(Position), f"unused position(s): {set(Position) - used}"


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
    ok, reason, *_ = verifier.verify_answer(sem, "How many active users last week?", "5", empty_steps,
                                            source_metric="active_users", declared_value=5)
    assert not ok and reason == "result_empty", (ok, reason)
    # a share metric returning 150 is impossible
    share_steps = [_qm("reminder_open_rate", 150)]
    ok2, reason2, *_ = verifier.verify_answer(sem, "What is the reminder open rate?", "150", share_steps,
                                              source_metric="reminder_open_rate", declared_value=150)
    assert not ok2 and reason2 == "implausible_value", (ok2, reason2)
    # a normal value passes sanity
    good_steps = [_qm("active_users", 886, period="last_week")]
    ok3, *_ = verifier.verify_answer(sem, "How many active users last week?", "886", good_steps,
                                     source_metric="active_users", declared_value=886)
    assert ok3


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


def test_single_metric_enforcement():
    """R7: the served number must BE a governed result; a value composed by hand (rate x count)
    matches no governed result and is refused no_governed_definition."""
    con = open_warehouse()
    sem = SemanticLayer(con)
    steps = [_qm("new_signups", 444, start="2026-06-01", end="2026-06-30"),
             _qm("activation_rate", 0.529, start="2026-06-01", end="2026-06-30")]
    ok, *_ = verifier.verify_answer(sem, "how many signups?", "444", steps, source_metric="new_signups",
                                    declared_value=444, run_output_validation=False, run_single_metric=True)
    assert ok, "a direct governed result must pass single-metric"
    # 235 = 444 * 0.529 matches no governed result -> refuse
    ok2, reason2, *_ = verifier.verify_answer(sem, "how many activated?", "235", steps, source_metric=None,
                                              declared_value=235, run_output_validation=False,
                                              run_single_metric=True)
    # A hand-derived value means no single governed metric produces it -> report that root cause.
    assert not ok2 and reason2 == "no_governed_definition", \
        "a hand-derived value must refuse no_governed_definition"


def test_verifier_skips_prose_answers():
    """The output checks apply to a NUMERIC answer, identified by the typed `value` field — not by
    parsing the text. A prose judgement or a diagnostic narrative leaves `value` unset
    (declared_value=None), so the checks stand down even with a source_metric declared and the
    metric's number sitting in the prose."""
    con = open_warehouse()
    sem = SemanticLayer(con)
    steps = [_qm("value_moments", 67132, period="all")]
    # a prose health verdict: no declared value -> skip
    ok, *_ = verifier.verify_answer(sem, "Is the app healthy?", "No — mixed early-warning signals",
                                    steps, source_metric="value_moments")
    assert ok, "prose answer (no declared value) must skip the output checks"
    # a diagnostic narrative that literally contains 67132: still skipped, because value is unset
    narrative = "No; value moments were 67132 all-time but active users rose from 836 to 886"
    ok2, *_ = verifier.verify_answer(sem, "What happened?", narrative, steps, source_metric="value_moments")
    assert ok2, "diagnostic narrative (no declared value) must skip the output checks"


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
        assert g.single_metric is (n >= 7) and g.output_validation is (n >= 8)
        assert g.trajectory_verify is (n >= 9)
        assert g.label() == f"R{n}"


def test_ablation_cell_is_expressible_and_incoherent_cells_are_named():
    """The point of the refactor: a leave-one-out cell exists in the flag space (no single
    rrung can express it), is self-labelling so a stored row says what produced it, and the
    cells that measure a DIFFERENT system are named rather than silently reported."""
    from agent.guardrails import LADDER, incoherent
    from agent.prompt import build_grounding
    con = open_warehouse(create_star_views=True)
    cell = LADDER[9].without("resolve")

    assert cell.trajectory_verify and not cell.resolve      # unreachable from any rrung
    assert cell.label() == "R9-resolve"
    assert incoherent(cell) is None

    # A cell whose guardrail cannot fire is named, not reported. output_validation reads a `value`
    # the answer tool only offers under single_metric, so without it the check is inert and its
    # measured contribution would be zero by construction — 365 stored answers sat in such cells.
    inert = LADDER[8].without("single_metric")
    assert "output_validation without single_metric" in (incoherent(inert) or "")
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
    assert incoherent(LADDER[9].without("single_metric")) is not None


def test_the_input_guardrail_blocks_an_ungoverned_dimension_and_value():
    """R5, deterministic (no model call): the coverage check rejects a filter DIMENSION the metric does
    not have, and a filter VALUE that is not a governed member — each with its own coded
    reason, before any query runs. The value case must NOT hand back a member list, or the
    model substitutes a sibling from it (the failure that served Americas for 'North America')."""
    con = open_warehouse()
    sem = SemanticLayer(con)
    tb = Toolbox(con, 6, sem, None, LADDER[5])                 # R5: member resolution on
    window = {"start": "2026-06-01", "end": "2026-06-30"}

    no_dim = input_guardrail.block(sem, tb.g, {"metric": "mrr", "filters": {"region": "Americas"}})
    assert no_dim and "dimension_not_supported" in no_dim   # mrr is sliceable by plan only

    bad_value = input_guardrail.block(
        sem, tb.g, {"metric": "active_users", "filters": {"region": "North America"}, **window})
    assert bad_value and "ungoverned_dimension_value" in bad_value
    assert "Americas" not in bad_value                 # no substitutable member list leaks back

    # a governed dimension holding a governed member passes both checks
    assert input_guardrail.block(
        sem, tb.g, {"metric": "active_users", "filters": {"region": "Americas"}, **window}) is None

    # below the resolve rung the value check is off — the pre-R5 hole, kept measurable
    below = Toolbox(con, 6, sem, None, LADDER[4])
    assert input_guardrail.block(
        sem, below.g, {"metric": "active_users", "filters": {"region": "North America"}, **window}) is None


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
              run_output_validation=False, run_single_metric=True)
    seen: dict = {}

    def passing(question, metric, metric_def, args, value, declared_value):
        seen.update(metric=metric, args=args, declared=declared_value)
        return True, "none", ""

    ok, _, _, _ = verifier.verify_answer(sem, "How many paying users?", "371", steps,
                                         verify_traj=passing, **kw)
    assert ok is True                                   # a passing verdict changes nothing
    assert seen["metric"] == "paying_users" and seen["declared"] == 371
    assert seen["args"] == {"metric": "paying_users"}   # the analyst's call, not the compiled SQL

    ok, reason, _, _ = verifier.verify_answer(
        sem, "How many paying users?", "371", steps,
        verify_traj=lambda *a: (False, "scope", "answers a different question"), **kw)
    # downgraded to a GOVERNED reason (scope -> other; the old out_of_scope was not in REFUSAL_REASONS)
    assert ok is False and reason == "other"


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
    for n, guardrail in [(7, "single_metric"), (8, "output_validation"), (9, "trajectory_verify")]:
        assert getattr(Toolbox(con, 6, sem, None, LADDER[n - 1]).g, guardrail) is False
        assert getattr(Toolbox(con, 6, sem, None, LADDER[n]).g, guardrail) is True

    # The single-metric check itself, deterministic and with no model needed. The wiring that
    # switches it on for a live run moved to the orchestrator's _Run; what is asserted here is
    # the rung it belongs to, and what it does when it fires.
    def check(rrung, declared):
        return verifier.verify_answer(
            sem, q, str(declared), steps, source_metric="active_users", declared_value=declared,
            run_single_metric=LADDER[rrung].single_metric,
            run_output_validation=LADDER[rrung].output_validation)

    assert check(7, 2100)[0], "a direct governed result passes single-metric"
    ok, reason, *_ = check(7, 999)
    assert not ok and reason == "no_governed_definition", \
        "a hand-derived value (matches no governed result) refuses no_governed_definition at R7"
    assert check(6, 999)[0], "single-metric must be OFF below rrung 7"

    # a prose answer (no typed value) is passed through untouched
    assert verifier.verify_answer(sem, q, "healthy overall", steps, source_metric="active_users",
                                  declared_value=None, run_single_metric=True)[0], \
        "no declared value -> output guardrails stand down"


if __name__ == "__main__":
    test_provenance_is_typed_not_guessed()
    test_every_offered_tool_can_be_dispatched()
    test_the_guardrail_registry_matches_the_set_and_names_real_files()
    test_the_check_tools_can_express_every_scope_the_guardrail_enforces()
    test_numeric_answers_cannot_skip_the_output_checks()
    test_provenance_reads_the_row_the_answer_came_from()
    test_dispatcher_records_the_measure_not_every_cell()
    test_metrics_conform_to_ontology()
    test_output_validation_catches_degenerate_values()
    test_value_resolver()
    test_single_metric_enforcement()
    test_verifier_skips_prose_answers()
    test_governed_segment_excludes_test_members()
    test_region_availability_is_read_from_the_dimension()
    test_ladder_presets_reproduce_the_rung_thresholds()
    test_ablation_cell_is_expressible_and_incoherent_cells_are_named()
    test_the_input_guardrail_blocks_an_ungoverned_dimension_and_value()
    test_closing_phase_offers_only_exit_tools()
    test_verifier_is_refuse_only()
    test_toolbox_wiring_and_rung_gate()
    print("OK - output guardrails (provenance/validation/verifier) + semantic layer + input guardrail + ladder: all pass.")
