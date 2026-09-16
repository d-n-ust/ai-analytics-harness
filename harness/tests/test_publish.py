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


# ---------------------------------------------------------------------------------------------
# The SEND path. Everything above tests `render`, which is pure; this tests `emit`, which was
# covered by nothing until the four defects below had already been shipped and found by hand.
# ---------------------------------------------------------------------------------------------

class Recorder:
    """Stands in for the backend and remembers everything it was asked to do.

    Small on purpose: it implements exactly the surface `emit` uses, so a change in that surface
    breaks this file rather than breaking a dashboard quietly. It needs no server, no credentials
    and no langfuse install, which is what lets CI run it — CI syncs without the observability
    group, so the real client is not importable there.
    """

    def __init__(self, existing_runs=()):
        self.created, self.items, self.run_items = [], [], []
        self.scores, self.traces, self.spans = [], [], []
        self._existing = list(existing_runs)
        self._current = None
        self.flushed = 0
        # emit reaches the raw API as client.api.datasets.get_runs and
        # client.api.dataset_run_items.create, so those paths must resolve exactly.
        self.api = type("API", (), {"datasets": self, "dataset_run_items": self})()

    # -- client surface ------------------------------------------------------------------
    def create_dataset(self, *, name, description=None, **kw):
        self.created.append(name)

    def create_dataset_item(self, *, dataset_name, id, input, expected_output, metadata, **kw):
        self.items.append({"id": id, "input": input, "expected": expected_output,
                           "metadata": metadata})

    def create_trace_id(self, *, seed=None):
        import hashlib
        return hashlib.sha256((seed or "").encode()).hexdigest()[:32]

    def create_score(self, *, name, value, score_id=None, data_type=None,
                     trace_id=None, dataset_run_id=None, **kw):
        self.scores.append({"name": name, "value": value, "type": data_type,
                            "id": score_id, "trace_id": trace_id, "run_id": dataset_run_id})

    def start_as_current_observation(self, **kw):
        self.traces.append(kw)
        self._current = (kw.get("trace_context") or {}).get("trace_id")
        return _Span(self, kw)

    def start_observation(self, **kw):
        # The real client creates a child of whatever span is current, which is why emit calls it
        # on the client rather than on the root span.
        self.spans.append({**kw, "trace": getattr(self, "_current", None)})
        return _Child()

    def flush(self):
        self.flushed += 1

    # -- raw api surface -----------------------------------------------------------------
    def get_runs(self, dataset, page=1, limit=100):
        return type("B", (), {"data": self._existing if page == 1 else []})()

    def create(self, *, run_name, dataset_item_id, trace_id, run_description=None, metadata=None,
               **kw):
        self.run_items.append({"run": run_name, "item": dataset_item_id, "trace": trace_id,
                               "metadata": metadata})
        return type("I", (), {"dataset_run_id": f"id-of-{run_name}"})()


class _Span:
    def __init__(self, rec, kw):
        self.rec, self.kw = rec, kw
        self.trace_id = kw.get("trace_context", {}).get("trace_id")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def set_trace_io(self, **kw):
        pass

    def end(self, end_time=None):
        pass


class _Child:
    def end(self, end_time=None):
        pass


def _emit(rows, summary=None, run_dir=None, **kw):
    """One publish. `run_dir` is reusable on purpose: the run directory's NAME is part of every
    trace seed, so simulating a re-publish means sending the same directory twice, not two
    directories holding the same rows."""
    rec = Recorder(**kw)
    out = emit(run_dir or written(rows, summary), client=rec)
    return rec, out


def test_emit_sends_one_item_per_question_and_one_trace_per_row():
    rows = [row(q, c, rep=r) for q in ("q1", "q2") for c in ("A", "B") for r in (0, 1)]
    rec, out = _emit(rows)
    assert out["sent"] is True
    assert rec.created == ["suite-abc123"], "the dataset is created once, by suite hash"
    assert sorted(i["id"] for i in rec.items) == ["q1", "q2"], "one item per QUESTION"
    assert len(rec.run_items) == 8, "every row is linked"
    assert len({r["trace"] for r in rec.run_items}) == 8, "and every row has its own trace"
    assert rec.flushed == 1, "an unflushed emit loses the tail of the run"


