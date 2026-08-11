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

from dataclasses import replace

import yaml

from experiments.engine import (
    STUDY_KEYS,
    Study,
    _column_letter,
    _longest_shared_span,
    apply_patch,
    check_candidate_count,
    check_same_numbers,
    vocabulary_audit,
)
from semantic.semantic import SemanticLayer
from warehouse.warehouse import open_warehouse

BUILD = Path(__file__).resolve().parent.parent / ".build" / "_test"
THRESHOLD = "5+ value moments in a single day"
EXP1 = "02_segment"        # bare name resolves; the engine finds it nested


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
    exp = Study.load("02_segment")
    assert exp.arms["B_documented"].patch == {} and not exp.arms["B_documented"].delete, (
        "the prose arm has a patch — it is supposed to BE the shipped layer, not a copy of it")
    _, paths, _ = _layers(exp)
    got = yaml.safe_load(paths["B_documented"].read_text())
    assert got == yaml.safe_load(exp.base.read_text()), "prose.yml generated something != the base"


def test_an_arm_that_shrinks_the_catalogue_declares_it():
    """Written when study 02 existed and every one of its arms offered the same fifteen metrics.
    That study is now merged into 01, whose repair arm DELETES the twin metric — so the property
    worth asserting is not that the counts match, but that a mismatch is declared.

    Under random choice between two confusable options, the arm with one fewer scores 50 points
    higher before any treatment exists. `changes_candidate_count` is the arm saying so out loud,
    and the guard exists to refuse a study where nobody has."""
    exp = Study.load("02_segment")
    _, _, layers = _layers(exp)
    check_candidate_count(layers, exp.arms)          # raises SystemExit if an arm shrinks silently
    counts = {a: len(sl.metrics) for a, sl in layers.items()}
    shrunk = [a for a, n in counts.items() if n < max(counts.values())]
    assert shrunk == ["D_declared"], f"unexpected arms shrink the catalogue: {counts}"
    assert exp.arms["D_declared"].changes_candidate_count, (
        "D_declared offers fewer metrics than its peers and does not declare it")


def test_every_arm_reaches_the_same_numbers():
    exp = Study.load("02_segment")
    con, _, layers = _layers(exp)
    problems = check_same_numbers(con, exp.base, layers, exp.arms)
    assert not problems, "arms differ in capability, not legibility:\n  " + "\n  ".join(problems)


def test_the_threshold_moves_and_does_not_multiply():
    """The fact under test appears in exactly the arms that claim it, and exactly once."""
    exp = Study.load("02_segment")
    _, _, layers = _layers(exp)
    # Stated as a PROPERTY rather than as a roster. The exact dict was written when this study had
    # three arms; the merge added the position control, which states the threshold exactly like the
    # arm it reorders. A test that has to be edited whenever an arm is added is a test that will be
    # edited without being read.
    seen = {a: sl.list_metrics_text().count(THRESHOLD) for a, sl in layers.items()}
    assert seen["A_implicit"] == 0, f"the absent arm still states the threshold: {seen}"
    assert all(n == 1 for a, n in seen.items() if a != "A_implicit"), (
        f"every arm but A_implicit must state the threshold exactly once: {seen}")
    # ...and in `segment` it is on the segment, not on the metric.
    metric_line = next(ln for ln in layers["D_declared"].list_metrics_text().splitlines()
                       if ln.startswith("- power_users:"))
    assert THRESHOLD not in metric_line, "segment arm still states the threshold on the metric"


def test_prose_and_segment_share_the_same_wording_on_the_aggregate_instance():
    """The control the NAME instance lacked, asserted on the instance that has it.

    `prose` and `segment` differ in WHERE the threshold is written. If they also differed in the
    words used, a win would be vocabulary and nobody could tell. The aggregate instance was built
    with that equality in mind — its segment description is the same phrase the prose arm puts in
    the metric description — so it is asserted rather than audited afterwards.

    SCOPED to the `q_thresh_*` questions on purpose. The NAME instance does NOT have this property:
    its segment arm gained bespoke synonyms ("including staff", "excluding staff") that match the
    question wording verbatim, which is the confound that cost that study its headline. That is
    pinned by `test_the_name_instance_vocabulary_confound_is_pinned` rather than quietly fixed here,
    because editing it would erase the evidence for why the control exists at all."""
    exp = Study.load("02_segment")
    _, _, layers = _layers(exp)
    rows = {(r["arm"], r["id"]): r["tokens"] for r in vocabulary_audit(exp.cases, layers)}
    scoped = [c for c in exp.cases if c["id"].startswith("q_thresh")]
    assert scoped, "no aggregate-instance questions found — the scope filter is wrong"
    for case in scoped:
        p, s = rows[("B_documented", case["id"])], rows[("D_declared", case["id"])]
        assert p == s, (f"{case['id']}: prose shares {p} tokens with the catalogue, segment {s} — "
                        "the arms differ in wording as well as structure")


def test_the_name_instance_vocabulary_confound_is_pinned():
    """The NAME instance's segment arm shares a long verbatim span with its questions, and that is
    recorded rather than repaired.

    `D_declared` declares synonyms like "including staff" and "excluding staff" that appear in the
    questions word for word, so its win on those items cannot be attributed to structure. Deleting
    the synonyms would make the study look clean and lose the reason its results are unciteable.
    The number is pinned so that a change to it is a decision someone makes, not a drift."""
    exp = Study.load("02_segment")
    _, _, layers = _layers(exp)
    rows = {(r["arm"], r["id"]): r["tokens"] for r in vocabulary_audit(exp.cases, layers)}
    worst = max((rows[("D_declared", c["id"])] for c in exp.cases if c["id"].startswith("p_pop")),
                default=0)
    assert worst >= 5, (
        "the name instance's vocabulary confound has gone. If that was deliberate, update this "
        "test and the study README; if not, a synonym list has been edited by accident.")


