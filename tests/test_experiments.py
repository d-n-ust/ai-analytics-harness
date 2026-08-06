"""The experiment engine keeps the promises the arms make — NO LLM.

    PYTHONPATH=. uv run python tests/test_experiments.py

An arm file is a claim about what changes. These check that the claim is true of the layer the
engine actually generates, because the alternative is what happened last time: an arm that had
quietly acquired a second treatment, discovered after the run was paid for and written up.

The patch tests matter more than they look. A one-letter typo in `metrics.power_user.agg` would,
under a naive merge, create a sixteenth metric, run green, and measure a layer nobody wrote.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from dataclasses import replace

from experiments.engine import (Study, _longest_shared_span, apply_patch, check_candidate_count,
                                check_same_numbers, vocabulary_audit)
from semantic.semantic import SemanticLayer
from warehouse.warehouse import open_warehouse

BUILD = Path(__file__).resolve().parent.parent / ".build" / "_test"
THRESHOLD = "5+ value moments in a single day"
EXP1 = "01_segment_in_metric_name"        # bare name resolves; the engine finds it nested


def _layers(exp: Study):
    con = open_warehouse(create_star_views=True)
    paths = exp.materialize(BUILD / exp.name)
    return con, paths, {a: SemanticLayer(con, spec_path=paths[a]) for a in exp.arms}


# -- the patch language ------------------------------------------------------ #

def test_a_patch_cannot_invent_the_thing_it_patches():
    spec = {"metrics": {"power_users": {"agg": "x"}}}
    apply_patch(spec, {"metrics.power_users.agg": "y"}, [])          # fine: last key may be new
    apply_patch(spec, {"metrics.power_users.default_segment": "p"}, [])
    for bad in ("metrics.power_user.agg", "governance.segments.power", "nope.thing"):
        try:
            apply_patch(spec, {bad: "y"}, [])
        except KeyError:
            continue
        raise AssertionError(f"patch {bad!r} was accepted — a typo can create a metric")


def test_deleting_something_absent_is_an_error():
    spec = {"metrics": {"a": {}}}
    try:
        apply_patch(spec, {}, ["metrics.b"])
    except KeyError:
        return
    raise AssertionError("deleting an absent key passed — the arm removes something already gone")


def test_a_patch_does_not_mutate_the_base():
    spec = {"metrics": {"a": {"agg": "orig"}}}
    apply_patch(spec, {"metrics.a.agg": "changed"}, [])
    assert spec["metrics"]["a"]["agg"] == "orig", "apply_patch mutated the base layer in place"


# -- the arms of experiment 2 ------------------------------------------------ #

def test_prose_is_the_shipped_layer_by_construction():
    """Not 'has not drifted from' — IS. An empty patch cannot drift."""
    exp = Study.load("02_segment_in_agg")
    assert exp.arms["B_prose"].patch == {} and not exp.arms["B_prose"].delete, (
        "the prose arm has a patch — it is supposed to BE the shipped layer, not a copy of it")
    _, paths, _ = _layers(exp)
    got = yaml.safe_load(paths["B_prose"].read_text())
    assert got == yaml.safe_load(exp.base.read_text()), "prose.yml generated something != the base"


def test_every_arm_offers_the_same_metrics():
    exp = Study.load("02_segment_in_agg")
    _, _, layers = _layers(exp)
    check_candidate_count(layers, exp.arms)          # raises SystemExit if not
    assert len({len(sl.metrics) for sl in layers.values()}) == 1


def test_every_arm_reaches_the_same_numbers():
    exp = Study.load("02_segment_in_agg")
    con, _, layers = _layers(exp)
    problems = check_same_numbers(con, exp.base, layers, exp.arms)
    assert not problems, "arms differ in capability, not legibility:\n  " + "\n  ".join(problems)


def test_the_threshold_moves_and_does_not_multiply():
    """The fact under test appears in exactly the arms that claim it, and exactly once."""
    exp = Study.load("02_segment_in_agg")
    _, _, layers = _layers(exp)
    seen = {a: sl.list_metrics_text().count(THRESHOLD) for a, sl in layers.items()}
    assert seen == {"A_absent": 0, "B_prose": 1, "C_segment": 1}, (
        f"the threshold is not where the arms say it is: {seen}")
    # ...and in `segment` it is on the segment, not on the metric.
    metric_line = next(ln for ln in layers["C_segment"].list_metrics_text().splitlines()
                       if ln.startswith("- power_users:"))
    assert THRESHOLD not in metric_line, "segment arm still states the threshold on the metric"


def test_prose_and_segment_share_the_same_wording_with_every_question():
    """The control that experiment 1 lacked.

    `prose` and `segment` differ in WHERE the threshold is written. If they also differed in the
    words used, a win would be vocabulary and nobody could tell. Equality here is what makes the
    comparison structural — so it is asserted, not audited after the fact."""
    exp = Study.load("02_segment_in_agg")
    _, _, layers = _layers(exp)
    rows = {(r["arm"], r["id"]): r["tokens"] for r in vocabulary_audit(exp.cases, layers)}
    for case in exp.cases:
        p, s = rows[("B_prose", case["id"])], rows[("C_segment", case["id"])]
        assert p == s, (f"{case['id']}: prose shares {p} tokens with the catalogue, segment {s} — "
                        "the arms differ in wording as well as structure")


def test_absent_states_the_threshold_nowhere():
    exp = Study.load("02_segment_in_agg")
    _, _, layers = _layers(exp)
    text = layers["A_absent"].list_metrics_text().lower()
    for leak in ("5+", "five or more", "moments >= 5", "single day"):
        assert leak not in text, f"absent arm still leaks the threshold: {leak!r}"


# -- the arms of experiment 1, migrated off four forked layer files ---------- #

def test_experiment_1_arms_reach_the_same_numbers():
    """The invariant, over the arm that MOVES the demand rather than restating it.

    `segment` deletes the twin, so `real_value_moments` is reachable only as `value_moments` under
    the `real_users` segment. Equality here is the whole claim that the repair changes the interface
    without changing the answers."""
    exp = Study.load(EXP1)
    con, _, layers = _layers(exp)
    problems = check_same_numbers(con, exp.base, layers, exp.arms)
    assert not problems, "arms differ in capability, not legibility:\n  " + "\n  ".join(problems)


def test_the_position_control_changes_only_order():
    """`prose_swapped` is the reason `reorder` exists. Content equality is what makes a difference
    between it and `prose` attributable to position and to nothing else."""
    exp = Study.load(EXP1)
    _, paths, _ = _layers(exp)
    prose = yaml.safe_load(paths["B_prose"].read_text())
    swapped = yaml.safe_load(paths["B_prose_swapped"].read_text())
    assert prose == swapped, "the position control changed a metric's content — it may only reorder"
    assert list(swapped["metrics"])[:2] == ["real_value_moments", "value_moments"]
    assert list(prose["metrics"])[:2] == ["value_moments", "real_value_moments"], (
        "prose and prose_swapped open with the same metric — the control controls for nothing")


def test_the_metric_name_leak_is_known_and_bounded():
    """`absent`'s floor is NOT total, and the limit is recorded rather than claimed away.

    The arm strips who-each-metric-counts from every description, but the metric NAMES are untouched
    — `real_value_moments` still says "real". That is the experiment's point (a name is not a
    definition), so it must stay true: if a future edit renamed metrics per-arm, the treatment would
    silently become "different names" and nothing would say so."""
    exp = Study.load(EXP1)
    _, _, layers = _layers(exp)
    names = {a: set(sl.metrics) for a, sl in layers.items()}
    # The segment arm legitimately drops the twin; every other arm must offer identical NAMES.
    unchanged = {a: n for a, n in names.items() if a != "C_segment"}
    assert len(set(map(frozenset, unchanged.values()))) == 1, (
        f"arms differ in metric NAMES, not just descriptions: {unchanged}")
    assert "real" in " ".join(names["A_absent"]), (
        "the absent arm no longer leaks via a name — the experiment's stated limit has moved")


def test_the_candidate_count_guard_fires_when_an_arm_shrinks_undeclared():
    """The confound that cost experiment 1 its headline, now refused by the runner.

    Asserted by REMOVING the declaration, because a guard that has only ever been seen to pass is
    a guard nobody knows works."""
    exp = Study.load(EXP1)
    _, _, layers = _layers(exp)
    check_candidate_count(layers, exp.arms)                       # declared: passes
    undeclared = {**exp.arms, "C_segment": replace(exp.arms["C_segment"], changes_candidate_count=False)}
    try:
        check_candidate_count(layers, undeclared)
    except SystemExit:
        return
    raise AssertionError("an arm offering 14 metrics against 15 passed without declaring it")


def test_the_segment_arm_still_carries_its_known_vocabulary_confound():
    """Pinned so the confound cannot be quietly edited away.

    Those synonyms are why this experiment's headline is unattributable. The repair is a NEW arm,
    not an edit to this one — editing it would redefine what twelve stored runs measured, silently.
    """
    exp = Study.load(EXP1)
    _, _, layers = _layers(exp)
    rows = {(r["arm"], r["id"]): r["tokens"] for r in vocabulary_audit(exp.cases, layers)}
    seg = rows[("C_segment", "p_pop_all_week")]
    others = [rows[(a, "p_pop_all_week")] for a in exp.arms if a != "C_segment"]
    assert seg >= 9 and seg - max(others) >= 3, (
        f"the segment arm no longer out-matches its rivals on wording ({seg} vs {others}) — either "
        "the confound was edited away without a new arm, or the audit stopped working")


# -- the patch language, continued ------------------------------------------- #

def test_reorder_moves_named_keys_to_the_front_and_keeps_the_rest_in_place():
    spec = {"metrics": {"a": 1, "b": 2, "c": 3}}
    assert list(apply_patch(spec, {}, [], {"metrics": ["b", "a"]})["metrics"]) == ["b", "a", "c"]
    assert list(apply_patch(spec, {}, [])["metrics"]) == ["a", "b", "c"]
    try:
        apply_patch(spec, {}, [], {"metrics": ["nope"]})
    except KeyError:
        return
    raise AssertionError("reordering an absent key passed — the control would silently do nothing")


def test_study_yml_rejects_an_unknown_key():
    """A typo in `guardrails` used to run the whole experiment at the default and report nothing."""
    exp = Study.load(EXP1)
    spec = yaml.safe_load((exp.directory / "study.yml").read_text())
    assert set(spec) <= {"title", "base", "rung", "guardrails", "arms", "tests_rules"}, (
        f"study.yml carries a key the loader would reject: {sorted(spec)}")


# -- the audit itself -------------------------------------------------------- #

def test_the_vocabulary_audit_can_actually_see_a_leak():
    """A check nobody has seen fire is a check nobody knows works."""
    n, span = _longest_shared_span("how many users completed five or more habits in a single day",
                                   "- power_users: users who completed five or more habits in a single day")
    assert n == 9 and span == "completed five or more habits in a single day", (n, span)
    assert _longest_shared_span("how many power users", "- mrr: monthly recurring revenue")[0] == 0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
    print("OK — patches cannot invent metrics, B_prose IS the shipped layer, 02's arms all offer the\n"
          "same fifteen metrics, both experiments reach the same numbers, the threshold moves without\n"
          "multiplying, the position control changes only order, the candidate-count guard fires when\n"
          "an arm shrinks undeclared, and 01's known vocabulary confound is pinned rather than edited\n"
          "away.")
