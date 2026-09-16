"""The projection onto a trace backend says what the run said, and needs neither to be checked.

Every test here runs with langfuse absent and no server reachable. That is the property worth
protecting: `render` is pure, so the mapping a reader sees on a dashboard can be diffed and
asserted here rather than eyeballed there.

Run: uv run python -m pytest harness/tests/test_publish.py -q     (or run this file directly)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from evals.publish import RUN_PREFIX, SCORES, SPAN_TYPES, _score, emit, render


def row(qid, cell="A", *, rep=0, suite="abc123", **kw):
    r = {"qid": qid, "rep": rep, "config": cell, "suite": suite, "question": f"Q {qid}?",
         "answer": "42", "gold": "42", "tier": "t1", "model": "gpt-5-mini",
         "expected_action": "answer", "outcome": "answer", "bucket": "right", "correct": True,
         "cost_usd": 0.0012, "elapsed_s": 5.0, "abstained": False, "confident_wrong": False,
         "fabricated": False, "off_governance": False,
         "turns": [{"in": 100, "out": 20, "cached": 80, "ms": 900}],
         "steps": [{"tool": "run_sql", "args": {"sql": "select 1"}, "result": "1"}],
         "acts": [{"guardrail": "governed_numbers", "position": "after",
                   "outcome": "allowed", "detail": "value_moments = 3785"}]}
    r.update(kw)
    return r


def written(rows, summary=None) -> Path:
    d = Path(tempfile.mkdtemp())
    (d / "raw.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (d / "summary.json").write_text(json.dumps(summary or {"meta": {"models": ["gpt-5-mini"],
                                                                    "reps": 1}, "cells": {}}))
    return d


def test_one_dataset_item_per_question_however_many_times_it_was_asked():
    """The bug this guards: an item per ROW puts the same question in the dataset once per
    repetition and once per arm, so a 2-question suite looks like an 8-question one."""
    rows = [row("q1", c, rep=i) for c in ("A", "B") for i in range(2)] + \
           [row("q2", c, rep=i) for c in ("A", "B") for i in range(2)]
    p = render(written(rows))
    assert [i["id"] for i in p["items"]] == ["q1", "q2"]
    assert sum(len(r["traces"]) for r in p["runs"]) == 8, "every row is still its own trace"


def test_two_rows_that_differ_only_by_an_unlisted_dimension_do_not_share_a_trace():
    """The mock sweep varied `rung` as well as `config`. Seeding a trace on the cell alone put 888
    rows into 444 traces, each silently overwriting the other, and the published silent-error
    count came out at half the truth with no error anywhere."""
    rows = [row("q1", "R1", rung=3), row("q1", "R1", rung=7)]
    p = render(written(rows))
    seeds = {t["seed"] for r in p["runs"] for t in r["traces"]}
    assert len(seeds) == 2, f"two distinct rows collapsed onto one trace: {seeds}"


def test_a_run_whose_rows_are_indistinguishable_refuses_to_publish_half_of_itself():
    """Failing loudly is the whole point: a silent halving is what actually happened, and nothing
    in the run, the summary or the dashboard showed it."""
    same = [row("q1", "R1"), row("q1", "R1")]          # identical on every identity field
    try:
        render(written(same))
    except SystemExit as exc:
        assert "not distinguishable" in str(exc) and "IDENTITY" in str(exc)
    else:
        raise AssertionError("published a run whose rows overwrite each other")


def test_a_trace_carries_what_a_reader_would_filter_by():
    """A dataset run links one trace per QUESTION, so a 148-row run shows 37 in the experiments
    table. Every row is still in Tracing, and these fields are the only way back to it."""
    from evals.publish import TRACE_FACETS
    t = render(written([row("q1", "R7", rung=7, tier="contested")]))["runs"][0]["traces"][0]
    f = t["facets"]
    assert f["qid"] == "q1" and f["config"] == "R7" and f["rung"] == 7
    assert f["tier"] == "contested" and f["expected_action"] == "answer"
    assert set(f) <= set(TRACE_FACETS)
    assert "cost_usd" not in f, "a measurement is a score, not a facet"


def test_a_cell_is_a_dataset_run_because_a_cell_is_what_the_experiment_varied():
    p = render(written([row("q1", "R7/A"), row("q1", "R7/D")]))
    assert [r["name"] for r in p["runs"]] == ["R7/A", "R7/D"]


def test_two_models_are_two_dataset_runs_and_never_one_averaged_one():
    """`summary.json` nests its numbers as model then cell, so that is the unit. Keying on the
    cell alone put both models in one run, whose coverage would then be an average across models
    and would disagree with the summary for the same run."""
    rows = [row("q1", "R1", model=m, correct=(m == "good")) for m in ("good", "bad")] + \
           [row("q2", "R1", model=m, correct=(m == "good")) for m in ("good", "bad")]
    p = render(written(rows))
    assert [r["name"] for r in p["runs"]] == ["bad · R1", "good · R1"]
    assert {r["metadata"]["model"] for r in p["runs"]} == {"good", "bad"}
    acc = {r["name"]: r["run_scores"]["balanced_accuracy"] for r in p["runs"]}
    assert acc["good · R1"] == 1.0 and acc["bad · R1"] == 0.0, \
        f"averaged across models instead of separated: {acc}"


def test_one_model_is_not_named_in_every_label():
    p = render(written([row("q1", "R1"), row("q1", "R7")]))
    assert [r["name"] for r in p["runs"]] == ["R1", "R7"]


def test_the_interval_comes_from_this_models_cell_and_not_another():
    """Scanning every model and keeping the last match handed one model another model's interval."""
    summary = {"meta": {"models": ["a", "b"], "reps": 1}, "cells": {
        "a": {"R1": {"uncertainty": {"coverage": {"lo": 0.1, "hi": 0.2}}}},
        "b": {"R1": {"uncertainty": {"coverage": {"lo": 0.8, "hi": 0.9}}}}}}
    p = render(written([row("q1", "R1", model="a"), row("q1", "R1", model="b")], summary))
    got = {r["metadata"]["model"]: (r["run_scores"]["coverage_lo"], r["run_scores"]["coverage_hi"])
           for r in p["runs"]}
    assert got == {"a": (0.1, 0.2), "b": (0.8, 0.9)}, got


