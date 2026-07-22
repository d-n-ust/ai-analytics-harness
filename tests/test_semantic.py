"""No-LLM proof of the spec-decomposition check (rrung>=6).

The check compares the metric behind an answer to what the question asked, slot by
slot: entity / population / measure / grain. Two halves:

  - deterministic (this test): read a metric's governed spec (entity + population +
    measure) from its definition, read the call's grain, link the answer number to the
    metric by VALUE, and compare to a required spec. Everything here is provable by
    construction, no model call — so the floor cases refuse and the controls do not.
  - the isolated decomposer (question -> required spec) is the one model-driven step; it
    is injected here as a stub, so this test never touches an LLM. Its accuracy is
    measured separately by a blind red-team, not asserted here.

Run: uv run python -m pytest tests/test_semantic.py -q     (or run this file directly)
"""

from __future__ import annotations

from types import SimpleNamespace

from harness import spec_check
from harness.semantic import SemanticLayer
from harness.tools import Toolbox
from harness.warehouse import open_warehouse


def _qm(metric, value, **args):
    """A recorded query_metric step returning one scalar, as the trace stores it."""
    return {"tool": "query_metric", "args": {"metric": metric, **args},
            "result": f"columns: value\n({value},)"}


# (label, question, answer, steps, required_spec, expect_refuse, expect_reason)
# required_spec is what an honest decomposer produces from the question alone; the metric
# side is read from the live semantic layer, so a mismatch is a real one.
CASES = [
    # ---- floor cases: a valid metric answering a slightly different question -------
    ("total users -> active_users (population)",
     "How many users do we have in total?", "2100",
     [_qm("active_users", 2100, period="all")],
     {"entity": "users", "population": "all", "measure": "count", "grain": "total"},
     True, "population_undefined"),

    ("total subscriptions -> active_subscriptions (population)",
     "How many subscriptions have we sold in total?", "371",
     [_qm("active_subscriptions", 371)],
     {"entity": "subscriptions", "population": "all", "measure": "count", "grain": "total"},
     True, "population_undefined"),

    ("total habits -> value_moments (entity)",
     "How many habits have been created in total?", "67132",
     [_qm("value_moments", 67132, period="all")],
     {"entity": "habits", "population": "all", "measure": "count", "grain": "total"},
     True, "no_governed_definition"),

    ("paying users -> active_users trap (population)",
     "How many paying users do we currently have?", "2100",
     [_qm("active_users", 2100, period="all")],
     {"entity": "users", "population": "paying", "measure": "count_distinct", "grain": "total"},
     True, "population_undefined"),

    ("active value moments -> value_moments (population on a SUM)",
     "How many value moments did active users generate?", "67132",
     [_qm("value_moments", 67132, period="all")],
     {"entity": "value_moments", "population": "active", "measure": "count", "grain": "total"},
     True, "population_undefined"),

    ("weekly window on a total question (grain)",
     "How many active users do we have in total?", "886",
     [_qm("active_users", 886, period="last_week")],
     {"entity": "users", "population": "active", "measure": "count_distinct", "grain": "total"},
     True, "wrong_grain"),

    ("share answered by a count (measure: rate vs amount)",
     "What share of our users are power users?", "432",
     [_qm("power_users", 432, period="all")],
     {"entity": "users", "population": "all", "measure": "ratio", "grain": "total"},
     True, "wrong_measure"),

    # ---- controls that must NOT over-refuse ---------------------------------------
    ("active users last week (all slots match)",
     "How many active users did we have last week?", "886",
     [_qm("active_users", 886, period="last_week")],
     {"entity": "users", "population": "active", "measure": "count_distinct", "grain": "period"},
     False, None),

    ("paying users answered by paying_users (correct)",
     "How many paying users do we currently have?", "371",
     [_qm("paying_users", 371)],
     {"entity": "users", "population": "paying", "measure": "count_distinct", "grain": "total"},
     False, None),

    ("total value moments: count vs sum is same measure class",
     "How many value moments in total?", "67132",
     [_qm("value_moments", 67132, period="all")],
     {"entity": "value_moments", "population": "all", "measure": "count", "grain": "total"},
     False, None),

    ("MRR: a named money measure, so population is not compared",
     "What is our current MRR?", "48210.50",
     [_qm("mrr", "48210.50")],
     {"entity": "revenue", "population": "all", "measure": "sum", "grain": "total"},
     False, None),
]


