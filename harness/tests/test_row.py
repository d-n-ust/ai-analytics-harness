"""The row builder is the only recorder — proved, not asserted in a comment.

Three runners write measurements and they had already drifted: the same fact under three names,
one name over two facts, and telemetry the engine measured that two of the three never wrote
down. `evals/row.py` exists to make that impossible. A rule that lives only in that module's
docstring is a rule until the next runner is written, so it is checked here two ways:

  by CONTRACT     the row carries every field the published archive is keyed on, plus the
                  telemetry, and `elapsed_s` cannot be forgotten
  by STRUCTURE    no runner assembles a row of its own

Run: uv run python -m pytest harness/tests/test_row.py -q     (or run this file directly)
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

from agent.core.models import MODEL_SPECS
from agent.core.outcomes import Answer
from evals.row import ROW_SCHEMA_VERSION, measured_row

# Every field the published archive is keyed on. `components/coverage_audit.py` reads every run
# ever stored and the site's essays cite these by name, so this list may GROW and may not shrink:
# a rename is a silent re-analysis of numbers that are already published.
PUBLISHED_FIELDS = {
    "qid", "tier", "question", "model", "gold",
    "answer", "explanation", "outcome", "reason", "missing", "refused_by",
    "source_metric", "declared_value", "typed_value", "value_recovered", "direction",
    "candidates", "sources",
    "correct", "executed", "abstained", "confident_wrong", "fabricated", "off_governance",
    "wrong_scope", "wrong_metric", "needs_judge", "bucket", "expected_refuse",
    "reason_match", "metric_match", "driver_ok", "cause_ok", "score",
    "steps", "turns", "acts", "claims", "claim_audit", "claim_retries", "hand_backs",
    "repairs", "scope_shadow", "verifier_verdict", "error",
    "input_tokens", "output_tokens", "cached_tokens", "tool_calls", "model_calls",
    "iterations", "elapsed_s", "schema_version",
}

# What v18 adds. Named separately so the reason each one exists is recorded next to it.
V18_FIELDS = {
    "cost_usd",           # per row, so cost splits by pile and by outcome, not only by cell
    "round_trips",        # what a clarification costs the reader, as a column not a footnote
    "expected_action",    # WHICH pile — the main runner computed it and threw it away
    "served_candidate",   # contested: which reading was served
    "divergence",         # contested: how far it sat from the one it displaced
}

CASE = {"id": "q1", "tier": "answerable", "question": "how many active users?",
        "expect": {"type": "metric_answer", "tolerance": 0.005, "metric": "active_users",
                   "gold_sql": "SELECT 1"}}


def _answer(**kw) -> Answer:
    base = dict(question=CASE["question"], rung=3, model="gpt-5-mini", answer="886",
                outcome="answer", declared_value=886.0, typed_value=True,
                input_tokens=12_000, output_tokens=400, cached_tokens=8_000,
                tool_calls=3, model_calls=4, iterations=2)
    return Answer(**{**base, **kw})


def test_the_row_carries_every_published_field_and_the_telemetry():
    row = measured_row(_answer(), CASE, 886.0, elapsed_s=1.234)
    missing = PUBLISHED_FIELDS - set(row)
    assert not missing, f"the row no longer carries published fields: {sorted(missing)}"
    assert V18_FIELDS <= set(row), f"missing v18 fields: {sorted(V18_FIELDS - set(row))}"
    assert row["schema_version"] == ROW_SCHEMA_VERSION


def test_latency_cannot_be_forgotten():
    """A default of 0.0 is indistinguishable in a stored row from a run that was instantaneous,
    and latency is the one field that cannot be recovered afterwards. So it is required, and a
    caller that omits it fails at the call site rather than writing a column of zeros."""
    try:
        measured_row(_answer(), CASE, 886.0)
    except TypeError:
        return
    raise AssertionError("elapsed_s is defaultable — a runner can now silently record no latency")


def test_cost_is_the_model_price_and_is_none_when_there_is_no_price():
    row = measured_row(_answer(), CASE, 886.0, elapsed_s=1.0)
    spec = MODEL_SPECS["gpt-5-mini"]
    assert row["cost_usd"] == spec.cost(12_000, 400, 8_000)
    # A cached token is a SUBSET of input, billed at the discount — never an addition.
    assert row["cost_usd"] < spec.cost(12_000, 400, 0)
    # An unpriced model records None, not 0.0: a zero sums into a cell total as though free.
    unknown = measured_row(_answer(model="mock"), CASE, 886.0, elapsed_s=1.0)
    assert unknown["cost_usd"] is None


def test_a_clarification_costs_one_round_trip_and_nothing_else_does():
    for outcome, expected in (("answer", 0), ("refuse", 0), ("clarify", 1), ("error", 0)):
        row = measured_row(_answer(outcome=outcome), CASE, 886.0, elapsed_s=1.0)
        assert row["round_trips"] == expected, f"{outcome} priced at {row['round_trips']}"


def test_caller_context_merges_last_and_cannot_be_dropped():
    """A runner owns what it VARIES — the cell, the rung, the arm — and the row owns everything
    about the run. Merging context last means a runner can override a field it genuinely owns
    and cannot silently lose one it passed."""
    row = measured_row(_answer(), CASE, 886.0, elapsed_s=1.0,
                       rung=3, config="R9", rep=2, arm="E_disclosed")
    assert (row["rung"], row["config"], row["rep"], row["arm"]) == (3, "R9", 2, "E_disclosed")


# EMPTY, and it is meant to stay that way. Every runner records through `measured_row`, so every
# experiment is on the same telemetry axis. A name appearing here means a second row schema was
# born and someone chose to live with it; the test fails on an entry that is no longer true, so
# the list cannot quietly become a monument to a migration that already finished.
UNMIGRATED_RUNNERS: set[str] = set()


def _hand_built_rows(path: Path) -> list[int]:
    """Line numbers of dict literals in `path` that are measurement rows.

    A row is recognised by what it carries rather than by its variable name: an `outcome`
    alongside anything that only a graded, traced run has. Both spellings count — the keys
    written literally, and the ones arriving through a `**graded` splat, which is how the
    contested fixture's row hid from a first, narrower version of this check.
    """
    found = []
    for node in ast.walk(ast.parse(path.read_text())):
        if not isinstance(node, ast.Dict):
            continue
        keys = {k.value for k in node.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        splatted = any(k is None for k in node.keys)
        companions = {"correct", "grade", "bucket", "tool_calls", "model_calls", "steps", "qid"}
        if "outcome" in keys and (companions & keys or splatted):
            found.append(node.lineno)
    return found


def test_no_runner_assembles_a_row_of_its_own():
    """The rule the module exists for, checked structurally rather than by review.

    A runner that hand-builds a row is writing a second schema. That is how the same fact came to
    have three names, how one name came to cover two facts, and how telemetry the engine measures
    on every run went unrecorded by two runners out of three.
    """
    root = Path(__file__).resolve().parents[1]
    runners = [root / "evals" / "runner.py",
               root / "experiments" / "engine.py",
               root / "experiments" / "06_third_state" / "fixture" / "run.py"]
    offenders = {}
    for path in runners:
        if not path.exists():          # a fixture may be retired; absence is not a failure
            continue
        lines = _hand_built_rows(path)
        if lines:
            offenders[str(path.relative_to(root))] = lines

    new = set(offenders) - UNMIGRATED_RUNNERS
    assert not new, (
        f"{sorted(new)} assemble a row instead of calling evals.row.measured_row. Their telemetry "
        "and field names are free to drift from every other experiment's.")
    done = UNMIGRATED_RUNNERS - set(offenders)
    assert not done, (
        f"{sorted(done)} no longer hand-build a row — remove them from UNMIGRATED_RUNNERS so the "
        "debt list keeps meaning what it says.")


def test_the_row_builder_is_the_only_place_that_stamps_a_schema_version():
    """Two copies of a version number is how a row comes to claim a schema its reader does not
    implement. `report.py` re-exports it; nothing else may define one."""
    import evals.report as report
    import evals.row as row_module
    assert report.ROW_SCHEMA_VERSION is row_module.ROW_SCHEMA_VERSION
    src = inspect.getsource(report)
    assert "ROW_SCHEMA_VERSION = " not in src, "report.py defines a second schema version"


if __name__ == "__main__":
    # `bench test` runs each file as a SCRIPT, so a test absent from this block runs nowhere.
    test_the_row_carries_every_published_field_and_the_telemetry()
    test_latency_cannot_be_forgotten()
    test_cost_is_the_model_price_and_is_none_when_there_is_no_price()
    test_a_clarification_costs_one_round_trip_and_nothing_else_does()
    test_caller_context_merges_last_and_cannot_be_dropped()
    test_no_runner_assembles_a_row_of_its_own()
    test_the_row_builder_is_the_only_place_that_stamps_a_schema_version()
    print("OK — one recorder: the published fields survive, latency cannot be forgotten, "
          "cost follows the model price, and no runner writes a row of its own.")