def test_an_edited_suite_lands_in_a_different_dataset():
    """The hash covers the questions, so editing one moves the whole run to a new dataset rather
    than mixing two question sets under one name and comparing across them."""
    assert render(written([row("q1", suite="aaa")]))["dataset"] == "suite-aaa"
    assert render(written([row("q1", suite="bbb")]))["dataset"] == "suite-bbb"
    mixed = render(written([row("q1", suite="aaa"), row("q2", suite="bbb")]))
    assert mixed["dataset"] == "suite-mixed"


def test_a_run_recorded_before_the_hash_existed_says_so_rather_than_claiming_to_be_mixed():
    assert render(written([row("q1", suite=None)]))["dataset"] == "suite-unstamped"


def test_the_stored_trace_becomes_spans_of_the_right_kinds():
    spans = render(written([row("q1")]))["runs"][0]["traces"][0]["spans"]
    assert [s["type"] for s in spans] == ["generation", "tool", "event"]
    assert all(s["type"] in SPAN_TYPES for s in spans), "every kind must map to a backend type"
    gen, tool, act = spans
    assert gen["usage"] == {"input": 100, "output": 20, "cache_read_input_tokens": 80}
    assert gen["model"] == "gpt-5-mini"
    assert tool["name"] == "run_sql" and tool["level"] == "DEFAULT"
    assert act["name"] == "governed_numbers · allowed" and act["output"] == "value_moments = 3785"


def test_a_guardrail_that_stopped_an_answer_is_not_rendered_like_one_that_waved_it_through():
    """An act is a record. Rendering the record itself put a Python dict repr in the span title,
    which made the least readable part of the trace the most prominent one."""
    blocked = {"guardrail": "governed_numbers", "position": "after", "outcome": "blocked",
               "detail": "ungoverned figure"}
    spans = render(written([row("q1", acts=[blocked])]))["runs"][0]["traces"][0]["spans"]
    act = [s for s in spans if s["type"] == "event"][0]
    assert act["name"] == "governed_numbers · blocked" and act["level"] == "WARNING"
    assert "{" not in act["name"], "the span title must not be a Python repr"