def test_comparison_deterministic():
    """The floor refuses, the controls pass — with the decomposer stubbed out."""
    con = open_warehouse()
    sem = SemanticLayer(con)
    for label, q, ans, steps, required, expect_refuse, expect_reason in CASES:
        source = steps[0]["args"]["metric"]                # the model's typed provenance
        ok, reason, missing, _ = spec_check.verify_answer(
            sem, q, ans, steps, decompose=lambda _q, r=required: r, source_metric=source)
        refused = not ok
        assert refused == expect_refuse, (
            f"{label}: expected {'refuse' if expect_refuse else 'allow'}, "
            f"got {'refuse' if refused else 'allow'}")
        if refused:
            assert reason == expect_reason, f"{label}: reason {reason!r} != {expect_reason!r}"
            assert missing, f"{label}: refusal must name the missing slot"


def test_metric_spec_reads_the_definition():
    """entity + population are read fields; measure is derived from the aggregate."""
    con = open_warehouse()
    sem = SemanticLayer(con)
    expect = {
        "active_users": ("users", "active", "count_distinct"),
        "value_moments": ("value_moments", "all", "sum"),
        "days_per_user": ("users", "active", "ratio"),
        "mrr": ("revenue", "active_subscription", "sum"),
        "active_subscriptions": ("subscriptions", "active_subscription", "count"),
        "paying_users": ("users", "paying", "count_distinct"),
        "reminder_open_rate": ("reminders", "active", "avg"),
    }
    for name, (e, p, mm) in expect.items():
        s = spec_check.metric_spec(sem.metrics[name])
        assert (s["entity"], s["population"], s["measure"]) == (e, p, mm), f"{name}: {s}"


def test_additivity_derives_from_measure():
    assert spec_check.additivity_of("sum") == "additive"
    assert spec_check.additivity_of("count") == "additive"
    assert spec_check.additivity_of("count_distinct") == "semi_additive"
    assert spec_check.additivity_of("ratio") == "non_additive"
    assert spec_check.additivity_of("avg") == "non_additive"


def test_metrics_conform_to_ontology():
    """Every metric's entity + population must be a value the ontology declares — so the
    decomposer (which reads the ontology) and the metric side share one vocabulary and
    cannot drift apart."""
    con = open_warehouse()
    sem = SemanticLayer(con)
    entities, populations = set(sem.ontology["entities"]), set(sem.ontology["populations"])
    assert "habits" in entities, "ontology must be a superset of the metrics (habits has no metric)"
    for name, m in sem.metrics.items():
        assert m.get("entity") in entities, f"{name}: entity {m.get('entity')!r} not in ontology"
        assert m.get("population") in populations, f"{name}: population {m.get('population')!r} not in ontology"


def test_provenance_is_typed_not_guessed():
    """The metric comes from the declaration; value-matching only selects WHICH call of
    that declared metric set the grain."""
    metrics = SemanticLayer(open_warehouse()).metrics
    # active_users queried twice; the reported 886 picks the last_week call (grain), not the total.
    steps = [_qm("active_users", 2100, period="all"),
             _qm("active_users", 886, period="last_week")]
    m, args, val = spec_check._provenance("886", steps, "active_users", metrics)
    assert m == "active_users" and args.get("period") == "last_week" and val == 886, (m, args, val)
    # a value shared across metrics never mislinks — the declared metric wins either way
    coll = [_qm("active_subscriptions", 371), _qm("paying_users", 371)]
    assert spec_check._provenance("371", coll, "paying_users", metrics)[0] == "paying_users"
    assert spec_check._provenance("371", coll, "active_subscriptions", metrics)[0] == "active_subscriptions"
    # no declaration, or a declared-but-unqueried metric -> nothing to verify
    assert spec_check._provenance("371", coll, None, metrics) == (None, None, None)
    assert spec_check._provenance("371", coll, "mrr", metrics) == (None, None, None)