def test_absent_states_the_threshold_nowhere():
    exp = Study.load("02_segment")
    _, _, layers = _layers(exp)
    text = layers["A_implicit"].list_metrics_text().lower()
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


def test_reorder_still_moves_a_metric_without_changing_it():
    """`reorder` exists so a position control is expressible as a DELTA rather than a forked file.
    Its only user was retired, so the mechanism is proved directly here — otherwise the next study
    to need it would find an untested feature."""
    from experiments.engine import apply_patch

    spec = {"metrics": {"a": {"x": 1}, "b": {"x": 2}, "c": {"x": 3}}}
    out = apply_patch(spec, {}, [], {"metrics": ["b", "a"]})
    assert list(out["metrics"]) == ["b", "a", "c"], "reorder did not move the named keys to the front"
    assert out["metrics"] == spec["metrics"], "reorder changed a metric's content — it may only reorder"


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
    unchanged = {a: n for a, n in names.items() if a != "D_declared"}
    assert len(set(map(frozenset, unchanged.values()))) == 1, (
        f"arms differ in metric NAMES, not just descriptions: {unchanged}")
    assert "real" in " ".join(names["A_implicit"]), (
        "the absent arm no longer leaks via a name — the experiment's stated limit has moved")


def test_the_candidate_count_guard_fires_when_an_arm_shrinks_undeclared():
    """The confound that cost experiment 1 its headline, now refused by the runner.

    Asserted by REMOVING the declaration, because a guard that has only ever been seen to pass is
    a guard nobody knows works."""
    exp = Study.load(EXP1)
    _, _, layers = _layers(exp)
    check_candidate_count(layers, exp.arms)                       # declared: passes
    undeclared = {**exp.arms, "D_declared": replace(exp.arms["D_declared"], changes_candidate_count=False)}
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
    seg = rows[("D_declared", "p_pop_all_week")]
    others = [rows[(a, "p_pop_all_week")] for a in exp.arms if a != "D_declared"]
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


def test_an_enforced_arm_differs_from_its_declared_arm_only_in_the_guardrail():
    """`E_enforced` is `D_declared` plus a check, and nothing else — asserted, not trusted.

    The two arms carry the same layer patch in two files, because an arm is a file and the engine
    has no include. Two copies of a rule is a rule that can disagree with itself: if someone adds a
    metric to D and forgets E, the study silently starts comparing catalogues instead of
    guardrails, and every number it produces is a measurement of the wrong thing."""
    for name in Study.discover():
        study = Study.load(name)
        d, e = study.arms.get("D_declared"), study.arms.get("E_enforced")
        if not (d and e):
            continue
        assert d.patch == e.patch, (
            f"{name}: D_declared and E_enforced patches differ. The guardrail must be the only "
            f"difference between them.")
        assert d.delete == e.delete, f"{name}: D_declared and E_enforced delete different keys"
        assert d.environment == e.environment, (
            f"{name}: D_declared and E_enforced declare different environments")
        assert (d.layer_dir, d.engine) == (e.layer_dir, e.engine), (
            f"{name}: D_declared and E_enforced point at different layers or engines — "
            f"D={d.engine or 'study'}:{d.layer_dir or '-'} E={e.engine or 'study'}:{e.layer_dir or '-'}")
        assert e.agent.get("guardrails") and not d.agent.get("guardrails"), (
            f"{name}: E_enforced must override guardrails and D_declared must not — that override "
            f"IS the treatment")


def test_study_yml_rejects_an_unknown_key():
    """A typo in `guardrails` used to run the whole experiment at the default and report nothing.

    Read STUDY_KEYS rather than restating it: an earlier version of this test kept its own copy of
    the allowed set, so adding a key to the loader failed here for a reason that had nothing to do
    with what the test is about."""
    for name in Study.discover():
        spec = yaml.safe_load((Study.resolve(name) / "study.yml").read_text())
        assert set(spec) <= STUDY_KEYS, (
            f"{name}/study.yml carries key(s) the loader would reject: "
            f"{sorted(set(spec) - STUDY_KEYS)}")


def test_every_arm_file_names_a_declared_matrix_column():
    """A letter must mean the same intervention in every study, and the check must be mechanical.

    Three studies once ran three vocabularies for the same three interventions — A_absent, A_raw,
    A_implicit — and the letters agreed with primitives_matrix.md in none of them. Nothing said so
    until two folders were compared by hand. `Study.load` now validates the `columns:` block against
    the arm files on disk; this asserts every study on disk passes it."""
    for name in Study.discover():
        Study.load(name)          # raises if a column is undeclared, misnamed, or has no arm

    exp = Study.load(EXP1)
    assert all(_column_letter(a) for a in exp.arms), (
        f"{EXP1} has arms that name no matrix column: {sorted(exp.arms)}")


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
    print("OK — patches cannot invent metrics, B_documented IS the shipped layer, 02's arms all offer the\n"
          "same fifteen metrics, both experiments reach the same numbers, the threshold moves without\n"
          "multiplying, the position control changes only order, the candidate-count guard fires when\n"
          "an arm shrinks undeclared, and 01's known vocabulary confound is pinned rather than edited\n"
          "away.")
