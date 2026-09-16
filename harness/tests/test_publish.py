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
         "turns": [{"input_tokens": 100, "output_tokens": 20, "ms": 900}],
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


def test_a_cell_is_a_dataset_run_because_a_cell_is_what_the_experiment_varied():
    p = render(written([row("q1", "R7/A"), row("q1", "R7/D")]))
    assert [r["name"] for r in p["runs"]] == ["R7/A", "R7/D"]


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
    assert gen["usage"] == {"input": 100, "output": 20} and gen["model"] == "gpt-5-mini"
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
    summary = {"meta": {"models": ["m"], "reps": 1},
               "cells": {"m": {"A": {"uncertainty": {"coverage": {"lo": 0.4, "hi": 0.9}}}}}}
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
    assert render(exp) == render(grid)


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
    test_a_cell_is_a_dataset_run_because_a_cell_is_what_the_experiment_varied()
    test_an_edited_suite_lands_in_a_different_dataset()
    test_a_run_recorded_before_the_hash_existed_says_so_rather_than_claiming_to_be_mixed()
    test_the_stored_trace_becomes_spans_of_the_right_kinds()
    test_a_guardrail_that_stopped_an_answer_is_not_rendered_like_one_that_waved_it_through()
    test_the_silent_error_score_is_present_on_every_row()
    test_a_failed_tool_call_is_visible_as_an_error_rather_than_as_a_quiet_span()
    test_a_score_keeps_the_type_it_was_declared_with()
    test_an_unpriced_row_sends_no_cost_rather_than_a_zero()
    test_the_set_level_numbers_are_ours_and_travel_with_their_interval()
    test_a_set_level_number_cannot_collide_with_a_row_level_one()
    test_an_experiment_run_reads_the_same_as_a_grid_run()
    test_an_absent_backend_is_reported_and_never_raised()
    print("OK — one item per question, a run per cell, typed scores, our own set-level numbers "
          "with intervals, both run shapes, and an absent backend that reports instead of raising.")