def test_typed_provenance_drives_the_check():
    """Provenance is the declaration, never a guess. paying_users and active_subscriptions
    both return 371 here; the declared metric decides, and with no declaration a numeric
    answer is simply not verified (we never infer the metric from the text)."""
    con = open_warehouse()
    sem = SemanticLayer(con)
    q = "How many paying users do we currently have?"
    required = {"entity": "users", "population": "paying", "measure": "count_distinct", "grain": "total"}
    steps = [_qm("active_subscriptions", 371), _qm("paying_users", 371)]   # both 371
    # declared correctly -> paying_users (users/paying) -> allow
    ok, *_ = spec_check.verify_answer(sem, q, "371", steps, lambda _q: required,
                                      source_metric="paying_users")
    assert ok, "declared paying_users -> allow"
    # if the model declares the wrong metric it used, the check faithfully refuses on it
    ok2, reason2, *_ = spec_check.verify_answer(sem, q, "371", steps, lambda _q: required,
                                                source_metric="active_subscriptions")
    assert not ok2 and reason2 == "no_governed_definition", "entity subscriptions != users -> refuse"
    # no declaration -> not verified, no guessing -> allow
    ok3, *_ = spec_check.verify_answer(sem, q, "371", steps, lambda _q: required, source_metric=None)
    assert ok3, "no provenance declared -> not verified"


def test_result_sanity_catches_degenerate_values():
    """The check on the returned value (not the metric selection): an empty/null result
    narrated as a number, a share out of range, or a negative count -> refuse."""
    con = open_warehouse()
    sem = SemanticLayer(con)
    ok_spec = {"entity": "users", "population": "active", "measure": "count_distinct", "grain": "total"}
    # the governed query returned no value, but the model answered a number -> result_empty
    empty_steps = [_qm("active_users", None, period="last_week")]
    ok, reason, *_ = spec_check.verify_answer(sem, "How many active users last week?", "5",
                                              empty_steps, lambda _q: ok_spec, source_metric="active_users")
    assert not ok and reason == "result_empty", (ok, reason)
    # a share metric returning 150 is impossible
    share_steps = [_qm("reminder_open_rate", 150)]
    ok2, reason2, *_ = spec_check.verify_answer(sem, "What is the reminder open rate?", "150",
                                                share_steps, lambda _q: ok_spec, source_metric="reminder_open_rate")
    assert not ok2 and reason2 == "implausible_value", (ok2, reason2)
    # a normal value passes sanity (and this spec matches, so it's allowed)
    good_steps = [_qm("active_users", 886, period="last_week")]
    good_spec = {"entity": "users", "population": "active", "measure": "count_distinct", "grain": "period"}
    ok3, *_ = spec_check.verify_answer(sem, "How many active users last week?", "886",
                                       good_steps, lambda _q: good_spec, source_metric="active_users")
    assert ok3


def test_coerce_out_of_vocab_to_other():
    spec = {"entity": "frobnicate", "population": "all", "measure": "count", "grain": "total"}
    out = spec_check._coerce(spec, ["users", "other"], ["all", "other"])
    assert out["entity"] == "other" and out["population"] == "all"