def test_emit_writes_no_trace_bodies_for_a_run_it_has_already_published():
    """A stable trace id does not make the SPANS inside it stable, so re-sending appended a second
    copy of every model call and doubled the trace. The dataset run is the unit of publication."""
    d = written([row("q1", "A"), row("q2", "A")])
    fresh, _ = _emit(None, run_dir=d)
    assert fresh.spans, "a first publish must write the bodies"

    already = [type("R", (), {"name": n, "id": "x"})()
               for n in {r["run"] for r in fresh.run_items}]
    again, out = _emit(None, run_dir=d, existing_runs=already)
    assert again.spans == [], "re-publishing must not append a second copy of every span"
    assert again.run_items == [], "nor a second set of run items"
    assert [s for s in again.scores if s["trace_id"]], "but scores ARE rewritten — regrade needs it"
    assert out["rescored"] == 1


def test_a_score_is_written_under_a_stable_id_so_a_regrade_corrects_it_in_place():
    import json as _json
    d = written([row("q1", "A")])
    first, _ = _emit(None, run_dir=d)
    # What `bench regrade` does: the same run directory, the same rows, a corrected verdict.
    (d / "raw.jsonl").write_text(_json.dumps(row("q1", "A", correct=False, bucket="wrong")) + "\n")
    second, _ = _emit(None, run_dir=d)
    by_name = {s["name"]: s for s in first.scores}
    again = {s["name"]: s for s in second.scores}
    assert by_name["correct"]["id"] == again["correct"]["id"], \
        "a regrade must correct the score a reader has open, not add a second beside it"
    assert by_name["correct"]["value"] != again["correct"]["value"]


def test_every_score_reaches_the_backend_with_its_declared_type():
    rec, _ = _emit([row("q1", "A")])
    typed = {s["name"]: s["type"] for s in rec.scores if s["trace_id"]}
    assert typed["correct"] == "BOOLEAN" and typed["bucket"] == "CATEGORICAL"
    assert typed["cost_usd"] == "NUMERIC"
    assert typed["silent_error"] == "BOOLEAN"


def test_set_level_scores_go_to_the_run_and_never_collide_with_a_row_score():
    rec, _ = _emit([row("q1", "A"), row("q2", "A")])
    run_level = {s["name"] for s in rec.scores if s["run_id"]}
    row_level = {s["name"] for s in rec.scores if s["trace_id"]}
    assert "run/coverage" in run_level and "run/silent_error" in run_level
    assert not (run_level & row_level), f"a name means two things at once: {run_level & row_level}"


def test_a_model_call_is_sent_with_its_usage_and_our_price():
    """Usage and a model name are enough for a backend to apply its OWN price table, which is the
    one thing it does not get to own. The turns must carry the price row.py computed."""
    rec, _ = _emit([row("q1", "A")])
    gen = [s for s in rec.spans if s["as_type"] == "generation"][0]
    assert gen["usage_details"]["input"] == 100
    assert gen["usage_details"]["cache_read_input_tokens"] == 80
    assert gen["cost_details"] is not None and gen["cost_details"]["total"] > 0


def test_a_cell_with_a_slash_produces_a_run_name_that_can_be_fetched_back():
    """A cell is named things like R7/D_declared, and the backend addresses a run by name IN THE
    URL PATH — so a slash made a run that existed and could not be read back."""
    rec, _ = _emit([row("q1", "R7/D_declared"), row("q1", "R7/A_implicit")])
    for item in rec.run_items:
        assert "/" not in item["run"], f"unfetchable run name: {item['run']}"
        assert "--" not in item["run"].split("--", 1)[1], "separator collapsed to a double dash"
    assert {i["metadata"]["cell"] for i in rec.run_items} == {"R7/D_declared", "R7/A_implicit"}, \
        "the exact cell must survive in metadata, since the name could not carry it"


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
    test_emit_sends_one_item_per_question_and_one_trace_per_row()
    test_emit_writes_no_trace_bodies_for_a_run_it_has_already_published()
    test_a_score_is_written_under_a_stable_id_so_a_regrade_corrects_it_in_place()
    test_every_score_reaches_the_backend_with_its_declared_type()
    test_set_level_scores_go_to_the_run_and_never_collide_with_a_row_score()
    test_a_model_call_is_sent_with_its_usage_and_our_price()
    test_a_cell_with_a_slash_produces_a_run_name_that_can_be_fetched_back()
    print("OK — one item per question, a run per cell, typed scores, our own set-level numbers "
          "with intervals, both run shapes, and an absent backend that reports instead of raising.")