def test_a_model_call_carries_the_tokens_it_used_and_the_price_we_computed():
    """A turn records `in`/`out`/`cached`. Reading `input_tokens`/`output_tokens` returned None for
    every call, so the backend showed no usage while the summary reported thousands of tokens.

    The price travels with it because usage plus a model name is enough for a backend to apply its
    own price table, which is the one thing it does not get to own."""
    gen = render(written([row("q1")]))["runs"][0]["traces"][0]["spans"][0]
    assert gen["usage"]["input"] == 100 and gen["usage"]["cache_read_input_tokens"] == 80

    from evals.publish import _turn_cost
    turn = {"in": 1_000_000, "out": 0, "cached": 0}
    priced = _turn_cost("gpt-5-mini", turn)
    assert priced is not None and priced > 0, "a known model must be priced by our own table"
    assert _turn_cost("a-model-nobody-has-priced", turn) is None, \
        "an unpriced model sends no cost, because a zero on a dashboard reads as free"
    assert _turn_cost("gpt-5-mini", {"in": 1_000_000, "out": 0, "cached": 1_000_000}) < priced, \
        "cached input is discounted here exactly as it is for the row"


def test_a_failed_tool_call_is_visible_as_an_error_rather_than_as_a_quiet_span():
    steps = [{"tool": "run_sql", "args": {}, "error": "no such column"},
             {"tool": "run_sql", "args": {}, "result": "1", "blocked_by": "R7"}]
    spans = render(written([row("q1", steps=steps)]))["runs"][0]["traces"][0]["spans"]
    tools = [s for s in spans if s["type"] == "tool"]
    assert [s["level"] for s in tools] == ["ERROR", "WARNING"]
    assert tools[0]["output"] == "no such column", "the error text is what makes it readable"


def test_a_score_keeps_the_type_it_was_declared_with():
    """Langfuse types a score by what it receives, so a boolean sent once as True and once as 1.0
    becomes two incomparable score types under one name. The type comes from SCORES."""
    assert _score("correct", True) == ("BOOLEAN", 1.0)
    assert _score("correct", False) == ("BOOLEAN", 0.0)
    assert _score("bucket", "right") == ("CATEGORICAL", "right")
    assert _score("cost_usd", 0.0012) == ("NUMERIC", 0.0012)
    for name in SCORES:
        assert _score(name, 1 if SCORES[name][0] != "CATEGORICAL" else "x")[0] == SCORES[name][0]


def test_an_unpriced_row_sends_no_cost_rather_than_a_zero():
    """`row.py` records None, not 0.0, when a model has no confirmed price. A zero on the
    dashboard would read as free."""
    scores = render(written([row("q1", cost_usd=None)]))["runs"][0]["traces"][0]["scores"]
    assert "cost_usd" not in scores
    assert "cost_usd" in render(written([row("q1")]))["runs"][0]["traces"][0]["scores"]


def test_the_silent_error_score_is_present_on_every_row():
    """It is not a stored field but a predicate, and it is the thing a reader most wants to filter
    a dashboard by: show me the answers nobody could have caught. It was silently absent."""
    clean = render(written([row("q1")]))["runs"][0]["traces"][0]["scores"]
    bad = render(written([row("q1", confident_wrong=True, correct=False,
                              bucket="wrong")]))["runs"][0]["traces"][0]["scores"]
    assert clean["silent_error"] is False and bad["silent_error"] is True

    from evals.selective import served_wrong
    assert served_wrong({"off_governance": True}) and not served_wrong({"outcome": "answer"}), \
        "the predicate is selective's, so the score and the metric cannot disagree"


def test_the_set_level_numbers_are_ours_and_travel_with_their_interval():
    # Addressed by the row's OWN model. Before the fix any model's entry would have matched.
    summary = {"meta": {"models": ["gpt-5-mini"], "reps": 1},
               "cells": {"gpt-5-mini": {
                   "A": {"uncertainty": {"coverage": {"lo": 0.4, "hi": 0.9}}}}}}
    rows = [row("q1", "A"), row("q2", "A", correct=False, bucket="wrong", confident_wrong=True)]
    s = render(written(rows, summary))["runs"][0]["run_scores"]
    assert s["n_questions"] == 2
    assert s["coverage"] == 1.0 and s["silent_error"] == 0.5
    assert (s["coverage_lo"], s["coverage_hi"]) == (0.4, 0.9), \
        "a point estimate without its interval reads as exact"