def test_value_resolver():
    """Free-text filter values resolve to the governed member or refuse; the compiler
    canonicalises a resolvable value and rejects an unknown one."""
    from harness.semantic import SemanticError
    sem = SemanticLayer(open_warehouse())
    assert sem.resolve_member("platform", "iPhone") == "ios"
    assert sem.resolve_member("region", "europe") == "EMEA"
    assert sem.resolve_member("plan", "yearly") == "annual"
    assert sem.resolve_member("channel", "paid search") == "paid_search"
    assert sem.resolve_member("platform", "Blackberry") is None          # no governed member
    assert sem.resolve_member("is_internal", False) is False             # no vocab -> pass through
    # the compiler rewrites the value to its canonical member ...
    sql = sem.compile("active_users", filters={"platform": "iPhone"}, period="last_week")
    assert "platform = 'ios'" in sql and "iPhone" not in sql
    # ... and refuses an unresolvable one rather than querying an empty slice
    try:
        sem.compile("active_users", filters={"platform": "Blackberry"})
        assert False, "expected SemanticError"
    except SemanticError:
        pass
    # below the resolve rung (resolve=False) the raw value is used as-is — the pre-R6 bug
    raw = sem.compile("active_users", filters={"platform": "iPhone"}, resolve=False)
    assert "platform = 'iPhone'" in raw


def test_grain_of_call():
    assert spec_check.grain_of_call({}) == "total"
    assert spec_check.grain_of_call({"period": "all"}) == "total"
    assert spec_check.grain_of_call({"period": "last_week"}) == "period"
    assert spec_check.grain_of_call({"start": "2026-01-01"}) == "period"
    assert spec_check.grain_of_call({"group_by": ["region"]}) == "per_dimension"
    assert spec_check.grain_of_call({"time_grain": "week"}) == "per_dimension"


class _FakeModel:
    """Returns a canned declare_spec for the one floor question — proves the Toolbox
    wiring and the rung gate without an LLM. Accepts force_tool/temperature."""
    spec = SimpleNamespace(name="fake")

    def create(self, system, messages, tools, force_tool=None, temperature=None):
        block = SimpleNamespace(type="tool_use", id="d1", name="declare_spec",
                                input={"entity": "users", "population": "all",
                                       "measure": "count", "grain": "total"})
        return SimpleNamespace(content=[block])


def test_toolbox_wiring_and_rung_gate():
    con = open_warehouse()
    sem = SemanticLayer(con)
    steps = [_qm("active_users", 2100, period="all")]
    q = "How many users do we have in total?"

    # the granular rung flags gate each step separately
    assert Toolbox(con, 6, sem, None, 5).resolve is False and Toolbox(con, 6, sem, None, 6).resolve is True
    assert Toolbox(con, 6, sem, None, 6).spec_check is False and Toolbox(con, 6, sem, None, 7).spec_check is True
    assert Toolbox(con, 6, sem, None, 7).result_sanity is False and Toolbox(con, 6, sem, None, 8).result_sanity is True

    tb7 = Toolbox(con, rung=6, semantic=sem, tree=None, rrung=7)
    ok, reason, missing, _ = tb7.verify_answer(q, "2100", steps, _FakeModel(), "active_users")
    assert not ok and reason == "population_undefined" and missing, "R7 spec check must refuse the floor case"

    tb6 = Toolbox(con, rung=6, semantic=sem, tree=None, rrung=6)
    ok6, *_ = tb6.verify_answer(q, "2100", steps, _FakeModel(), "active_users")
    assert ok6, "spec check must be OFF below rrung 7"

    ok_nomodel, *_ = tb7.verify_answer(q, "2100", steps, None, "active_users")
    assert ok_nomodel, "with no model to decompose, spec check must not fire"


if __name__ == "__main__":
    test_comparison_deterministic()
    test_metric_spec_reads_the_definition()
    test_additivity_derives_from_measure()
    test_metrics_conform_to_ontology()
    test_provenance_is_typed_not_guessed()
    test_typed_provenance_drives_the_check()
    test_result_sanity_catches_degenerate_values()
    test_coerce_out_of_vocab_to_other()
    test_value_resolver()
    test_grain_of_call()
    test_toolbox_wiring_and_rung_gate()
    print(f"OK - spec check: {len(CASES)} comparison cases + derivation + additivity + "
          "ontology + typed-provenance + coercion + grain + wiring/gating all pass.")