def test_a_set_level_number_cannot_collide_with_a_row_level_one():
    """`silent_error` is a boolean about one row and a rate over a cell. Published under one name,
    a chart averages a fact with a proportion and the number means nothing."""
    p = render(written([row("q1", "A"), row("q2", "A")]))
    rows = set(p["runs"][0]["traces"][0]["scores"])
    sets = {RUN_PREFIX + k for k in p["runs"][0]["run_scores"]}
    assert "silent_error" in rows and RUN_PREFIX + "silent_error" in sets
    assert not (rows & sets), f"a name means two things at once: {rows & sets}"


def test_an_experiment_run_reads_the_same_as_a_grid_run():
    """Two runners write two files. The difference is about the runners, not about the rows, so
    it is absorbed in render rather than pushed onto every caller."""
    rows = [row("q1", "A"), row("q1", "B")]
    grid = written(rows)
    exp = Path(tempfile.mkdtemp())
    (exp / "run.json").write_text(json.dumps({"rows": rows}))
    (exp / "summary.json").write_text((grid / "summary.json").read_text())
    def without_seeds(p):
        # A seed names the RUN it came from, deliberately, so two runs never share a trace. These
        # are two directories holding the same rows, so only the seeds may differ.
        for r in p["runs"]:
            for t in r["traces"]:
                t.pop("seed")
        return p

    assert without_seeds(render(exp)) == without_seeds(render(grid))


def test_an_absent_backend_is_reported_and_never_raised():
    """`make eval` and every test must run with no dependency and no credentials. Absence returns
    a sentence; it does not become a stack trace, and it does not fail a run that already has
    every number it needs."""
    out = emit(written([row("q1")]), dry_run=True)
    assert out["sent"] is False and out["traces"] == 1 and out["items"] == 1

    import os
    saved = {k: os.environ.pop(k, None) for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")}
    try:
        out = emit(written([row("q1")]))
        assert out["sent"] is False
        assert "not installed" in out["reason"] or "not configured" in out["reason"]
    finally:
        os.environ.update({k: v for k, v in saved.items() if v is not None})


if __name__ == "__main__":
    # `bench test` runs each file as a SCRIPT, so a test absent from this block runs nowhere.
    test_one_dataset_item_per_question_however_many_times_it_was_asked()
    test_two_rows_that_differ_only_by_an_unlisted_dimension_do_not_share_a_trace()
    test_a_run_whose_rows_are_indistinguishable_refuses_to_publish_half_of_itself()
    test_a_trace_carries_what_a_reader_would_filter_by()
    test_a_cell_is_a_dataset_run_because_a_cell_is_what_the_experiment_varied()
    test_two_models_are_two_dataset_runs_and_never_one_averaged_one()
    test_one_model_is_not_named_in_every_label()
    test_the_interval_comes_from_this_models_cell_and_not_another()
    test_an_edited_suite_lands_in_a_different_dataset()
    test_a_run_recorded_before_the_hash_existed_says_so_rather_than_claiming_to_be_mixed()
    test_the_stored_trace_becomes_spans_of_the_right_kinds()
    test_a_guardrail_that_stopped_an_answer_is_not_rendered_like_one_that_waved_it_through()
    test_the_silent_error_score_is_present_on_every_row()
    test_a_model_call_carries_the_tokens_it_used_and_the_price_we_computed()
    test_a_failed_tool_call_is_visible_as_an_error_rather_than_as_a_quiet_span()
    test_a_score_keeps_the_type_it_was_declared_with()
    test_an_unpriced_row_sends_no_cost_rather_than_a_zero()
    test_the_set_level_numbers_are_ours_and_travel_with_their_interval()
    test_a_set_level_number_cannot_collide_with_a_row_level_one()
    test_an_experiment_run_reads_the_same_as_a_grid_run()
    test_an_absent_backend_is_reported_and_never_raised()
    print("OK — one item per question, a run per cell, typed scores, our own set-level numbers "
          "with intervals, both run shapes, and an absent backend that reports instead of raising.")
